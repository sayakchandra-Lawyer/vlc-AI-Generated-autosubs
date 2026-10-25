--[[
  AutoSubs core: shared logic for the AutoSubs interface script (automatic
  mode) and the AutoSubs extension (manual mode).

  VLC's Lua API cannot read audio, so the heavy lifting happens in an
  external helper (vlc-autosubs-helper, Whisper speech translation).
  This module:
    * works out the local file path of the video that is playing,
    * decides whether it needs English subtitles,
    * starts the helper in the background with a small "job" file,
    * polls the helper's status file and loads the subtitle snapshots
      it writes into the running video.

  Everything lives in <VLC user data dir>/autosubs:
    autosubs.conf           settings (key=value); "helper" is set by
                            `vlc-autosubs install`
    app/                    the prebuilt helper (downloadable builds only)
    jobs/<id>.job           written by Lua: what to process
    jobs/<id>.status        written by the helper: progress
    jobs/<id>.<n>.srt       subtitle snapshots (latest one is kept)
--]]

local M = {}

local IS_WIN = package.config:sub(1, 1) == "\\"
local SEP = IS_WIN and "\\" or "/"

-- Settings; any of them can be overridden in autosubs.conf.
local DEFAULTS = {
  enabled = "1",               -- automatic mode on/off (interface script)
  helper = "",                 -- helper executable, set by `vlc-autosubs install`
  model = "auto",              -- auto | tiny | base | small | medium | large-v3
  device = "auto",             -- auto | cpu | cuda
  write_sidecar = "1",         -- also save "<video>.en.srt" next to the video
  skip_english_audio = "1",    -- don't subtitle videos whose audio is English
  skip_if_english_subs = "1",  -- skip when English subtitles already exist
  osd = "1",                   -- show on-screen status messages
}

local AUDIO_EXTS = {
  mp3 = true, flac = true, wav = true, m4a = true, aac = true, ogg = true,
  opus = true, wma = true, alac = true, aiff = true, ape = true,
}

local SIDECAR_SUFFIXES = {
  ".en.srt", ".eng.srt", ".english.srt", ".EN.srt", ".English.srt",
  ".en.ass", ".en.ssa", ".en.vtt", ".eng.ass", ".eng.vtt",
}

local LANG_NAMES = {
  fr = "French", ru = "Russian", ja = "Japanese", cs = "Czech", de = "German",
  es = "Spanish", it = "Italian", pt = "Portuguese", zh = "Chinese",
  ko = "Korean", pl = "Polish", uk = "Ukrainian", nl = "Dutch", sv = "Swedish",
  tr = "Turkish", ar = "Arabic", hi = "Hindi", el = "Greek", hu = "Hungarian",
  fi = "Finnish", da = "Danish", no = "Norwegian", ro = "Romanian",
  sk = "Slovak", he = "Hebrew", th = "Thai", vi = "Vietnamese", id = "Indonesian",
  fa = "Persian", bn = "Bengali", ta = "Tamil", sr = "Serbian", hr = "Croatian",
  bg = "Bulgarian", ca = "Catalan", ms = "Malay", en = "English",
}

-- How long a "running" job may go without a heartbeat before we assume
-- the helper died (it writes one every 10 s).
local STALE_AFTER_S = 60
-- Load the next snapshot when playback gets this close to the end of the
-- subtitles that are already loaded. Loading lazily keeps the number of
-- extra subtitle tracks in VLC's menu small.
local LOAD_AHEAD_S = 45

---------------------------------------------------------------------------
-- small helpers
---------------------------------------------------------------------------

local function join(...) return table.concat({ ... }, SEP) end

local function exists(path)
  local f = io.open(path, "rb")
  if f then f:close() return true end
  return false
end

local function read_kv(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local t = {}
  for line in f:lines() do
    local k, v = line:match("^%s*([%w_]+)%s*=%s*(.-)%s*$")
    if k then t[k] = v end
  end
  f:close()
  return t
end

local function write_kv(path, t)
  local f = io.open(path, "w")
  if not f then return false end
  for k, v in pairs(t) do f:write(k, "=", tostring(v), "\n") end
  f:close()
  return true
end

local function quote(s)
  if IS_WIN then return '"' .. s .. '"' end
  return "'" .. (s:gsub("'", "'\\''")) .. "'"
end

-- djb2, kept to 32 bits (exact with Lua 5.1 doubles).
local function hash(s)
  local h = 5381
  for i = 1, #s do h = (h * 33 + s:byte(i)) % 4294967296 end
  return string.format("%08x", h)
end

local function log(msg) vlc.msg.info("[autosubs] " .. msg) end

function M.root() return join(vlc.config.userdatadir(), "autosubs") end

local function jobs_dir() return join(M.root(), "jobs") end

function M.load_config()
  local cfg = {}
  for k, v in pairs(DEFAULTS) do cfg[k] = v end
  local file = read_kv(join(M.root(), "autosubs.conf"))
  if file then for k, v in pairs(file) do cfg[k] = v end end
  return cfg
end

local function truthy(v) return v == "1" or v == "true" or v == "yes" or v == "on" end

local function spawn(args)
  local parts = {}
  for _, a in ipairs(args) do parts[#parts + 1] = quote(a) end
  local cmd = table.concat(parts, " ")
  if IS_WIN then
    cmd = 'start "" /B ' .. cmd
  else
    cmd = "nohup " .. cmd .. " >/dev/null 2>&1 &"
  end
  log("starting helper: " .. cmd)
  return os.execute(cmd)
end

local function osd(cfg, text)
  log(text)
  if truthy(cfg.osd) then
    pcall(vlc.osd.message, "AutoSubs: " .. text, nil, "top-right", 4000000)
  end
end

local function lang_name(code)
  if not code or code == "" then return "?" end
  return LANG_NAMES[code] or code
end

local function play_time_s()
  local input = vlc.object.input()
  if not input then return 0 end
  local ok, t = pcall(vlc.var.get, input, "time")
  if ok and type(t) == "number" then return t / 1000000 end
  return 0
end

---------------------------------------------------------------------------
-- media inspection
---------------------------------------------------------------------------

-- Local filesystem path of the playing item, or nil (streams, discs, ...).
function M.current_media_path()
  local item = vlc.input.item()
  if not item then return nil end
  local uri = item:uri()
  if not uri or not uri:match("^file://") then return nil end
  local path
  if vlc.strings.make_path then path = vlc.strings.make_path(uri) end
  if not path then
    path = vlc.strings.decode_uri(uri:gsub("^file://", ""))
    if IS_WIN then path = path:gsub("^/", ""):gsub("/", "\\") end
  end
  return path
end

local function has_english_sidecar(path)
  local base = path:gsub("%.[^%.\\/]*$", "")
  for _, suffix in ipairs(SIDECAR_SUFFIXES) do
    if exists(base .. suffix) then return true end
  end
  return false
end

-- Best effort: looks for a subtitle stream tagged English in the media info.
local function has_embedded_english_subs()
  local item = vlc.input.item()
  if not item then return false end
  local ok, info = pcall(item.info, item)
  if not ok or type(info) ~= "table" then return false end
  for _, cat in pairs(info) do
    if type(cat) == "table" then
      local is_sub, is_en = false, false
      for _, v in pairs(cat) do
        v = tostring(v):lower()
        if v == "subtitle" then is_sub = true end
        if v:match("^english") or v == "en" or v == "eng" then is_en = true end
      end
      if is_sub and is_en then return true end
    end
  end
  return false
end

local function skip_reason(path, cfg, force)
  local ext = (path:match("%.([^%.\\/]+)$") or ""):lower()
  if AUDIO_EXTS[ext] then return "audio-only file, skipped" end
  if force then return nil end
  if truthy(cfg.skip_if_english_subs) then
    if has_english_sidecar(path) then return "English subtitle file already present" end
    if has_embedded_english_subs() then return "video already has English subtitles" end
  end
  return nil
end

---------------------------------------------------------------------------
-- jobs
---------------------------------------------------------------------------

local function job_for(path)
  local name = path:match("([^\\/]+)$") or "video"
  name = name:gsub("%.[^%.]*$", ""):gsub("[^%w%-]", "_"):sub(1, 40)
  local id = hash(path) .. "_" .. name
  local dir = jobs_dir()
  return {
    id = id,
    file = join(dir, id .. ".job"),
    status = join(dir, id .. ".status"),
    srt = function(n) return join(dir, id .. "." .. n .. ".srt") end,
  }
end

local function needs_start(st)
  if not st then return true end
  if st.state == "cancelled" then return true end
  if st.state == "starting" or st.state == "loading" or st.state == "running" then
    local updated = tonumber(st.updated) or 0
    return os.time() - updated > STALE_AFTER_S
  end
  return false
end

local function start_job(state)
  local cfg, job = state.cfg, state.job
  local helper = cfg.helper
  if helper == "" or not exists(helper) then
    state.message = "helper not found; run: vlc-autosubs install"
    osd(cfg, state.message)
    return false
  end
  local spec = {
    media = state.path,
    model = cfg.model,
    device = cfg.device,
    write_sidecar = cfg.write_sidecar,
    skip_english_audio = state.force and "0" or cfg.skip_english_audio,
  }
  if not write_kv(job.file, spec) then
    -- jobs dir missing (installer not run?): create it and retry once
    os.execute((IS_WIN and "mkdir " or "mkdir -p ") .. quote(jobs_dir()))
    if not write_kv(job.file, spec) then
      state.message = "cannot write to " .. jobs_dir()
      osd(cfg, state.message)
      return false
    end
  end
  -- Claim the job right away so a second VLC script won't start it again.
  write_kv(job.status, { state = "starting", updated = os.time(), snapshot = 0 })
  spawn({ helper, job.file })
  state.starts = state.starts + 1
  state.message = "starting English subtitle generation"
  osd(cfg, "generating English subtitles…")
  return true
end

local function load_snapshot(state, n, covered)
  local file = state.job.srt(n)
  if not exists(file) then return false end
  local ok, err = pcall(vlc.input.add_subtitle, file, true)
  if not ok then
    log("add_subtitle failed: " .. tostring(err))
    return false
  end
  log("loaded " .. file .. " (covers " .. covered .. " s)")
  state.loaded = n
  state.loaded_covered = covered
  return true
end

---------------------------------------------------------------------------
-- public API
---------------------------------------------------------------------------

function M.new_state() return {} end

--[[
  Advance the state machine for whatever is playing now. Call it
  periodically (interface script) or on events (extension).
  opts.now   - act immediately instead of waiting a tick for VLC to probe
               the file
  opts.force - user asked explicitly: ignore "already has English subs",
               retry failed jobs and load the newest snapshot right away
  opts.auto  - automatic mode; respects enabled=0 in autosubs.conf
--]]
function M.tick(state, opts)
  opts = opts or {}
  local path = M.current_media_path()
  if path ~= state.path then
    for k in pairs(state) do state[k] = nil end
    state.path = path
    state.ticks, state.loaded, state.loaded_covered, state.starts = 0, 0, 0, 0
    state.cfg = M.load_config()
    state.message = path and "waiting" or "no local video playing"
    if path then state.job = job_for(path) end
  end
  if not path then return end
  if opts.force and not state.force then
    -- explicit request: start over from a clean slate
    state.force, state.finished, state.checked, state.starts = true, false, false, 0
  end
  if state.finished then return end

  local cfg = state.cfg
  if opts.auto and not truthy(cfg.enabled) then
    state.finished, state.message = true, "automatic mode disabled in autosubs.conf"
    return
  end

  state.ticks = state.ticks + 1
  if state.ticks < 2 and not opts.now then return end

  if not state.checked then
    state.checked = true
    local reason = skip_reason(path, cfg, state.force)
    if reason then
      state.finished, state.message = true, reason
      log(path .. ": " .. reason)
      return
    end
  end

  local st = read_kv(state.job.status)
  if st and st.state == "error" and state.starts == 0 then
    st = nil -- retry once per playback (the helper may have been fixed since)
  end
  if st and st.state == "english" and state.force and state.starts == 0 then
    st = nil -- user wants subtitles anyway
  end
  if needs_start(st) then
    if state.starts >= 2 then
      state.finished, state.message = true, "helper keeps stopping; see jobs/" .. state.job.id .. ".log"
      osd(cfg, state.message)
      return
    end
    start_job(state)
    return
  end

  local snap = tonumber(st.snapshot) or 0
  local covered = tonumber(st.covered) or 0
  local done = st.state == "done"
  if snap > state.loaded then
    local want = done or state.loaded == 0 or opts.force
      or play_time_s() > state.loaded_covered - LOAD_AHEAD_S
    if want then load_snapshot(state, snap, covered) end
  end

  if st.state == "loading" then
    state.message = "loading Whisper model (first run downloads it)…"
  elseif st.state == "running" or st.state == "starting" then
    local pct = math.floor((tonumber(st.progress) or 0) * 100 + 0.5)
    if st.language == "en" then
      state.message = string.format("transcribing English: %d%%", pct)
    else
      state.message = string.format("translating %s → English: %d%%", lang_name(st.language), pct)
    end
  elseif st.state == "english" then
    state.finished, state.message = true, "audio is already English, no subtitles needed"
    log(state.message)
  elseif st.state == "error" then
    state.finished = true
    state.message = "error: " .. (st.error or "unknown") .. " (see jobs/" .. state.job.id .. ".log)"
    osd(cfg, state.message)
  elseif done then
    if snap == 0 then
      state.finished, state.message = true, "no speech found"
      log(state.message)
    elseif state.loaded == snap then
      state.finished = true
      state.message = st.language == "en" and "English subtitles ready"
        or "English subtitles ready (translated from " .. lang_name(st.language) .. ")"
      osd(cfg, state.message)
    end
  end
end

function M.describe(state)
  if not state.path then return "No local video is playing." end
  local name = state.path:match("([^\\/]+)$") or state.path
  return name .. "<br>" .. (state.message or "")
end

return M

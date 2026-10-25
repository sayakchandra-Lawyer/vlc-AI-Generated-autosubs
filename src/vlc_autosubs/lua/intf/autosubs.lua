--[[
  AutoSubs interface script: automatic mode.

  Runs in the background for the whole VLC session and adds English
  subtitles to every video you play. Enable it with
    Tools > Preferences > Show settings: All > Interface > Main interfaces:
      tick "Lua interpreter", then under Main interfaces > Lua set
      "Lua interface" to: autosubs
  (the installer does this for you), then restart VLC.
--]]

local core = require("autosubs_core")

vlc.msg.info("[autosubs] automatic mode started")

-- VLC 3 stops the script by making mwait() raise "Interrupted."; newer
-- versions may also offer should_die().
local function should_die()
  return vlc.misc.should_die ~= nil and vlc.misc.should_die()
end

local state = core.new_state()
while not should_die() do
  local ok, err = pcall(core.tick, state, { auto = true })
  if not ok then vlc.msg.err("[autosubs] " .. tostring(err)) end
  if not pcall(vlc.misc.mwait, vlc.misc.mdate() + 2000000) then break end
end
vlc.msg.info("[autosubs] automatic mode stopped")

--[[
  AutoSubs extension: manual mode, from the menu
  View > Auto English Subtitles (VLC on macOS: VLC > Extensions).

  While the window is open, every video you start gets English subtitles,
  and "Generate / Refresh" starts (or retries) the current one and loads
  the newest part of the subtitles. For fully automatic subtitles without
  opening anything, use automatic mode (the autosubs interface script).
--]]

local core, state, dlg, lbl

function descriptor()
  return {
    title = "Auto English Subtitles",
    version = "1.2.0",
    author = "Sayak Chandra",
    shortdesc = "Auto English Subtitles",
    description = "Generates English subtitles for the playing video with "
      .. "Whisper speech translation (French, Russian, Japanese, Czech and "
      .. "~95 more languages).",
    capabilities = { "input-listener" },
  }
end

local function refresh(opts)
  core.tick(state, opts)
  lbl:set_text(core.describe(state))
  dlg:update()
end

function activate()
  core = require("autosubs_core")
  state = core.new_state()
  dlg = vlc.dialog("Auto English Subtitles")
  lbl = dlg:add_label("", 1, 1, 3, 1)
  dlg:add_button("Generate / Refresh", function() refresh({ now = true, force = true }) end, 1, 2, 1, 1)
  dlg:add_button("Close", function() vlc.deactivate() end, 3, 2, 1, 1)
  refresh({ now = true })
  dlg:show()
end

function deactivate()
  if dlg then dlg:delete() end
end

function close()
  vlc.deactivate()
end

function input_changed()
  if core then refresh({ now = true }) end
end

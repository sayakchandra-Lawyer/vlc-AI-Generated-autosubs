# AutoSubs — automatic English subtitles for VLC

Play a video in French, Russian, Japanese, Czech or any of ~99 languages, and
English subtitles show up on their own a few seconds later. They are made on
your own computer with OpenAI's Whisper speech-translation model (through
[faster-whisper](https://github.com/SYSTRAN/faster-whisper)). Nothing is uploaded.

## How it works

VLC's Lua scripting can't read audio, so AutoSubs has two parts:

1. **Lua scripts inside VLC** notice when a video starts, start the helper
   in the background, and load its subtitles into the playing video.
2. **A Python helper** (`vlc_autosubs.py`) runs Whisper with
   `task="translate"`, which turns speech in any supported language straight
   into English text.

Subtitles arrive in parts: the first ~15 seconds come within moments, and
later parts are loaded before playback reaches them. When the whole video is
done, the subtitles are also saved next to it as `<video>.en.srt`, so VLC
loads them instantly next time.

Videos are skipped when they already have English subtitles (an `.en.srt`
file or an English subtitle track), when the audio is English, or when they
are audio-only.

## Install

You need **VLC 3.x** and **Python 3.9 or newer**.
Windows: get Python from python.org and tick "Add python.exe to PATH".

1. **Quit VLC.**
2. In this folder, run:

   ```
   python3 install.py            # Windows: py install.py
   ```

   This copies the scripts into VLC's user folder, creates a private Python
   environment with faster-whisper (about 200 MB download), and turns on
   automatic mode in VLC's settings. A backup of your settings is saved as
   `vlcrc.autosubs-backup`.
3. Start VLC and play a video. The first time, the Whisper model downloads
   (~500 MB for the default `small` model), so the first subtitles take
   longer. To download it during install instead, add `--download-model small`.

Options:

| Option | What it does |
| --- | --- |
| `--model medium` | choose the model (see below) |
| `--manual-only` | don't turn on automatic mode; use the menu extension only |
| `--python /path/to/python` | use an existing Python that has `faster-whisper` installed |
| `--uninstall` | remove AutoSubs and turn automatic mode off |

### Turning automatic mode on by hand

If you'd rather not let the installer edit VLC's settings: Tools → Preferences
→ Show settings: **All** → Interface → Main interfaces → tick **Lua
interpreter**. Then, under Main interfaces → Lua, set **Lua interface** to
`autosubs`. Save and restart VLC.

## Using it

- **Automatic mode** (default): just play videos. Status messages appear
  in the top-right corner of the video.
- **Manual mode**: View → **Auto English Subtitles** (on macOS: VLC →
  Extensions). The window shows progress. **Generate / Refresh** starts or
  retries the current video, even one that was skipped, and loads the newest
  part of its subtitles.

As new parts load, VLC lists them as extra subtitle tracks (Subtitle → Sub
Track). The newest one is selected automatically, and it always contains
everything translated so far.

When you switch to another video, the previous one's work stops so the new
video gets the CPU. That video starts again from scratch the next time you
play it.

## Choosing a model

Edit `autosubs.conf` (see below), or reinstall with `--model`.

| Model | Download | Quality | Notes |
| --- | --- | --- | --- |
| `tiny`, `base` | 75–150 MB | rough | for slow machines |
| `small` | ~500 MB | decent | **default without a GPU** |
| `medium` | ~1.5 GB | good | CPU is fine if your machine is fast enough |
| `large-v3` | ~3 GB | best | **default with an NVIDIA GPU** |

Don't use `turbo` / `large-v3-turbo`: that model wasn't trained to translate
and often answers in the original language. On CPU, `small` usually runs
faster than real time. If subtitles can't keep up with playback, choose a
smaller model.

**NVIDIA GPU:** faster-whisper needs CUDA 12 and cuDNN 9 (see faster-whisper's
README). If the GPU can't be used, AutoSubs falls back to the CPU on its own.

## Settings: `autosubs.conf`

The file lives in AutoSubs' folder (see "Where things are"). Write one
`key=value` per line, then restart VLC.

```
model=auto                # auto | tiny | base | small | medium | large-v3
device=auto               # auto | cpu | cuda
enabled=1                 # 0 = automatic mode off (manual mode still works)
write_sidecar=1           # save <video>.en.srt next to the video
skip_english_audio=1
skip_if_english_subs=1
osd=1                     # on-screen status messages
python=                   # custom Python executable (default: AutoSubs' venv)
```

## Where things are

| | Windows | macOS | Linux |
| --- | --- | --- | --- |
| scripts | `%APPDATA%\vlc\lua\` | `~/Library/Application Support/org.videolan.vlc/lua/` | `~/.local/share/vlc/lua/` |
| AutoSubs | `%APPDATA%\vlc\autosubs\` | `~/Library/Application Support/org.videolan.vlc/autosubs/` | `~/.local/share/vlc/autosubs/` |

Each video gets files in `autosubs/jobs/`: `.status`, `.log` and the `.srt`
parts. You can delete that folder's contents at any time.

## Troubleshooting

- **Nothing happens.** In VLC, open Tools → Messages, set verbosity to 2 and
  look for lines with `autosubs`. If none appear, automatic mode isn't on.
  Check the preferences above, or use manual mode.
- **"error: …" on screen.** Read `autosubs/jobs/<video>.log`.
  `ModuleNotFoundError: faster_whisper` means the helper is using the wrong
  Python; re-run the installer, or set `python=` in `autosubs.conf`.
- **Snap/Flatpak VLC on Linux** is sandboxed and can't start the helper. Use
  your distribution's `vlc` package instead.
- **Only local files** are supported, not streams, DVDs or network URLs.
- **Windows:** paths with characters outside your system's code page (for
  example Japanese file names on an English Windows) may fail, because VLC 3's
  Lua can't pass them to other programs. Rename the file if that happens. A
  console window may also flash briefly when a video starts.

## Uninstall

```
python3 install.py --uninstall
```

The `.en.srt` files saved next to your videos are kept.

## License

AutoSubs is free software under the [MIT License](LICENSE): you may use,
copy, modify and share it, including commercially, as long as the license
notice is kept.

It relies on [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
(MIT), OpenAI's Whisper models (MIT) and [PyAV](https://github.com/PyAV-Org/PyAV)
(BSD). These are downloaded by the installer, not bundled with AutoSubs.

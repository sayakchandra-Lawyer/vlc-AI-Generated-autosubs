# AutoSubs — automatic English subtitles for VLC

[![CI](https://github.com/sayakchandra-Lawyer/vlc-AI-Generated-autosubs/actions/workflows/ci.yml/badge.svg)](https://github.com/sayakchandra-Lawyer/vlc-AI-Generated-autosubs/actions/workflows/ci.yml)

Play a video in French, Russian, Japanese, Czech or any of ~99 languages, and
English subtitles show up on their own a few seconds later. They are made on
your own computer with OpenAI's Whisper speech-translation model (through
[faster-whisper](https://github.com/SYSTRAN/faster-whisper)). It's free, there
are no accounts or API keys, and nothing is uploaded.

- Subtitles arrive in parts while you watch, ahead of playback.
- Finished subtitles are saved next to the video as `<video>.en.srt`, so the
  next playback is instant, and they also work in other players.
- Videos that already have English subtitles or English audio are skipped.

## Install

Pick **one** of the two ways. Both need [VLC](https://www.videolan.org/) 3.x.
Quit VLC before installing.

### Option 1: download (no Python needed)

Get the file for your computer from the
[latest release](https://github.com/sayakchandra-Lawyer/vlc-AI-Generated-autosubs/releases/latest):

| Your computer | Standard | Offline (includes the `small` model) |
| --- | --- | --- |
| Windows 10/11 (64-bit) | `vlc-autosubs-<version>-windows-x64.zip` | `…-windows-x64-offline-small.zip` |
| Mac with Apple Silicon (M1 or newer) | `vlc-autosubs-<version>-macos-arm64.tar.gz` | `…-macos-arm64-offline-small.tar.gz` |
| Linux (64-bit) | `vlc-autosubs-<version>-linux-x64.tar.gz` | `…-linux-x64-offline-small.tar.gz` |

**Standard** (~150 MB) downloads the Whisper model the first time you play
a video. **Offline** (~600 MB) already contains it, which is good for slow
connections or computers that are never online.

Unpack it, then:

- **Windows:** double-click `vlc-autosubs.exe`. If SmartScreen warns about an
  unknown publisher, click *More info → Run anyway* (the app isn't
  code-signed).
- **macOS:** open Terminal in the unpacked folder and run
  ```
  xattr -dr com.apple.quarantine .
  ./vlc-autosubs install
  ```
  The first command is needed because the app isn't notarized by Apple.
- **Linux:** in the unpacked folder, run `./vlc-autosubs install`

The installer copies AutoSubs into VLC's folder, so you can delete the
download afterwards. The `vlc-autosubs` command used below then lives at:

| | Installed command |
| --- | --- |
| Windows | `"%APPDATA%\vlc\autosubs\app\vlc-autosubs.exe"` |
| macOS | `~/"Library/Application Support/org.videolan.vlc/autosubs/app/vlc-autosubs"` |
| Linux | `~/.local/share/vlc/autosubs/app/vlc-autosubs` |

Intel Macs: use Option 2.

### Option 2: install with uv

[uv](https://docs.astral.sh/uv/) installs AutoSubs in its own environment
and fetches a suitable Python if needed, so the Python setup already on your
computer doesn't matter. Git is not needed.

1. Install uv (one time), then open a **new** terminal:
   - Windows (PowerShell):
     `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Quit VLC, then:
   ```
   uv tool install https://github.com/sayakchandra-Lawyer/vlc-AI-Generated-autosubs/archive/refs/heads/main.zip
   vlc-autosubs install
   ```
   If `vlc-autosubs` isn't found, run `uv tool update-shell`, open a new
   terminal and try again.

To update to the latest code, run the first command again with
`--reinstall --refresh` added, then `vlc-autosubs install` again. To install a
specific release instead, use its tag's zip, for example
`https://github.com/sayakchandra-Lawyer/vlc-AI-Generated-autosubs/archive/refs/tags/v1.1.0.zip`.

This is also the way to go for **NVIDIA GPUs**: with CUDA 12 and cuDNN 9
installed, AutoSubs uses the GPU and the more accurate `large-v3` model by
itself. The downloadable builds run on the CPU.

### After installing

Start VLC and play a video. To check that everything is in order, run
(downloads: use the installed command from the table above):

```
vlc-autosubs doctor            # or: vlc-autosubs doctor "some video.mkv"
```

Install options: `--model medium` picks a model, `--manual-only` skips
automatic mode, and `--download-model small` fetches a model right away.
`vlc-autosubs --help` lists all commands.

## Using it

- **Automatic mode** (default): just play videos. Status messages appear in
  the top-right corner of the video.
- **Manual mode**: View → **Auto English Subtitles** (on macOS: VLC →
  Extensions). The window shows progress. **Generate / Refresh** starts or
  retries the current video, even one that was skipped.

As new parts of the subtitles load, VLC lists them as extra subtitle tracks
(Subtitle → Sub Track). The newest one is selected automatically and always
contains everything translated so far.

When you switch to another video, work on the previous one stops so the new
video gets the CPU. The stopped video starts over the next time you play it.

## Choosing a model

| Model | Download | Quality | Notes |
| --- | --- | --- | --- |
| `tiny`, `base` | 75–150 MB | rough | for slow machines |
| `small` | ~500 MB | decent | **default without a GPU**; in the offline builds |
| `medium` | ~1.5 GB | good | CPU is fine if your machine is fast enough |
| `large-v3` | ~3 GB | best | **default with an NVIDIA GPU** |

Change it with `vlc-autosubs install --model medium`, or in `autosubs.conf`.
On a CPU, `small` usually runs faster than real time. If subtitles can't keep
up with playback, choose a smaller model.

**Why only Whisper models?** AutoSubs needs *speech in any language → English
text*, including languages like Japanese and Russian, on an ordinary computer.
- English-only models (`small.en`, distil-whisper, Moonshine, …) and
  `large-v3-turbo` can't translate at all.
- Newer multilingual models either cover far fewer languages (NVIDIA Canary
  and Parakeet, Voxtral), need a GPU, or have licenses that forbid commercial
  use (SeamlessM4T).

So Whisper remains the practical choice here.

## Settings: `autosubs.conf`

The file lives in AutoSubs' folder (see below). Write one `key=value` per
line, then restart VLC.

```
model=auto                # auto | tiny | base | small | medium | large-v3
device=auto               # auto | cpu | cuda
enabled=1                 # 0 = automatic mode off (manual mode still works)
write_sidecar=1           # save <video>.en.srt next to the video
skip_english_audio=1
skip_if_english_subs=1
osd=1                     # on-screen status messages
helper=…                  # set by `vlc-autosubs install`; don't edit
```

## Supported platforms

| Platform | Status |
| --- | --- |
| Linux, VLC 3.0.x from your distribution's packages | tested |
| Windows 10/11 | should work — reports welcome |
| macOS, Apple Silicon | should work — reports welcome |
| macOS, Intel | uv install only |
| Linux Snap/Flatpak VLC | not supported (sandboxed, can't start the helper) |
| VLC 4 (beta) | not tested |

Found a problem, or tried it on a platform listed as untested? Please
[open an issue](https://github.com/sayakchandra-Lawyer/vlc-AI-Generated-autosubs/issues)
and include the output of `vlc-autosubs doctor` and the last lines of the log
file (see Troubleshooting).

## Where things are

| | Windows | macOS | Linux |
| --- | --- | --- | --- |
| scripts | `%APPDATA%\vlc\lua\` | `~/Library/Application Support/org.videolan.vlc/lua/` | `~/.local/share/vlc/lua/` |
| AutoSubs | `%APPDATA%\vlc\autosubs\` | `~/Library/Application Support/org.videolan.vlc/autosubs/` | `~/.local/share/vlc/autosubs/` |

Each video gets files in `autosubs/jobs/`: `.status`, `.log` and the `.srt`
parts. You can delete that folder's contents at any time. Downloaded models
are kept in the Hugging Face cache (`~/.cache/huggingface`).

## Troubleshooting

- **Run `vlc-autosubs doctor` first.** It checks the speech engine, voice
  detection and (given a video) audio decoding.
- **Nothing happens.** In VLC, open Tools → Messages, set verbosity to 2 and
  look for lines with `autosubs`. If none appear, automatic mode isn't on:
  run `vlc-autosubs install` again, or use manual mode.
- **"error: …" on screen.** Read `autosubs/jobs/<video>.log`.
- **"helper not found".** Run `vlc-autosubs install` again. This happens when
  the uv environment was moved or removed.
- **Snap/Flatpak VLC on Linux** is sandboxed and can't start the helper. Use
  your distribution's `vlc` package instead.
- **Only local files** are supported, not streams, DVDs or network URLs.
- **Windows:** paths with characters outside your system's code page (for
  example Japanese file names on an English Windows) may fail, because VLC 3's
  Lua can't pass them to other programs. Rename the file if that happens. A
  black window may flash for a moment when a video starts; that's VLC
  starting the helper.
- **Antivirus warnings (Windows):** programs packaged with PyInstaller, like
  the downloads, are sometimes flagged by mistake. If yours blocks AutoSubs,
  use Option 2, which runs the same code from source.

### Turning automatic mode on by hand

`vlc-autosubs install` does this for you (keeping a backup of VLC's settings
as `vlcrc.autosubs-backup`). To do it yourself: Tools → Preferences → Show
settings: **All** → Interface → Main interfaces → tick **Lua interpreter**.
Then, under Main interfaces → Lua, set **Lua interface** to `autosubs`. Save
and restart VLC.

## Uninstall

```
vlc-autosubs uninstall              # downloads: the installed command from the table above
uv tool uninstall vlc-autosubs      # only if you used Option 2
```

The `.en.srt` files saved next to your videos are kept.

## For developers

AutoSubs is a regular Python package managed with
[uv](https://docs.astral.sh/uv/). Dependencies are pinned in `uv.lock`, and
`.python-version` sets the Python used for development and builds.

```
src/vlc_autosubs/
  cli.py          the `vlc-autosubs` command
  installer.py    copies the Lua scripts into VLC, edits vlcrc
  helper.py       the background job: Whisper → .srt snapshots
  lua/            the VLC side (interface script, extension, shared module)
devtools/         build and release tools (a uv workspace member, so
                  people installing AutoSubs don't get them)
  pyinstaller/    the PyInstaller recipe (vlc-autosubs.spec) and entry scripts
  src/autosubs_devtools/
    build.py      the build pipeline: app folder → docs, model → archive
    buildinfo.py  what a build records (BUILDINFO.txt, requirements.txt)
    release.py    release notes for a tag, smoke tests of builds
    cli.py        the commands below
tests/            pytest suite (uses a stand-in for Whisper, no model needed)
```

| Command | What it does |
| --- | --- |
| `uv sync` | create `.venv` with the app and dev tools |
| `uv run pytest` | run the tests |
| `uv run vlc-autosubs install` | install your working copy into VLC (keep the checkout in place) |
| `uv run autosubs-build` | standalone build for this platform → `dist/` |
| `uv run autosubs-build --bundle-model small` | the same, with a model inside (offline build) |
| `uv run autosubs-reproduce v1.1.0` | rebuild a tagged release from its locked dependencies → `dist/reproduced/` |
| `uv run autosubs-smoke-test dist/*.tar.gz` | unpack builds and check they start, pass `doctor`, and (offline builds) contain their model |
| `uv run autosubs-release-notes v1.1.0` | check a tag matches the version, and print its `CHANGELOG.md` section |

Every build contains `BUILDINFO.txt` (version, commit, Python, platform) and
`requirements.txt` with the exact package versions inside it.

`AUTOSUBS_FAKE=1` replaces Whisper with a stand-in that writes dummy lines,
which is handy for testing the VLC side without downloading a model.

**Releasing:**
1. Set the new version in `src/vlc_autosubs/__init__.py` and
   `src/vlc_autosubs/lua/extensions/autosubs_ext.lua`, and add a section at
   the top of `CHANGELOG.md`. The tests fail if these don't match.
2. Commit and push.
3. Push a tag: `git tag v1.1.0 && git push origin v1.1.0`

GitHub Actions then builds all six downloads, smoke-tests each one, and
publishes the release with the changelog section as its notes. The workflow
only calls the commands above, so every step can also be run locally.

## License

AutoSubs is free software under the [MIT License](LICENSE): you may use,
copy, modify and share it, including commercially, as long as the license
notice is kept.

It relies on [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
(MIT), OpenAI's Whisper models (MIT) and [PyAV](https://github.com/PyAV-Org/PyAV)
(BSD). The offline builds include the Whisper `small` model under its MIT
license.

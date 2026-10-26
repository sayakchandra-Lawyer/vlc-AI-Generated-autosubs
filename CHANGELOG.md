# Changelog

## 1.2.0 — 2026-10-26

- **Choose the translation quality while installing.** The installer asks
  Fast, Better or Best, suggests one for your computer (Best with an NVIDIA
  graphics card, otherwise Fast, the only one that keeps up on a laptop
  processor) and downloads it right away. Press Enter to take the
  suggestion. Scripts and `--model` are never asked.
- `vlc-autosubs doctor` shows which model is set up and whether it's
  downloaded. An interrupted download no longer counts as downloaded, so the
  installer finishes it instead of skipping it.
- The uv install needs Python 3.11 to 3.14, and its command now asks uv for
  Python 3.13: onnxruntime, which the speech recognition needs, has no
  packages for Python 3.15 yet, nor for Intel Macs beyond 3.13. CI tests
  Python 3.11 to 3.14 on Windows, macOS and Linux.

## 1.1.0 — 2026-10-25

- **Ready-made downloads** for Windows, macOS (Apple Silicon) and Linux that
  need no Python: unpack, run `vlc-autosubs install`, done. "Offline" builds
  also include the `small` Whisper model.
- **Install with uv**: `uv tool install https://github.com/sayakchandra-Lawyer/vlc-AI-Generated-autosubs/archive/refs/heads/main.zip`,
  then `vlc-autosubs install`. uv picks a suitable Python by itself, and
  Git isn't needed.
- The code is now a regular Python package (`src/vlc_autosubs`, managed with
  `pyproject.toml` and `uv.lock`) instead of a zip file.
- New commands: `vlc-autosubs doctor` checks that everything works, and
  `vlc-autosubs download-model` fetches a model ahead of time.
- Fixed: on Windows, the helper could crash the first time it downloaded a
  model (its progress bar had no console to write to).
- Upgrading from 1.0 removes its private Python environment (~1 GB).
- For developers: `uv run autosubs-build` makes a standalone build,
  `uv run autosubs-reproduce v1.1.0` rebuilds a release from its locked
  dependencies, and tests run with `uv run pytest` on Windows, macOS and
  Linux in CI. Bug reports have an issue template.
- Upgrading from 1.0: run the new installer; the old `install.py` and its
  private virtualenv are no longer used.

## 1.0.1 — 2026-10-25

- Fixed: "TypeError: open() got an unexpected keyword argument
  'metadata_errors'" with current PyAV (19.x) releases.
- Fixed: a video that failed once kept showing the old error, even after
  updating. Failed videos are now retried once each time they are played.
- The helper's log now starts with its version number.
- Added an MIT license.

## 1.0.0 — 2026-10-25

- First release: automatic mode (Lua interface script), manual mode (VLC
  extension), Whisper speech translation helper and a cross-platform installer.

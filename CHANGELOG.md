# Changelog

## 1.1.0 — 2026-10-25

- **Ready-made downloads** for Windows, macOS (Apple Silicon) and Linux that
  need no Python: unpack, run `vlc-autosubs install`, done. "Offline" builds
  also include the `small` Whisper model.
- **Install with uv**: `uv tool install git+https://github.com/sayakchandra-Lawyer/vlc-AI-Generated-autosubs`,
  then `vlc-autosubs install`. uv picks a suitable Python by itself.
- The code is now a regular Python package (`src/vlc_autosubs`, managed with
  `pyproject.toml` and `uv.lock`) instead of a zip file.
- New commands: `vlc-autosubs doctor` checks that everything works, and
  `vlc-autosubs download-model` fetches a model ahead of time.
- Windows: no more console window while subtitles are being generated.
- For developers: `uv run autosubs-build` makes a standalone build,
  `uv run autosubs-reproduce v1.1.0` rebuilds a release from its locked
  dependencies, and tests run with `uv run pytest`.
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

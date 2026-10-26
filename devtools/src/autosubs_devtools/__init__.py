"""Build and release tools for AutoSubs.

A uv workspace member, so the commands work in a checkout without being
installed for people who only use AutoSubs. Commands (devtools/pyproject.toml):

  autosubs-build          standalone build for this platform -> dist/
  autosubs-reproduce      rebuild a tagged release from its locked dependencies
  autosubs-smoke-test     unpack a build and check that it runs
  autosubs-release-notes  check a tag against the version; print its changelog

Modules: buildinfo (what a build records about itself), build (the build
pipeline), release (checks used when publishing), cli (the commands).
"""

import os

# The repository: this file is devtools/src/autosubs_devtools/__init__.py.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SPEC = os.path.join(ROOT, "devtools", "pyinstaller", "vlc-autosubs.spec")

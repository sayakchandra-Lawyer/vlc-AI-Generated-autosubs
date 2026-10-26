# PyInstaller recipe for the standalone AutoSubs: one folder with two
# programs, `vlc-autosubs` (the command) and `vlc-autosubs-helper` (what VLC
# starts in the background). `uv run autosubs-build` runs this and then adds
# the docs, an optional model and the archive; on its own,
# `uv run pyinstaller devtools/pyinstaller/vlc-autosubs.spec` makes just the folder.
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files

datas, binaries, hiddenimports = [], [], []
for pkg in ("faster_whisper", "ctranslate2", "av", "onnxruntime", "tokenizers"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
datas += collect_data_files("vlc_autosubs")  # the Lua scripts


def entry(name):
    return os.path.join(SPECPATH, name + ".py")


a = Analysis([entry("cli_entry"), entry("helper_entry")], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, excludes=["tkinter", "pytest", "PyInstaller"])
pyz = PYZ(a.pure)


# Both programs share one analysis; each must run only its own entry script.
def without(name):
    return [s for s in a.scripts if s[0] != name]


cli = EXE(pyz, without("helper_entry"), [], exclude_binaries=True,
          name="vlc-autosubs", console=True)
# Windowless on Windows, so no console pops up while VLC runs it.
helper = EXE(pyz, without("cli_entry"), [], exclude_binaries=True,
             name="vlc-autosubs-helper", console=sys.platform != "win32")
COLLECT(cli, helper, a.binaries, a.datas, name="vlc-autosubs")

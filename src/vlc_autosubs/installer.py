"""Install AutoSubs' Lua scripts into VLC and point them at the helper."""

import os
import platform
import re
import shutil
import sys
from importlib import resources

SYSTEM = platform.system()
FROZEN = getattr(sys, "frozen", False)

LUA_FILES = [
    "modules/autosubs_core.lua",
    "intf/autosubs.lua",
    "extensions/autosubs_ext.lua",
]


class InstallError(Exception):
    pass


# --------------------------------------------------------------------------
# locations
# --------------------------------------------------------------------------

def vlc_user_dir():
    home = os.path.expanduser("~")
    if SYSTEM == "Windows":
        return os.path.join(os.environ["APPDATA"], "vlc")
    if SYSTEM == "Darwin":
        return os.path.join(home, "Library", "Application Support", "org.videolan.vlc")
    data = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    return os.path.join(data, "vlc")


def vlcrc_path():
    home = os.path.expanduser("~")
    if SYSTEM == "Windows":
        return os.path.join(os.environ["APPDATA"], "vlc", "vlcrc")
    if SYSTEM == "Darwin":
        return os.path.join(home, "Library", "Preferences", "org.videolan.vlc", "vlcrc")
    conf = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return os.path.join(conf, "vlc", "vlcrc")


def autosubs_root():
    return os.path.join(vlc_user_dir(), "autosubs")


def conf_path():
    return os.path.join(autosubs_root(), "autosubs.conf")


def _exe(name):
    return name + ".exe" if SYSTEM == "Windows" else name


def find_helper():
    """The command VLC should start, for the way AutoSubs is installed now."""
    if FROZEN:
        # Prebuilt bundle: it is copied into AutoSubs' folder by install().
        return os.path.join(autosubs_root(), "app", _exe("vlc-autosubs-helper"))
    # pip/uv install: the gui-script sits next to this environment's python.
    # (Don't resolve symlinks: venv pythons often point outside the venv.)
    helper = os.path.join(os.path.dirname(sys.executable), _exe("vlc-autosubs-helper"))
    if not os.path.exists(helper):
        raise InstallError(
            f"{helper} not found. Install AutoSubs as a package first, e.g.\n"
            "  uv tool install git+https://github.com/sayakchandra-Lawyer/vlc-AI-Generated-autosubs")
    return helper


# --------------------------------------------------------------------------
# settings
# --------------------------------------------------------------------------

def read_conf():
    settings = {}
    try:
        with open(conf_path(), encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    settings[k.strip()] = v.strip()
    except OSError:
        pass
    return settings


def write_conf(settings):
    os.makedirs(autosubs_root(), exist_ok=True)
    with open(conf_path(), "w", encoding="utf-8") as f:
        f.write("# AutoSubs settings — see README.md. Restart VLC after editing.\n")
        for k, v in settings.items():
            f.write(f"{k}={v}\n")


# --------------------------------------------------------------------------
# vlcrc editing: extraintf (in [core]) gets "luaintf", lua-intf (in [lua])
# becomes "autosubs".
# --------------------------------------------------------------------------

def _set_option(lines, section, key, transform):
    pat = re.compile(r"^#?\s*" + re.escape(key) + r"\s*=(.*)$")
    for i, line in enumerate(lines):
        m = pat.match(line.rstrip("\r\n"))
        if m:
            current = "" if line.startswith("#") else m.group(1).strip()
            new = transform(current)
            lines[i] = f"{key}={new}\n" if new is not None else f"#{key}=\n"
            return
    new = transform("")
    if new is None:
        return
    header = f"[{section}]"
    for i, line in enumerate(lines):
        if line.strip().startswith(header):
            lines.insert(i + 1, f"{key}={new}\n")
            return
    lines.append(f"\n{header}\n{key}={new}\n")


def edit_vlcrc(enable, path=None):
    path = path or vlcrc_path()
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="surrogateescape") as f:
            lines = f.readlines()
        backup = path + ".autosubs-backup"
        if enable and not os.path.exists(backup):
            shutil.copy2(path, backup)
    elif not enable:
        return

    def extraintf(cur):
        mods = [m for m in cur.split(":") if m]
        if enable and "luaintf" not in mods:
            mods.append("luaintf")
        if not enable:
            mods = [m for m in mods if m != "luaintf"]
        return ":".join(mods) or None

    def lua_intf(cur):
        if enable:
            return "autosubs"
        return None if cur == "autosubs" else (cur or None)

    _set_option(lines, "core", "extraintf", extraintf)
    _set_option(lines, "lua", "lua-intf", lua_intf)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.writelines(lines)
    print(("enabled" if enable else "disabled") + f" automatic mode in {path}")


# --------------------------------------------------------------------------

def _install_bundle():
    """Copy the prebuilt app into AutoSubs' folder so the download can go."""
    src = os.path.dirname(os.path.abspath(sys.executable))
    dst = os.path.join(autosubs_root(), "app")
    if os.path.normcase(src) == os.path.normcase(dst):
        return
    print(f"copying AutoSubs to {dst} …")
    try:
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    except OSError as e:
        raise InstallError(f"could not copy to {dst}: {e}\n"
                           "Quit VLC (it may be running the helper) and try again.")


def install(model=None, manual_only=False):
    user_dir = vlc_user_dir()
    lua = resources.files("vlc_autosubs") / "lua"
    for rel in LUA_FILES:
        dst = os.path.join(user_dir, "lua", *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write((lua / rel).read_bytes())
        print(f"installed {dst}")
    os.makedirs(os.path.join(autosubs_root(), "jobs"), exist_ok=True)

    if FROZEN:
        _install_bundle()
    old_venv = os.path.join(autosubs_root(), "venv")  # made by AutoSubs 1.0
    if os.path.isdir(old_venv):
        shutil.rmtree(old_venv, ignore_errors=True)
        print(f"removed the old Python environment {old_venv}")
    settings = read_conf()
    settings.pop("python", None)  # used by AutoSubs 1.0
    settings["helper"] = find_helper()
    if model:
        settings["model"] = model
    write_conf(settings)
    print(f"helper: {settings['helper']}")

    if not manual_only:
        edit_vlcrc(True)
    print("\nDone. Start VLC and play a video" +
          ("." if manual_only else " — English subtitles appear automatically.") +
          "\nManual mode: View > Auto English Subtitles (macOS: VLC > Extensions).")


def uninstall():
    user_dir = vlc_user_dir()
    for rel in LUA_FILES:
        path = os.path.join(user_dir, "lua", *rel.split("/"))
        if os.path.exists(path):
            os.remove(path)
            print(f"removed {path}")
    root = autosubs_root()
    if os.path.isdir(root):
        shutil.rmtree(root, ignore_errors=True)
        if os.path.exists(root):
            print(f"could not remove all of {root}; delete it by hand after quitting VLC")
        else:
            print(f"removed {root}")
    edit_vlcrc(False)
    print("Python packages are not removed; with uv: uv tool uninstall vlc-autosubs")

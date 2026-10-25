import os
import re

from vlc_autosubs import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_lua_extension_version_matches():
    ext = read("src", "vlc_autosubs", "lua", "extensions", "autosubs_ext.lua")
    assert f'version = "{__version__}"' in ext


def test_changelog_has_this_version_first():
    first = re.search(r"^## (\S+)", read("CHANGELOG.md"), re.M).group(1)
    assert first == __version__


def test_users_only_get_the_vlc_autosubs_commands():
    tomllib = __import__("pytest").importorskip("tomllib")
    project = tomllib.loads(read("pyproject.toml"))["project"]
    assert set(project["scripts"]) == {"vlc-autosubs"}
    assert set(project["gui-scripts"]) == {"vlc-autosubs-helper"}

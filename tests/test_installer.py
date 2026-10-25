import os

from vlc_autosubs import installer


def test_install_and_uninstall(fake_home):
    installer.install(model="medium")
    user_dir = installer.vlc_user_dir()
    assert user_dir.startswith(str(fake_home))
    for rel in installer.LUA_FILES:
        assert os.path.exists(os.path.join(user_dir, "lua", *rel.split("/")))
    conf = installer.read_conf()
    assert conf["model"] == "medium"
    assert os.path.exists(conf["helper"])
    with open(installer.vlcrc_path(), encoding="utf-8") as f:
        rc = f.read()
    assert "extraintf=luaintf" in rc and "lua-intf=autosubs" in rc

    installer.uninstall()
    assert not os.path.exists(installer.autosubs_root())
    for rel in installer.LUA_FILES:
        assert not os.path.exists(os.path.join(user_dir, "lua", *rel.split("/")))
    with open(installer.vlcrc_path(), encoding="utf-8") as f:
        rc = f.read()
    assert "luaintf" not in rc and "lua-intf=autosubs" not in rc


def test_vlcrc_keeps_other_interfaces(tmp_path):
    rc = tmp_path / "vlcrc"
    rc.write_text("[core]\nextraintf=http\n[lua]\n#lua-intf=dummy\n", encoding="utf-8")
    installer.edit_vlcrc(True, str(rc))
    assert "extraintf=http:luaintf" in rc.read_text(encoding="utf-8")
    installer.edit_vlcrc(False, str(rc))
    text = rc.read_text(encoding="utf-8")
    assert "extraintf=http\n" in text and "lua-intf=autosubs" not in text


def test_upgrade_from_1_0_drops_old_python_setting(fake_home):
    os.makedirs(os.path.join(installer.autosubs_root(), "venv", "bin"))
    with open(installer.conf_path(), "w", encoding="utf-8") as f:
        f.write("python=/old/venv/bin/python\nmodel=small\n")
    installer.install(manual_only=True)
    conf = installer.read_conf()
    assert "python" not in conf and conf["model"] == "small" and "helper" in conf
    assert not os.path.exists(os.path.join(installer.autosubs_root(), "venv"))

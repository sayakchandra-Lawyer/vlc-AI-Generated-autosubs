import os
import stat
import sys
import tarfile

import pytest

from autosubs_devtools import build, buildinfo, release
from vlc_autosubs import __version__

POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="uses a script as a stand-in program")


@pytest.mark.parametrize("system, machine, tag", [
    ("Windows", "AMD64", "windows-x64"),
    ("Darwin", "arm64", "macos-arm64"),
    ("Linux", "x86_64", "linux-x64"),
    ("Linux", "aarch64", "linux-arm64"),
])
def test_platform_tag(system, machine, tag):
    assert buildinfo.platform_tag(system, machine) == tag


def test_archive_names_and_formats():
    assert build.archive_name("windows-x64") == f"vlc-autosubs-{__version__}-windows-x64"
    assert build.archive_name("linux-x64", "small") == \
        f"vlc-autosubs-{__version__}-linux-x64-offline-small"
    assert build.archive_format("Windows") == "zip"
    assert build.archive_format("Darwin") == build.archive_format("Linux") == "tar.gz"


def test_requirements_pin_the_app_but_not_dev_tools():
    reqs = buildinfo.runtime_requirements()
    names = {r.split("==")[0] for r in reqs}
    assert "faster-whisper" in names and "ctranslate2" in names
    assert not names & {"pytest", "pyinstaller", "autosubs-devtools", "vlc-autosubs"}
    assert all("==" in r for r in reqs)


def test_buildinfo_says_how_to_reproduce():
    text = buildinfo.buildinfo_txt("linux-x64", "small")
    assert f"AutoSubs {__version__}\n" in text
    assert f"reproduce: uv run autosubs-reproduce v{__version__} --bundle-model small" in text


def test_quickstart_names_version_and_platform():
    text = build.quickstart_txt("macos-arm64")
    assert text.startswith(f"AutoSubs {__version__} for macos-arm64\n")


CHANGELOG = """# Changelog

## 2.0.0 — 2027-01-01

- Big change.

## 1.9.0

- Older change.
"""


def test_changelog_section():
    assert release.changelog_section(CHANGELOG, "2.0.0") == "- Big change.\n"
    assert release.changelog_section(CHANGELOG, "1.9.0") == "- Older change.\n"
    assert release.changelog_section(CHANGELOG, "2.0") is None


def test_release_notes_check_the_tag():
    assert release.release_notes(f"v{__version__}").strip()
    with pytest.raises(release.ReleaseError, match="doesn't match"):
        release.release_notes("v0.0.1")


@pytest.mark.parametrize("fmt", ["zip", "tar.gz"])
def test_make_archive_round_trip(tmp_path, fmt):
    app = tmp_path / "app"
    (app / "sub").mkdir(parents=True)
    (app / "sub" / "data.txt").write_text("hi", encoding="utf-8")
    archive = build.make_archive(str(app), str(tmp_path / f"out.{fmt}"), "top", fmt)
    top = release._extract(archive, str(tmp_path / "unpacked"))
    assert os.path.basename(top) == "top"
    assert (tmp_path / "unpacked" / "top" / "sub" / "data.txt").read_text(encoding="utf-8") == "hi"


def _fake_build(tmp_path, name, doctor_output="[ok] model: small (automatic choice): downloaded",
                doctor_exit=0):
    """A build archive whose programs are small scripts."""
    app = tmp_path / "app"
    app.mkdir()
    script = (f"#!{sys.executable}\n"
              "import sys\n"
              f"if sys.argv[1:] == ['--version']: print('AutoSubs {__version__}')\n"
              f"else: print({doctor_output!r}); sys.exit({doctor_exit})\n")
    for program in ("vlc-autosubs", "vlc-autosubs-helper"):
        path = app / program
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return build.make_archive(str(app), str(tmp_path / name), f"vlc-autosubs-{__version__}",
                              "tar.gz")


@POSIX_ONLY
def test_smoke_test_passes_a_working_build(tmp_path):
    archive = _fake_build(tmp_path, "vlc-autosubs-x-linux-x64.tar.gz")
    assert "[ok]" in release.smoke_test(archive)


@POSIX_ONLY
def test_smoke_test_catches_a_failing_doctor(tmp_path):
    archive = _fake_build(tmp_path, "vlc-autosubs-x-linux-x64.tar.gz",
                          doctor_output="[FAIL] speech engine", doctor_exit=1)
    with pytest.raises(release.ReleaseError, match="doctor"):
        release.smoke_test(archive)


@POSIX_ONLY
def test_smoke_test_checks_the_offline_model(tmp_path):
    archive = _fake_build(tmp_path, "vlc-autosubs-x-linux-x64-offline-small.tar.gz")
    with pytest.raises(release.ReleaseError, match="small model"):
        release.smoke_test(archive)
    (tmp_path / "app").rename(tmp_path / "old-app")
    included = _fake_build(
        tmp_path, "vlc-autosubs-x-linux-x64-offline-small.tar.gz",
        doctor_output="[ok] model: small (automatic choice): included in this download")
    assert "included" in release.smoke_test(included)


@POSIX_ONLY
def test_smoke_test_catches_lost_executable_bits(tmp_path):
    archive = _fake_build(tmp_path, "vlc-autosubs-x-linux-x64.tar.gz")
    broken = str(tmp_path / "broken.tar.gz")
    with tarfile.open(archive) as src, tarfile.open(broken, "w:gz") as dst:
        for member in src.getmembers():
            if member.isfile():
                member.mode &= ~0o111
            dst.addfile(member, src.extractfile(member) if member.isfile() else None)
    with pytest.raises(release.ReleaseError, match="isn't executable"):
        release.smoke_test(broken)

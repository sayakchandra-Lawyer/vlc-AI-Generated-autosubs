"""Checks used when publishing: release notes for a tag, and smoke tests."""

import os
import re
import stat
import subprocess
import tarfile
import tempfile
import zipfile

from autosubs_devtools import ROOT
from vlc_autosubs import __version__


class ReleaseError(Exception):
    pass


def changelog_section(changelog, version):
    """The body of the `## <version> …` section of a changelog, or None."""
    match = re.search(rf"^## {re.escape(version)}(?:[ \t][^\n]*)?\n(.*?)(?=^## |\Z)",
                      changelog, re.M | re.S)
    return match.group(1).strip() + "\n" if match else None


def release_notes(tag):
    """Check that `tag` is this version's tag; return its CHANGELOG.md section."""
    if tag != f"v{__version__}":
        raise ReleaseError(f"tag {tag} doesn't match the version in the code "
                           f"({__version__}); expected v{__version__}")
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
        notes = changelog_section(f.read(), __version__)
    if not notes or not notes.strip():
        raise ReleaseError(f"CHANGELOG.md has no section for {__version__}")
    return notes


def _extract(archive, dest):
    """Unpack a build archive into `dest`; returns the folder inside it."""
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
            names = z.namelist()
    else:
        with tarfile.open(archive) as t:
            names = t.getnames()
            try:
                t.extractall(dest, filter="data")
            except TypeError:  # Python without extraction filters
                t.extractall(dest)
    tops = {n.replace("\\", "/").split("/")[0] for n in names}
    if len(tops) != 1:
        raise ReleaseError(f"{archive} should hold exactly one folder, found {sorted(tops)}")
    return os.path.join(dest, tops.pop())


def _run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)
    output = proc.stdout + proc.stderr
    if proc.returncode != 0:
        raise ReleaseError(f"`{' '.join(cmd[1:])}` failed ({proc.returncode}):\n{output}")
    return output


def smoke_test(archive):
    """Unpack a build and check its programs start and the speech stack works.
    Returns the output of `vlc-autosubs doctor`."""
    name = os.path.basename(archive)
    with tempfile.TemporaryDirectory() as tmp:
        app = _extract(os.path.abspath(archive), tmp)
        suffix = ".exe" if os.name == "nt" else ""
        exe = os.path.join(app, "vlc-autosubs" + suffix)
        for program in (exe, os.path.join(app, "vlc-autosubs-helper" + suffix)):
            if not os.path.isfile(program):
                raise ReleaseError(f"{name} has no {os.path.basename(program)}")
            if os.name != "nt" and not os.stat(program).st_mode & stat.S_IXUSR:
                raise ReleaseError(f"{os.path.basename(program)} in {name} isn't executable")

        version = _run([exe, "--version"]).strip()
        if version != f"AutoSubs {__version__}":
            raise ReleaseError(f"{name} reports {version!r}, expected 'AutoSubs {__version__}'")
        doctor = _run([exe, "doctor"])
        offline = re.search(r"-offline-(.+?)\.(?:zip|tar\.gz)$", name)
        if offline and f"bundled: {offline.group(1)}" not in doctor:
            raise ReleaseError(f"{name} should bundle the {offline.group(1)} model:\n{doctor}")
        return doctor

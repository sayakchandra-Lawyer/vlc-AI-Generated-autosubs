"""What a build records about itself: BUILDINFO.txt and requirements.txt."""

import datetime
import platform
import subprocess
import sys
from importlib import metadata

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from autosubs_devtools import ROOT
from vlc_autosubs import __version__

_SYSTEMS = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}
_ARCHES = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}


def platform_tag(system=None, machine=None):
    """e.g. windows-x64, macos-arm64, linux-x64 (defaults: this computer)."""
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    return f"{_SYSTEMS.get(system, system.lower())}-{_ARCHES.get(machine, machine)}"


def git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        return out + (" (with uncommitted changes)" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown (not a git checkout)"


def runtime_requirements():
    """Exact versions of everything the app needs (like `pip freeze`, minus dev tools)."""
    pinned, todo = {}, ["vlc-autosubs"]
    while todo:
        name = canonicalize_name(todo.pop())
        if name in pinned:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        pinned[name] = dist.version
        for req in dist.requires or []:
            r = Requirement(req)
            if r.marker is None or r.marker.evaluate({"extra": ""}):
                todo.append(r.name)
    pinned.pop("vlc-autosubs", None)
    return [f"{n}=={v}" for n, v in sorted(pinned.items())]


def requirements_txt():
    return "# Exact package versions in this build\n" + "\n".join(runtime_requirements()) + "\n"


def buildinfo_txt(tag, bundle_model=None):
    reproduce = f"uv run autosubs-reproduce v{__version__}"
    if bundle_model:
        reproduce += f" --bundle-model {bundle_model}"
    return (f"AutoSubs {__version__}\n"
            f"platform: {tag}\n"
            f"model: {bundle_model or 'none bundled (downloaded on first use)'}\n"
            f"python: {sys.version.split()[0]}\n"
            f"commit: {git_commit()}\n"
            f"built: {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M UTC}\n"
            f"reproduce: {reproduce}\n")

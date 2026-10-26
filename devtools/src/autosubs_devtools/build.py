"""The build pipeline: PyInstaller app folder → docs and optional model → archive.

Builds are made for the platform they run on; CI builds the others
(.github/workflows/release.yml).
"""

import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from importlib import resources

from autosubs_devtools import ROOT, SPEC
from autosubs_devtools.buildinfo import buildinfo_txt, platform_tag, requirements_txt
from vlc_autosubs import __version__


def archive_name(tag, bundle_model=None):
    """File name without extension, e.g. vlc-autosubs-1.1.0-windows-x64-offline-small."""
    return f"vlc-autosubs-{__version__}-{tag}" + (f"-offline-{bundle_model}" if bundle_model else "")


def archive_format(system=None):
    # zip for Windows; tar keeps the executable bits zip extractors often drop
    return "zip" if (system or platform.system()) == "Windows" else "tar.gz"


def run_pyinstaller(work_dir):
    """Build the app folder from the spec; returns its path."""
    import PyInstaller.__main__

    dist = os.path.join(work_dir, "dist")
    PyInstaller.__main__.run([SPEC, "--noconfirm", "--clean",
                              "--distpath", dist, "--workpath", os.path.join(work_dir, "pyi")])
    return os.path.join(dist, "vlc-autosubs")


def add_model(app, model):
    """Put a Whisper model inside the app, where the helper looks for it."""
    from vlc_autosubs.helper import download_model

    print(f"bundling model '{model}'…")
    model_dir = os.path.join(app, "models", model)
    download_model(model, output_dir=model_dir)
    # huggingface_hub leaves download bookkeeping here; not needed to run
    shutil.rmtree(os.path.join(model_dir, ".cache"), ignore_errors=True)


def quickstart_txt(tag):
    template = resources.files("autosubs_devtools").joinpath("quickstart.txt")
    return template.read_text(encoding="utf-8").format(version=__version__, platform=tag)


def add_docs(app, tag, bundle_model=None):
    """README.txt, BUILDINFO.txt, requirements.txt and LICENSE.txt next to the programs."""
    files = {
        "README.txt": quickstart_txt(tag),
        "BUILDINFO.txt": buildinfo_txt(tag, bundle_model),
        "requirements.txt": requirements_txt(),
    }
    for name, text in files.items():
        with open(os.path.join(app, name), "w", encoding="utf-8") as f:
            f.write(text)
    shutil.copy2(os.path.join(ROOT, "LICENSE"), os.path.join(app, "LICENSE.txt"))


def make_archive(app, path, top, fmt):
    """Pack the folder `app` as `path`, with everything inside a folder `top`."""
    if fmt == "zip":
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for root, _dirs, files in os.walk(app):
                for fn in files:
                    full = os.path.join(root, fn)
                    z.write(full, os.path.join(top, os.path.relpath(full, app)))
    else:
        with tarfile.open(path, "w:gz") as t:
            t.add(app, arcname=top)
    return path


def build(bundle_model=None, out_dir=None):
    out_dir = os.path.abspath(out_dir or os.path.join(ROOT, "dist"))
    tag = platform_tag()

    app = run_pyinstaller(os.path.join(ROOT, "build"))
    if bundle_model:
        add_model(app, bundle_model)
    add_docs(app, tag, bundle_model)

    os.makedirs(out_dir, exist_ok=True)
    fmt = archive_format()
    archive = make_archive(app, os.path.join(out_dir, f"{archive_name(tag, bundle_model)}.{fmt}"),
                           top=f"vlc-autosubs-{__version__}", fmt=fmt)
    print(f"\nbuilt {archive} ({os.path.getsize(archive) / 1e6:.0f} MB)")
    return archive


def reproduce(tag, bundle_model=None):
    """Rebuild release `tag` from its own checkout and locked dependencies."""
    known = subprocess.run(["git", "rev-parse", "--verify", "--quiet", tag + "^{commit}"],
                           cwd=ROOT, capture_output=True)
    if known.returncode != 0:
        sys.exit(f"tag {tag} not found; fetch the tags first: git fetch --tags")
    tree = os.path.join(ROOT, "build", "reproduce-" + tag)
    if not os.path.exists(tree):
        subprocess.run(["git", "worktree", "add", "--detach", tree, tag], cwd=ROOT, check=True)
    cmd = ["uv", "run", "--locked", "--directory", tree, "autosubs-build",
           "--out", os.path.join(ROOT, "dist", "reproduced")]
    if bundle_model:
        cmd += ["--bundle-model", bundle_model]
    subprocess.run(cmd, check=True)

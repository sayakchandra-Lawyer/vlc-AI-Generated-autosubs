"""The commands listed in devtools/pyproject.toml."""

import argparse
import sys

from autosubs_devtools import build, release


def build_main():
    ap = argparse.ArgumentParser(prog="autosubs-build",
                                 description="Build a standalone AutoSubs for this platform.")
    ap.add_argument("--bundle-model", metavar="MODEL",
                    help="include a Whisper model for offline use (e.g. small)")
    ap.add_argument("--out", help="output folder (default: dist/)")
    args = ap.parse_args()
    build.build(args.bundle_model, args.out)


def reproduce_main():
    ap = argparse.ArgumentParser(
        prog="autosubs-reproduce",
        description="Rebuild a tagged release from its exact locked dependencies.")
    ap.add_argument("tag", help="release tag, e.g. v1.1.0")
    ap.add_argument("--bundle-model", metavar="MODEL")
    args = ap.parse_args()
    build.reproduce(args.tag, args.bundle_model)


def smoke_test_main():
    ap = argparse.ArgumentParser(
        prog="autosubs-smoke-test",
        description="Unpack builds and check that their programs start and work.")
    ap.add_argument("archives", nargs="+", metavar="ARCHIVE", help="e.g. dist/*.tar.gz")
    args = ap.parse_args()
    failed = False
    for archive in args.archives:
        try:
            print(release.smoke_test(archive), end="")
            print(f"ok: {archive}")
        except release.ReleaseError as e:
            print(f"FAILED: {archive}: {e}", file=sys.stderr)
            failed = True
    sys.exit(1 if failed else 0)


def release_notes_main():
    ap = argparse.ArgumentParser(
        prog="autosubs-release-notes",
        description="Check that a tag matches the version, and print its CHANGELOG.md section.")
    ap.add_argument("tag", help="release tag, e.g. v1.1.0")
    ap.add_argument("--output", metavar="FILE", help="write the notes here instead of printing")
    args = ap.parse_args()
    try:
        notes = release.release_notes(args.tag)
    except release.ReleaseError as e:
        sys.exit(f"error: {e}")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(notes)
    else:
        print(notes, end="")

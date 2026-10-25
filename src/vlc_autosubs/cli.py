"""The `vlc-autosubs` command."""

import argparse
import sys

from vlc_autosubs import __version__, helper, installer

MODELS = ["auto", "tiny", "base", "small", "medium", "large-v3"]


def _pause_if_double_clicked(argv):
    # Double-clicking the Windows build opens a console that closes as soon
    # as we exit; keep it open so people can read what happened.
    if installer.FROZEN and installer.SYSTEM == "Windows" and not argv:
        input("\nPress Enter to close this window…")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(
        prog="vlc-autosubs",
        description="Automatic English subtitles for VLC (Whisper speech translation).")
    ap.add_argument("--version", action="version", version=f"AutoSubs {__version__}")
    sub = ap.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("install", help="install into VLC and turn on automatic mode")
    p.add_argument("--model", choices=MODELS, help="Whisper model (default: auto)")
    p.add_argument("--manual-only", action="store_true",
                   help="don't turn on automatic mode, only the menu extension")
    p.add_argument("--download-model", metavar="MODEL", choices=MODELS[1:],
                   help="download a model now instead of on first use")

    sub.add_parser("uninstall", help="remove AutoSubs from VLC")

    p = sub.add_parser("doctor", help="check that everything works")
    p.add_argument("media", nargs="?", help="optionally, a video to test audio decoding on")

    p = sub.add_parser("download-model", help="download a Whisper model ahead of time")
    p.add_argument("model", choices=MODELS[1:])

    p = sub.add_parser("run-job", help=argparse.SUPPRESS)
    p.add_argument("job")

    # Running the prebuilt app without arguments (double-click) installs it.
    args = ap.parse_args(argv or (["install"] if installer.FROZEN else ["--help"]))
    try:
        if args.command == "install":
            installer.install(model=args.model, manual_only=args.manual_only)
            if args.download_model:
                print(f"downloading model '{args.download_model}'…")
                print("saved to", helper.download_model(args.download_model))
        elif args.command == "uninstall":
            installer.uninstall()
        elif args.command == "doctor":
            ok = True
            print(f"AutoSubs {__version__}, Python {sys.version.split()[0]}")
            print(f"VLC folder: {installer.vlc_user_dir()}")
            print(f"helper: {installer.read_conf().get('helper', '(not installed)')}")
            for name, passed, detail in helper.doctor(args.media):
                ok &= passed
                print(f"[{'ok' if passed else 'FAIL'}] {name}: {detail}")
            if not ok:
                sys.exit(1)
        elif args.command == "download-model":
            print("saved to", helper.download_model(args.model))
        elif args.command == "run-job":
            helper.main([args.job])
    except installer.InstallError as e:
        print(f"error: {e}", file=sys.stderr)
        _pause_if_double_clicked(argv)
        sys.exit(1)
    _pause_if_double_clicked(argv)

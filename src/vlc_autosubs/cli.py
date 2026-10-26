"""The `vlc-autosubs` command."""

import argparse
import sys
import traceback

from vlc_autosubs import __version__, helper, installer, models

MODELS = ["auto", "tiny", "base", "small", "medium", "large-v3"]


def _pause_if_double_clicked(argv):
    # Double-clicking the Windows build opens a console that closes as soon
    # as we exit; keep it open so people can read what happened.
    if installer.FROZEN and installer.SYSTEM == "Windows" and not argv:
        input("\nPress Enter to close this window…")


def _interactive():
    """Someone at a terminal who can answer questions."""
    return all(stream is not None and stream.isatty() for stream in (sys.stdin, sys.stdout))


def _download(model, optional=False):
    """Download a model. If `optional`, a failed or interrupted download is
    fine: the helper fetches the model when a video is first played."""
    print(f"\ndownloading Whisper model '{model}' ({models.SIZES.get(model, '?')}); "
          "this can take a while…")
    try:
        print(f"done, saved to {helper.download_model(model)}")
    except (Exception, KeyboardInterrupt) as e:
        if not optional:
            raise
        reason = "stopped" if isinstance(e, KeyboardInterrupt) else f"failed ({e})"
        print(f"\nThe download {reason}. That's OK: AutoSubs will download the model "
              "the first time you play a video.")


def _install(args):
    model, asked = args.model, False
    if model is None and _interactive():
        model, asked = models.ask(current=installer.read_conf().get("model")), True
    installer.install(model=model, manual_only=args.manual_only)
    if args.download_model:
        _download(args.download_model)
    elif asked and not models.is_downloaded(model):
        _download(model, optional=True)
    print(installer.finish_message(args.manual_only))
    if asked and models.slow_on_this_computer(model):
        print("\nTip: on this computer the subtitles may fall behind the video at first. "
              "Pause the video\nfor a few minutes to let them get ahead. Once a video is "
              "done, its subtitles are saved\nand appear instantly every time after that.")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(
        prog="vlc-autosubs",
        description="Automatic English subtitles for VLC (Whisper speech translation).")
    ap.add_argument("--version", action="version", version=f"AutoSubs {__version__}")
    sub = ap.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("install", help="install into VLC and turn on automatic mode")
    p.add_argument("--model", choices=MODELS,
                   help="Whisper model; without it, you're asked (default when not asked: auto)")
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
            _install(args)
        elif args.command == "uninstall":
            installer.uninstall()
        elif args.command == "doctor":
            ok = True
            print(f"AutoSubs {__version__}, Python {sys.version.split()[0]}")
            print(f"VLC folder: {installer.vlc_user_dir()}")
            print(f"helper: {installer.read_conf().get('helper', '(not installed)')}")
            for name, passed, detail in helper.doctor(args.media,
                                                      installer.read_conf().get("model")):
                ok &= passed
                print(f"[{'ok' if passed else 'FAIL'}] {name}: {detail}")
            if not ok:
                sys.exit(1)
        elif args.command == "download-model":
            _download(args.model)
        elif args.command == "run-job":
            helper.main([args.job])
    except installer.InstallError as e:
        print(f"error: {e}", file=sys.stderr)
        _pause_if_double_clicked(argv)
        sys.exit(1)
    except Exception:
        # Keep a double-clicked window open long enough to read what broke.
        if not (installer.FROZEN and not argv):
            raise
        traceback.print_exc()
        _pause_if_double_clicked(argv)
        sys.exit(1)
    _pause_if_double_clicked(argv)

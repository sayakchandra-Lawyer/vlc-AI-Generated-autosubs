"""The Whisper models people choose between, and the installer's question."""

import sys

from vlc_autosubs import helper

SIZES = {"tiny": "75 MB", "base": "145 MB", "small": "480 MB",
         "medium": "1.5 GB", "large-v3": "3 GB"}

# What the installer offers, in plain words. tiny and base stay available
# through `vlc-autosubs install --model`, but aren't worth a newcomer's time.
CHOICES = [
    ("small", "Fast", "decent translations; keeps up with the video on most computers"),
    ("medium", "Better", "more accurate; without an NVIDIA graphics card it's\n"
                         "usually slower than the video"),
    ("large-v3", "Best", "most accurate; needs an NVIDIA graphics card to keep up\n"
                         "with the video"),
]


def has_nvidia_gpu():
    if getattr(sys, "frozen", False):
        return False  # the downloadable builds always run on the processor
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def recommended(gpu):
    # Without a GPU only "small" keeps up with playback, and subtitles that
    # lag behind look broken to someone who doesn't know why.
    return "large-v3" if gpu else "small"


def effective(name, gpu=None):
    """The model the helper will use for a setting ("auto" or empty → the default)."""
    if name in (None, "", "auto"):
        return recommended(has_nvidia_gpu() if gpu is None else gpu)
    return name


def is_included(name):
    """Shipped inside this download (offline builds)."""
    return helper.resolve_model(name) != name


def is_downloaded(name):
    """Usable without downloading: included, or already in the download cache."""
    if is_included(name):
        return True
    helper.quiet_huggingface()
    try:
        from faster_whisper import download_model
        download_model(name, local_files_only=True)
        return True
    except Exception:
        return False


def status(name):
    if is_included(name):
        return "included in this download"
    if is_downloaded(name):
        return "downloaded"
    return f"not downloaded yet; downloads when you first play a video ({SIZES.get(name, '?')})"


def ask(current=None, gpu=None, read=None, write=print):
    """Ask which model to use and return its name; Enter takes the suggestion."""
    read = read or input
    gpu = has_nvidia_gpu() if gpu is None else gpu
    names = [name for name, _, _ in CHOICES]
    default = current if current in names else recommended(gpu)

    write("\nWhich translation quality do you want?\n")
    for number, (name, label, text) in enumerate(CHOICES, 1):
        if is_included(name):
            notes = ["included in this download"]
        elif is_downloaded(name):
            notes = ["already downloaded"]
        else:
            notes = [f"{SIZES[name]} download"]
        if name == recommended(gpu):
            notes.append("recommended for this computer")
        if name == current:
            notes.append("your current choice")
        start = f"  {number}) {label:<8}  "
        indent = "\n" + " " * len(start)
        write(f"{start}{text.replace(chr(10), indent)}{indent}({', '.join(notes)})")
    write("\nYou can change this later by running the installer again.")

    prompt = f"Type 1, 2 or 3 and press Enter (just Enter = {names.index(default) + 1}): "
    while True:
        try:
            answer = read(prompt).strip().lower()
        except EOFError:
            return default
        if not answer:
            return default
        if answer.isdigit() and 1 <= int(answer) <= len(names):
            return names[int(answer) - 1]
        for name, label, _ in CHOICES:
            if answer in (name, label.lower(), name.split("-")[0]):
                return name
        write("Please type 1, 2 or 3.")


def slow_on_this_computer(name, gpu=None):
    gpu = has_nvidia_gpu() if gpu is None else gpu
    return not gpu and name in ("medium", "large-v3")

"""AutoSubs helper: turns the speech in a video into English subtitles.

Started in the background by the AutoSubs VLC scripts as

    vlc-autosubs-helper <jobs dir>/<id>.job

It runs Whisper (via faster-whisper) with task="translate", which goes
straight from speech in ~99 languages (French, Russian, Japanese, Czech, ...)
to English text. While it works it keeps <id>.status up to date and writes
growing subtitle snapshots <id>.<n>.srt that VLC loads as playback advances.

Only one helper runs at a time: a new job stops the previous one, so the
video you are watching now always gets the CPU/GPU.
"""

import os
import signal
import sys
import textwrap
import threading
import time
import traceback

from vlc_autosubs import __version__ as VERSION

HEARTBEAT_S = 10
# Wall-clock seconds between snapshots; short at first so the opening
# minutes get subtitles quickly.
SNAPSHOT_INTERVALS = [5, 10, 20, 30, 60]
MAX_LINE = 42
MAX_LINES = 2


def read_kv(path):
    data = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    return data


def truthy(v):
    return str(v).lower() in ("1", "true", "yes", "on")


def replace_with_retry(src, dst):
    # On Windows os.replace fails while VLC has dst open for reading.
    for _ in range(20):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            time.sleep(0.1)
    os.replace(src, dst)


class Status:
    """Atomic key=value status file shared with the Lua side."""

    def __init__(self, path):
        self.path = path
        self.data = {}
        self.lock = threading.Lock()

    def update(self, **fields):
        with self.lock:
            self.data.update(fields)
            self.data["updated"] = int(time.time())
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for k, v in self.data.items():
                    f.write(f"{k}={str(v).replace(chr(10), ' ')}\n")
            replace_with_retry(tmp, self.path)

    def heartbeat_forever(self):
        while True:
            time.sleep(HEARTBEAT_S)
            self.update()


# --------------------------------------------------------------------------
# process management
# --------------------------------------------------------------------------

def pid_alive(pid):
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        k32.GetExitCodeProcess(handle, ctypes.byref(code))
        k32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def take_over(jobs_dir, job_id):
    """Stop the previous helper (if any) and register this one."""
    lock = os.path.join(jobs_dir, "current.pid")
    try:
        with open(lock, encoding="utf-8") as f:
            pid_s, _, prev_id = f.read().strip().partition(" ")
        pid = int(pid_s)
    except (OSError, ValueError):
        pid, prev_id = None, None
    if pid and pid != os.getpid() and prev_id != job_id and pid_alive(pid):
        for sig in (signal.SIGTERM, getattr(signal, "SIGKILL", None)):
            if sig is None:
                break
            try:
                os.kill(pid, sig)
            except OSError:
                pass
            for _ in range(30):
                if not pid_alive(pid):
                    break
                time.sleep(0.1)
            if not pid_alive(pid):
                break
        prev_status = os.path.join(jobs_dir, prev_id + ".status")
        try:
            st = Status(prev_status)
            st.data = read_kv(prev_status)
            if st.data.get("state") in ("starting", "loading", "running"):
                st.update(state="cancelled")
        except OSError:
            pass
    with open(lock, "w", encoding="utf-8") as f:
        f.write(f"{os.getpid()} {job_id}")


def reset_signals():
    # VLC blocks SIGTERM in its threads and children inherit the mask,
    # which would make us ignore the next helper's request to stop.
    # (SIGHUP stays ignored, as nohup set it up.)
    if hasattr(signal, "pthread_sigmask"):
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGTERM})
        signal.signal(signal.SIGTERM, signal.SIG_DFL)


def lower_priority():
    try:
        if os.name == "nt":
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL
        else:
            os.nice(10)
    except Exception:
        pass


# --------------------------------------------------------------------------
# subtitles
# --------------------------------------------------------------------------

def split_cue(start, end, text):
    """Wrap long segments into readable cues of at most MAX_LINES lines."""
    text = " ".join(text.split())
    if not text:
        return []
    lines = textwrap.wrap(text, MAX_LINE) or [text]
    chunks = [lines[i:i + MAX_LINES] for i in range(0, len(lines), MAX_LINES)]
    total = sum(len(" ".join(c)) for c in chunks)
    cues, t = [], start
    for c in chunks:
        dur = (end - start) * len(" ".join(c)) / total
        cues.append((t, t + dur, "\n".join(c)))
        t += dur
    return cues


def srt_time(seconds):
    ms = int(round(max(seconds, 0) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(path, cues):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(cues, 1):
            f.write(f"{i}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n\n")
    replace_with_retry(tmp, path)


# --------------------------------------------------------------------------
# speech translation
# --------------------------------------------------------------------------

def choose_model(job):
    """The Whisper model, device and compute type a job will use."""
    import ctranslate2
    device = job.get("device", "auto")
    if device == "auto" and getattr(sys, "frozen", False):
        # The downloadable builds don't ship CUDA's libraries; trying the GPU
        # would fetch the 3 GB large-v3 model only to fall back to the CPU.
        device = "cpu"
    if device == "auto":
        try:
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"
    model = job.get("model", "auto")
    if model == "auto":
        # large-v3 translates far better, but is only practical on a GPU.
        # (Note: "turbo"/"large-v3-turbo" was not trained to translate.)
        model = "large-v3" if device == "cuda" else "small"
    compute = "float16" if device == "cuda" else "int8"
    return model, device, compute


def pick_model(job, log):
    model, device, compute = choose_model(job)
    log(f"model={model} device={device} compute={compute}")
    return resolve_model(model), device, compute


def bundled_models_dir():
    """Models shipped inside an offline build sit next to the executable."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "models")
    return None


def resolve_model(name):
    """A model name, or the path of a bundled/local copy of it."""
    if os.path.isdir(name):
        return name
    bundled = bundled_models_dir()
    if bundled and os.path.isfile(os.path.join(bundled, name, "model.bin")):
        return os.path.join(bundled, name)
    return name


MODEL_SIZES = {"tiny": "75 MB", "base": "145 MB", "small": "480 MB",
               "medium": "1.5 GB", "large-v3": "3 GB"}


def quiet_huggingface():
    """Hide two harmless Hugging Face warnings that read like errors: no
    symlink support (normal on Windows; we keep one copy of each model, so
    it costs no space) and the server's tip to log in for faster downloads.
    Must run before huggingface_hub is imported."""
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HUB_VERBOSITY", "error")


def model_availability(name):
    """Whether a model is already on this computer, in words."""
    if os.path.isdir(name):
        return "local folder"
    if resolve_model(name) != name:
        return "bundled"
    quiet_huggingface()
    from faster_whisper.utils import _MODELS  # model name -> Hugging Face repo
    from huggingface_hub import try_to_load_from_cache
    repo = name if "/" in name else _MODELS.get(name)
    if repo is None:
        raise ValueError(f"unknown model '{name}', expected one of: {', '.join(_MODELS)}")
    # Only looks in the cache, never online. model.bin is the big file; it
    # is missing until its download has finished.
    if isinstance(try_to_load_from_cache(repo, "model.bin"), str):
        return "downloaded"
    size = MODEL_SIZES.get(name)
    return "not downloaded yet; downloads on first use" + (f", {size}" if size else "")


def download_model(name, output_dir=None):
    """Fetch a faster-whisper model (into the Hugging Face cache by default)."""
    quiet_huggingface()
    from faster_whisper import download_model as fw_download
    return fw_download(name, output_dir=output_dir)


def doctor(media=None):
    """Check that the speech stack works; returns a list of (check, ok, detail)."""
    quiet_huggingface()  # faster_whisper imports huggingface_hub
    results = []

    def check(name, fn):
        try:
            results.append((name, True, fn()))
        except Exception as e:
            results.append((name, False, f"{type(e).__name__}: {e}"))

    def cuda():
        import ctranslate2
        n = ctranslate2.get_cuda_device_count()
        return f"ctranslate2 {ctranslate2.__version__}, {n} CUDA device(s)"

    def vad():
        import numpy as np
        from faster_whisper.vad import get_speech_timestamps
        get_speech_timestamps(np.zeros(16000, dtype=np.float32))
        return "Silero VAD runs"

    def decode():
        from faster_whisper import decode_audio
        patch_pyav()
        audio = decode_audio(media)
        return f"decoded {len(audio) / 16000:.1f} s of audio from {media}"

    def model():
        from vlc_autosubs import installer
        conf = installer.read_conf()
        name, device, _compute = choose_model(conf)
        label = name
        if conf.get("model", "auto") == "auto":
            label += f", picked by auto for the {'GPU' if device == 'cuda' else 'CPU'}"
        return f"{label} ({model_availability(name)})"

    check("speech engine", cuda)
    check("voice detection", vad)
    check("model", model)
    if media:
        check("audio decoding", decode)
    return results


def patch_pyav():
    """faster-whisper calls av.open(..., metadata_errors=...), which newer
    PyAV releases no longer accept; drop the argument when it's rejected."""
    import av
    if getattr(av.open, "_autosubs_patched", False):
        return
    original = av.open

    def open_compat(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        except TypeError as e:
            if "metadata_errors" not in str(e) or "metadata_errors" not in kwargs:
                raise
            kwargs.pop("metadata_errors")
            return original(*args, **kwargs)

    open_compat._autosubs_patched = True
    av.open = open_compat


def translate(media, model_name, device, compute, log):
    """Yield (start, end, english_text); first yields (language, prob, duration)."""
    if os.environ.get("AUTOSUBS_FAKE"):
        yield from fake_translate(media)
        return
    from faster_whisper import WhisperModel
    patch_pyav()
    threads = max(1, (os.cpu_count() or 2) - 1)
    model = WhisperModel(model_name, device=device, compute_type=compute,
                         cpu_threads=threads)
    segments, info = model.transcribe(
        media,
        task="translate",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,  # avoids repetition loops
    )
    log(f"detected language {info.language} (p={info.language_probability:.2f})")
    yield info.language, info.language_probability, info.duration
    for seg in segments:
        yield seg.start, seg.end, seg.text


def fake_translate(media):
    """Test stand-in for Whisper (AUTOSUBS_FAKE=1): needs no model download."""
    import av
    with av.open(media) as c:
        duration = (c.duration or 0) / 1_000_000
    yield os.environ.get("AUTOSUBS_FAKE_LANG", "fr"), 0.99, duration
    t = 0.0
    while t < duration:
        time.sleep(float(os.environ.get("AUTOSUBS_FAKE_DELAY", "0.5")))
        yield t, min(t + 2.5, duration), f"Fake English line at {int(t)} s"
        t += 3.0


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def run(job_file):
    jobs_dir = os.path.dirname(os.path.abspath(job_file))
    job_id = os.path.splitext(os.path.basename(job_file))[0]
    job = read_kv(job_file)
    media = job["media"]
    status = Status(os.path.join(jobs_dir, job_id + ".status"))
    log_file = open(os.path.join(jobs_dir, job_id + ".log"), "a", encoding="utf-8")
    # Started without a console (Windows), stdout/stderr are None and any
    # library that prints, like the model download's progress bar, crashes.
    # Send that output to the job's log instead, and skip progress bars.
    if sys.stdout is None:
        sys.stdout = log_file
    if sys.stderr is None:
        sys.stderr = log_file
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    quiet_huggingface()

    def log(msg):
        log_file.write(time.strftime("%H:%M:%S ") + msg + "\n")
        log_file.flush()

    log(f"AutoSubs helper {VERSION}, job {job_id}: {media}")
    reset_signals()
    take_over(jobs_dir, job_id)
    lower_priority()
    status.update(state="loading", pid=os.getpid(), snapshot=0, covered=0, progress=0)
    threading.Thread(target=status.heartbeat_forever, daemon=True).start()

    snap_path = lambda n: os.path.join(jobs_dir, f"{job_id}.{n}.srt")
    for name in os.listdir(jobs_dir):  # leftovers from an earlier run
        if name.startswith(job_id + ".") and name.endswith(".srt"):
            os.remove(os.path.join(jobs_dir, name))

    model, device, compute = pick_model(job, log)
    cues, snap = [], 0

    def snapshot():
        nonlocal snap
        snap += 1
        write_srt(snap_path(snap), cues)
        status.update(snapshot=snap, covered=round(cues[-1][1], 1))
        if snap > 1:
            try:
                os.remove(snap_path(snap - 1))
            except OSError:
                pass

    def attempt(device, compute):
        stream = translate(media, model, device, compute, log)
        language, _prob, duration = next(stream)
        status.update(state="running", language=language, duration=int(duration))
        if language == "en" and truthy(job.get("skip_english_audio", "1")):
            status.update(state="english")
            return False
        last = time.time()
        for start, end, text in stream:
            cues.extend(split_cue(start, end, text))
            status.data["progress"] = round(min(end / duration, 1.0), 3) if duration else 0
            interval = SNAPSHOT_INTERVALS[min(snap, len(SNAPSHOT_INTERVALS) - 1)]
            if cues and time.time() - last >= interval:
                snapshot()
                last = time.time()
        return True

    try:
        finished = attempt(device, compute)
    except Exception as e:
        if device != "cuda" or cues:
            raise
        # Typical: CUDA present but cuBLAS/cuDNN missing. Fall back to CPU.
        log(f"GPU failed ({e}); retrying on CPU")
        model, device, compute = pick_model(dict(job, device="cpu"), log)
        finished = attempt(device, compute)
    if not finished:
        log("audio is English; nothing to do")
        return

    if cues:
        snapshot()
        if truthy(job.get("write_sidecar", "1")):
            sidecar = os.path.splitext(media)[0] + ".en.srt"
            if not os.path.exists(sidecar):
                try:
                    write_srt(sidecar, cues)
                    log(f"saved {sidecar}")
                except OSError as e:
                    log(f"could not save {sidecar}: {e}")
    status.update(state="done", progress=1)
    log(f"done: {len(cues)} cues")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        if sys.stdout:  # None in the windowless Windows launcher
            print(__doc__)
        sys.exit(2)
    job_file = argv[0]
    try:
        run(job_file)
    except Exception as e:
        jobs_dir = os.path.dirname(os.path.abspath(job_file))
        job_id = os.path.splitext(os.path.basename(job_file))[0]
        with open(os.path.join(jobs_dir, job_id + ".log"), "a", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        st = Status(os.path.join(jobs_dir, job_id + ".status"))
        try:
            st.data = read_kv(st.path)
        except OSError:
            pass
        st.update(state="error", error=f"{type(e).__name__}: {e}"[:200])
        sys.exit(1)
    # Don't wait for the heartbeat thread.
    os._exit(0)


if __name__ == "__main__":
    main()

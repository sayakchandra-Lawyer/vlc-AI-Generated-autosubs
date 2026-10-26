import os

from vlc_autosubs import helper


def test_srt_time():
    assert helper.srt_time(0) == "00:00:00,000"
    assert helper.srt_time(3723.4567) == "01:02:03,457"
    assert helper.srt_time(-1) == "00:00:00,000"


def test_split_cue_wraps_long_text_into_two_line_cues():
    text = "word " * 40
    cues = helper.split_cue(10.0, 20.0, text)
    assert len(cues) > 1
    assert cues[0][0] == 10.0 and abs(cues[-1][1] - 20.0) < 1e-9
    for start, end, body in cues:
        assert start < end
        lines = body.split("\n")
        assert len(lines) <= helper.MAX_LINES
        assert all(len(line) <= helper.MAX_LINE for line in lines)


def test_split_cue_ignores_empty_text():
    assert helper.split_cue(0, 1, "   ") == []


def test_resolve_model_keeps_names_and_paths(tmp_path):
    assert helper.resolve_model("small") == "small"
    assert helper.resolve_model(str(tmp_path)) == str(tmp_path)


def _run_job(tmp_path, monkeypatch, media, language="fr", **job):
    monkeypatch.setenv("AUTOSUBS_FAKE", "1")
    monkeypatch.setenv("AUTOSUBS_FAKE_DELAY", "0")
    monkeypatch.setenv("AUTOSUBS_FAKE_LANG", language)
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    job_file = jobs / "abc_film.job"
    job_file.write_text("".join(f"{k}={v}\n" for k, v in dict(media=media, **job).items()),
                        encoding="utf-8")
    helper.run(str(job_file))
    return jobs, helper.read_kv(str(jobs / "abc_film.status"))


def test_job_writes_subtitles_and_sidecar(tmp_path, monkeypatch, sample_wav):
    jobs, status = _run_job(tmp_path, monkeypatch, sample_wav)
    assert status["state"] == "done"
    assert status["language"] == "fr"
    snap = jobs / f"abc_film.{status['snapshot']}.srt"
    text = snap.read_text(encoding="utf-8")
    assert text.startswith("1\n00:00:00,000 --> ")
    sidecar = sample_wav.with_name(sample_wav.stem + ".en.srt")
    assert sidecar.read_text(encoding="utf-8") == text


def test_job_without_sidecar(tmp_path, monkeypatch, sample_wav):
    _run_job(tmp_path, monkeypatch, sample_wav, write_sidecar=0)
    assert not sample_wav.with_name(sample_wav.stem + ".en.srt").exists()


def test_english_audio_is_skipped(tmp_path, monkeypatch, sample_wav):
    jobs, status = _run_job(tmp_path, monkeypatch, sample_wav, language="en")
    assert status["state"] == "english"
    assert not list(jobs.glob("*.srt"))


def test_doctor_checks_the_speech_stack(sample_wav):
    results = {name: (ok, detail) for name, ok, detail in helper.doctor(str(sample_wav))}
    assert results["speech engine"][0], results
    assert results["voice detection"][0], results
    assert results["audio decoding"][0], results
    assert "20.0 s" in results["audio decoding"][1]


def test_job_survives_missing_console(tmp_path, monkeypatch, sample_wav):
    """Windows starts the helper without a console: stdout/stderr are None,
    and the model download's progress bar used to crash on that."""
    def chatty_translate(media):
        from huggingface_hub.utils import tqdm
        bar = tqdm(total=1, desc="model.bin", disable=False)
        bar.update(1)
        bar.close()
        print("printed by a library")
        yield "fr", 0.99, 6.0
        yield 0.0, 2.0, "Hello"

    monkeypatch.setattr(helper, "fake_translate", chatty_translate)
    monkeypatch.setattr("sys.stdout", None)
    monkeypatch.setattr("sys.stderr", None)
    jobs, status = _run_job(tmp_path, monkeypatch, sample_wav)
    assert status["state"] == "done", status
    assert "printed by a library" in (jobs / "abc_film.log").read_text(encoding="utf-8")


def test_downloadable_build_stays_on_cpu(monkeypatch):
    # The builds ship no CUDA libraries, so "auto" must not pick the GPU.
    import ctranslate2
    monkeypatch.setattr(ctranslate2, "get_cuda_device_count", lambda: 1)
    assert helper.pick_model({}, lambda msg: None)[1] == "cuda"  # not frozen
    monkeypatch.setattr("sys.frozen", True, raising=False)
    model, device, compute = helper.pick_model({}, lambda msg: None)
    assert (model, device, compute) == ("small", "cpu", "int8")


def test_harmless_huggingface_warnings_are_hidden():
    # Needs a fresh interpreter: the settings apply when huggingface_hub loads.
    import subprocess
    import sys
    code = (
        "import os\n"
        "for k in ('HF_HUB_DISABLE_SYMLINKS_WARNING', 'HF_HUB_VERBOSITY'):\n"
        "    os.environ.pop(k, None)\n"
        "from vlc_autosubs import helper\n"
        "helper.quiet_huggingface()\n"
        "import logging\n"
        "from huggingface_hub import constants\n"
        "from huggingface_hub.utils import logging as hf_logging\n"
        "assert constants.HF_HUB_DISABLE_SYMLINKS_WARNING\n"
        "assert hf_logging.get_logger('huggingface_hub').getEffectiveLevel() >= logging.ERROR\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_doctor_says_whether_the_model_is_downloaded(fake_home, tmp_path):
    # A fresh interpreter, because huggingface_hub reads HF_HUB_CACHE when it
    # loads; the empty cache folder stands in for a model not downloaded yet.
    import ast
    import subprocess
    import sys
    from vlc_autosubs import installer
    installer.write_conf({"model": "medium"})
    cache = tmp_path / "hf-cache"
    env = dict(os.environ, HF_HUB_CACHE=str(cache), HF_HUB_OFFLINE="1")
    code = ("from vlc_autosubs import helper\n"
            "print({name: (ok, detail) for name, ok, detail in helper.doctor()}['model'])\n")

    def model_check():
        out = subprocess.run([sys.executable, "-c", code], env=env, check=True,
                             capture_output=True, text=True).stdout
        return ast.literal_eval(out.strip().splitlines()[-1])

    not_yet = (True, "medium (not downloaded yet; downloads on first use, 1.5 GB)")
    assert model_check() == not_yet

    # An interrupted download: the small files arrived, model.bin didn't.
    snapshot = cache / "models--Systran--faster-whisper-medium" / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    (snapshot.parent.parent / "refs").mkdir()
    (snapshot.parent.parent / "refs" / "main").write_text("abc123")
    (snapshot / "config.json").write_text("{}")
    assert model_check() == not_yet

    (snapshot / "model.bin").write_bytes(b"")
    assert model_check() == (True, "medium (downloaded)")

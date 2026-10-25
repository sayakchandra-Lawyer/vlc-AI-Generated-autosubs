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

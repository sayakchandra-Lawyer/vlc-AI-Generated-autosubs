import math
import struct
import wave

import pytest


@pytest.fixture
def sample_wav(tmp_path):
    """A 20 s, 16 kHz mono tone; stands in for a video's audio track."""
    path = tmp_path / "Film d'été.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        frames = (int(8000 * math.sin(i / 10)) for i in range(16000 * 20))
        w.writeframes(b"".join(struct.pack("<h", f) for f in frames))
    return path


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Point every VLC location at a temporary folder."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("APPDATA", str(home / "AppData"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "config"))
    return home

from __future__ import annotations

import sys
import types
import wave
from pathlib import Path

import pytest

from voice.audio import record_to_wav
from voice.speech import (
    FasterWhisperRecognizer,
    ModelUnavailableError,
    Transcript,
    WindowsSpeechOutput,
)


def make_local_model(model_dir: Path) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    for name in ("config.json", "model.bin", "tokenizer.json"):
        (model_dir / name).touch()


def test_model_missing_is_reported_without_network_access(tmp_path: Path) -> None:
    recognizer = FasterWhisperRecognizer(tmp_path / "model")
    assert not recognizer.model_installed
    with pytest.raises(ModelUnavailableError, match="Download model"):
        recognizer.transcribe(tmp_path / "audio.wav")


def test_local_transcription_uses_cpu_int8_and_detects_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "model"
    make_local_model(model_dir)
    init_options = {}

    class FakeModel:
        def __init__(self, path, **kwargs):
            init_options.update(path=path, **kwargs)

        def transcribe(self, path, **kwargs):
            assert path.endswith("audio.wav")
            assert kwargs == {"beam_size": 1, "vad_filter": True}
            segments = [types.SimpleNamespace(text="Open settings")]
            return segments, types.SimpleNamespace(language="en", language_probability=0.96)

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    recognizer = FasterWhisperRecognizer(model_dir)
    result = recognizer.transcribe(tmp_path / "audio.wav")

    assert result == Transcript("Open settings", "en", 0.96)
    assert init_options["device"] == "cpu"
    assert init_options["compute_type"] == "int8"
    assert init_options["local_files_only"] is True


def test_download_uses_pinned_tiny_model_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "model"
    calls = {}

    def download_model(name, **kwargs):
        calls.update(name=name, **kwargs)
        make_local_model(Path(kwargs["output_dir"]))

    package = types.ModuleType("faster_whisper")
    package.utils = types.SimpleNamespace(download_model=download_model)
    monkeypatch.setitem(sys.modules, "faster_whisper", package)
    monkeypatch.setitem(sys.modules, "faster_whisper.utils", package.utils)

    recognizer = FasterWhisperRecognizer(model_dir)
    assert recognizer.download_model() == model_dir
    assert calls["name"] == "tiny"
    assert calls["revision"] == "d90ca5fe260221311c53c58e660288d3deb8d356"
    assert recognizer.model_installed


def test_recording_writes_bounded_mono_16khz_wav(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio_api = types.ModuleType("sounddevice")
    audio_api.query_devices = lambda **_kwargs: {"default_samplerate": 44_100}

    class FakeRawStream:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]

        def __enter__(self):
            self.callback(b"\x00\x00" * 22_050, 22_050, None, None)
            return self

        def __exit__(self, *_args):
            return False

    audio_api.RawInputStream = FakeRawStream
    monkeypatch.setitem(sys.modules, "sounddevice", audio_api)
    output = tmp_path / "capture.wav"
    stop = __import__("threading").Event()
    stop.set()

    assert record_to_wav(output, stop) == output
    with wave.open(str(output), "rb") as recording:
        assert recording.getnchannels() == 1
        assert recording.getframerate() == 16_000
        assert recording.getsampwidth() == 2
        assert recording.getnframes() == 8_000


def test_empty_speech_output_does_not_initialize_com() -> None:
    WindowsSpeechOutput().speak("   ")

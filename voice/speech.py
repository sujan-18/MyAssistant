"""Local speech model management, transcription and Windows speech output."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


TINY_MODEL_REVISION = "d90ca5fe260221311c53c58e660288d3deb8d356"


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: str | None
    language_probability: float | None


class ModelUnavailableError(RuntimeError):
    """The local speech model has not been downloaded yet."""


class SpeechRecognizer(Protocol):
    def transcribe(self, wav_path: Path) -> Transcript: ...


class SpeechOutput(Protocol):
    def speak(self, text: str) -> None: ...


class FasterWhisperRecognizer:
    """Explicitly local CPU/int8 Whisper recognizer."""

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self._model = None

    @property
    def model_installed(self) -> bool:
        return all(
            (self.model_dir / filename).is_file()
            for filename in ("config.json", "model.bin", "tokenizer.json")
        )

    def download_model(self) -> Path:
        try:
            from faster_whisper.utils import download_model
        except ImportError as exc:
            raise RuntimeError("Install the optional voice dependencies first.") from exc
        self.model_dir.mkdir(parents=True, exist_ok=True)
        download_model(
            "tiny",
            output_dir=str(self.model_dir),
            revision=TINY_MODEL_REVISION,
        )
        if not self.model_installed:
            raise RuntimeError("Model download finished, but required files are missing.")
        return self.model_dir

    def transcribe(self, wav_path: Path) -> Transcript:
        if not self.model_installed:
            raise ModelUnavailableError(
                "The local Whisper tiny model is missing. Use Download model while online."
            )
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Install the optional voice dependencies first.") from exc
        if self._model is None:
            self._model = WhisperModel(
                str(self.model_dir),
                device="cpu",
                compute_type="int8",
                cpu_threads=max(1, min(os.cpu_count() or 1, 4)),
                local_files_only=True,
            )
        segments, info = self._model.transcribe(
            str(wav_path),
            beam_size=1,
            vad_filter=True,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        language = getattr(info, "language", None)
        probability = getattr(info, "language_probability", None)
        return Transcript(text, language, probability)


class WindowsSpeechOutput:
    """Use an installed Windows SAPI voice; never speak without an explicit call."""

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        try:
            import pythoncom
            import win32com.client
        except ImportError as exc:
            raise RuntimeError("Install the optional voice dependencies first.") from exc
        pythoncom.CoInitialize()
        speaker = None
        try:
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(text, 0)
        finally:
            speaker = None
            pythoncom.CoUninitialize()

"""Explicit push-to-talk UI; transcripts remain previews until Phase 9."""

from __future__ import annotations

import tempfile
import threading
import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from voice.audio import MAX_RECORDING_SECONDS, record_to_wav
from voice.speech import FasterWhisperRecognizer, SpeechRecognizer, Transcript, WindowsSpeechOutput


class CaptureWorker(QThread):
    recorded = Signal(str)
    failed = Signal(str)

    def __init__(self, output_path: Path) -> None:
        super().__init__()
        self.output_path = output_path
        self.stop_event = threading.Event()

    def stop_recording(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        try:
            self.recorded.emit(str(record_to_wav(self.output_path, self.stop_event)))
        except Exception as exc:
            self.failed.emit(str(exc))


class ModelWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, recognizer: FasterWhisperRecognizer) -> None:
        super().__init__()
        self.recognizer = recognizer

    def run(self) -> None:
        # Bound a stalled model request so the UI can report the failure and retry.
        os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "10")
        os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "15")
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        try:
            self.completed.emit(str(self.recognizer.download_model()))
        except Exception as exc:
            self.failed.emit(str(exc))


class TranscriptionWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, recognizer: SpeechRecognizer, wav_path: Path) -> None:
        super().__init__()
        self.recognizer = recognizer
        self.wav_path = wav_path

    def run(self) -> None:
        try:
            self.completed.emit(self.recognizer.transcribe(self.wav_path))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.wav_path.unlink(missing_ok=True)


class SpeechOutputWorker(QThread):
    completed = Signal()
    failed = Signal(str)

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

    def run(self) -> None:
        try:
            WindowsSpeechOutput().speak(self.text)
            self.completed.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class VoicePanel(QWidget):
    """Voice UI that captures only on an explicit button press."""

    def __init__(self, model_dir: Path) -> None:
        super().__init__()
        self.setObjectName("VoicePanel")
        self.recognizer = FasterWhisperRecognizer(model_dir)
        self._capture_worker: CaptureWorker | None = None
        self._transcription_worker: TranscriptionWorker | None = None
        self._model_worker: ModelWorker | None = None
        self._speech_worker: SpeechOutputWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(12)
        self.status_label = QLabel("Microphone is off. Recording starts only when you press Record.")
        self.status_label.setObjectName("PanelStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        model_info = QLabel(
            "Local model: Whisper tiny multilingual (about 78 MB). CPU int8; no GPU required."
        )
        model_info.setObjectName("Description")
        model_info.setWordWrap(True)
        layout.addWidget(model_info)

        self.record_button = QPushButton("Record")
        self.record_button.setObjectName("PrimaryButton")
        self.record_button.clicked.connect(self._toggle_recording)
        layout.addWidget(self.record_button)
        self.download_button = QPushButton("Download model (one-time, internet required)")
        self.download_button.clicked.connect(self._confirm_model_download)
        layout.addWidget(self.download_button)

        self.transcript_view = QTextEdit()
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setPlaceholderText("Your transcript preview will appear here.")
        layout.addWidget(self.transcript_view, 1)
        self.speak_button = QPushButton("Speak transcript")
        self.speak_button.setObjectName("PrimaryButton")
        self.speak_button.setEnabled(False)
        self.speak_button.clicked.connect(self._speak_transcript)
        layout.addWidget(self.speak_button)
        self._refresh_model_status()

    def _refresh_model_status(self) -> None:
        self.download_button.setEnabled(not self.recognizer.model_installed)
        if self.recognizer.model_installed:
            self.status_label.setText("Local model ready. Press Record to start push-to-talk.")

    def _toggle_recording(self) -> None:
        worker = self._capture_worker
        if worker is not None and worker.isRunning():
            self.record_button.setEnabled(False)
            self.status_label.setText("Stopping microphone and preparing local transcription…")
            worker.stop_recording()
            return
        handle = tempfile.NamedTemporaryFile(prefix="myassistant-voice-", suffix=".wav", delete=False)
        audio_path = Path(handle.name)
        handle.close()
        self._capture_worker = CaptureWorker(audio_path)
        self._capture_worker.recorded.connect(self._transcribe)
        self._capture_worker.failed.connect(lambda error, path=audio_path: (path.unlink(missing_ok=True), self._show_error(error)))
        self._capture_worker.finished.connect(self._capture_finished)
        self._capture_worker.start()
        self.record_button.setText("Stop recording")
        self.status_label.setText(f"Recording from the default microphone (up to {MAX_RECORDING_SECONDS} seconds)…")

    def _capture_finished(self) -> None:
        worker = self._capture_worker
        if worker is not None and not worker.isRunning():
            self._capture_worker = None
            self.record_button.setText("Record")
            self.record_button.setEnabled(True)

    def stop_recording(self) -> None:
        if self._capture_worker is not None and self._capture_worker.isRunning():
            self._capture_worker.stop_recording()

    def _transcribe(self, path: str) -> None:
        audio_path = Path(path)
        self.record_button.setEnabled(False)
        self.status_label.setText("Transcribing on CPU; audio stays on this computer…")
        self._transcription_worker = TranscriptionWorker(self.recognizer, audio_path)
        self._transcription_worker.completed.connect(self._show_transcript)
        self._transcription_worker.failed.connect(self._show_error)
        self._transcription_worker.finished.connect(self._transcription_finished)
        self._transcription_worker.start()

    def _transcription_finished(self) -> None:
        self._transcription_worker = None
        self.record_button.setEnabled(True)

    def _show_transcript(self, transcript: Transcript) -> None:
        self.transcript_view.setPlainText(transcript.text)
        language = transcript.language or "unknown"
        self.status_label.setText(
            f"Preview only — detected language: {language}. Recognized text is not executed."
        )
        self.speak_button.setEnabled(bool(transcript.text.strip()))

    def _confirm_model_download(self) -> None:
        answer = QMessageBox.question(
            self,
            "Download local speech model",
            "Download the approximately 78 MB Whisper tiny multilingual model from Hugging Face? "
            "This is a one-time internet download. Transcription then runs locally. The model is MIT-licensed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.download_button.setEnabled(False)
        self.record_button.setEnabled(False)
        self.status_label.setText("Downloading the selected model…")
        self._model_worker = ModelWorker(self.recognizer)
        self._model_worker.completed.connect(self._model_downloaded)
        self._model_worker.failed.connect(self._show_error)
        self._model_worker.finished.connect(self._model_download_finished)
        self._model_worker.start()

    def _model_downloaded(self, _path: str) -> None:
        self.status_label.setText("Model downloaded. You can now record speech offline.")

    def _model_download_finished(self) -> None:
        self._model_worker = None
        self.record_button.setEnabled(True)
        self._refresh_model_status()

    def _speak_transcript(self) -> None:
        text = self.transcript_view.toPlainText()
        if not text.strip():
            return
        self.speak_button.setEnabled(False)
        self._speech_worker = SpeechOutputWorker(text)
        self._speech_worker.completed.connect(self._speech_finished)
        self._speech_worker.failed.connect(self._show_error)
        self._speech_worker.finished.connect(lambda: setattr(self, "_speech_worker", None))
        self._speech_worker.start()

    def _speech_finished(self) -> None:
        self.status_label.setText("Finished speaking.")
        self.speak_button.setEnabled(bool(self.transcript_view.toPlainText().strip()))

    def _show_error(self, error: str) -> None:
        self.status_label.setText(f"Voice feature unavailable: {error}")
        if self.transcript_view.toPlainText().strip():
            self.speak_button.setEnabled(True)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.stop_recording()
        if self._capture_worker is not None and self._capture_worker.isRunning():
            self._capture_worker.wait()
        for worker in (self._transcription_worker, self._model_worker, self._speech_worker):
            if worker is not None and worker.isRunning():
                worker.wait()
        event.accept()

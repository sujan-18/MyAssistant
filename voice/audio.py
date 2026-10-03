"""Push-to-talk recording with bounded, temporary PCM WAV output."""

from __future__ import annotations

import threading
import time
import wave
from pathlib import Path


SAMPLE_RATE = 16_000
CHANNELS = 1
MAX_RECORDING_SECONDS = 60


def available_input_devices() -> tuple[str, ...]:
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("Install the optional voice dependencies first.") from exc
    return tuple(
        str(device["name"])
        for device in sd.query_devices()
        if int(device.get("max_input_channels", 0)) > 0
    )


def record_to_wav(
    output_path: Path,
    stop_event: threading.Event,
    *,
    max_seconds: int = MAX_RECORDING_SECONDS,
) -> Path:
    """Record only while the caller holds a push-to-talk session open."""
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("Install the optional voice dependencies first.") from exc

    blocks: list[bytes] = []
    callback_errors: list[str] = []

    def capture(indata, frames, time_info, status) -> None:
        if status:
            callback_errors.append(str(status))
        blocks.append(bytes(indata))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        device = sd.query_devices(kind="input")
        input_rate = int(round(float(device["default_samplerate"])))
        if input_rate <= 0:
            raise RuntimeError("The default microphone reported an invalid sample rate.")
        with sd.RawInputStream(
            samplerate=input_rate,
            channels=CHANNELS,
            dtype="int16",
            callback=capture,
        ):
            while not stop_event.wait(0.05) and time.monotonic() - started < max_seconds:
                pass
    except Exception as exc:
        raise RuntimeError(f"Could not record from the default microphone: {exc}") from exc
    if callback_errors:
        raise RuntimeError("Microphone input reported an audio overflow; try again closer to the microphone.")
    raw_audio = b"".join(blocks)
    input_samples = len(raw_audio) // 2
    if input_samples < input_rate // 4:
        raise RuntimeError("No speech audio was recorded. Hold Record while speaking, then stop.")
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("The voice extra is missing NumPy, required to normalize microphone audio.") from exc
    if input_rate == SAMPLE_RATE:
        normalized_audio = raw_audio
    else:
        samples = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32)
        output_count = max(1, round(input_samples * SAMPLE_RATE / input_rate))
        source_positions = np.arange(input_samples, dtype=np.float64)
        target_positions = np.arange(output_count, dtype=np.float64) * input_rate / SAMPLE_RATE
        resampled = np.interp(target_positions, source_positions, samples)
        normalized_audio = np.clip(np.rint(resampled), -32768, 32767).astype(np.int16).tobytes()
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(normalized_audio)
    return output_path

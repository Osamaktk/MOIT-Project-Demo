from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol

from app.core.config import settings


class STTProvider(Protocol):
    name: str

    def transcribe(self, audio_path: str, language_hint: str | None = None) -> tuple[str, list[dict[str, Any]]]: ...


class FasterWhisperProvider:
    name = "faster_whisper"

    def __init__(self, model_size: str | None = None):
        self.model_size = model_size or settings.stt_model_size

    def transcribe(self, audio_path: str, language_hint: str | None = None) -> tuple[str, list[dict[str, Any]]]:
        try:
            model = get_whisper_model(self.model_size)
        except ImportError as exc:
            raise RuntimeError("faster-whisper is not installed. Install backend requirements to transcribe audio.") from exc
        segments, info = model.transcribe(audio_path, language=language_hint or None, word_timestamps=False)
        output = [{"start": max(0.0, float(segment.start)), "end": max(float(segment.start) + 0.01, float(segment.end)), "text": segment.text.strip(), "lang": info.language, "speaker": None} for segment in segments if segment.text.strip()]
        return info.language, output


@lru_cache(maxsize=2)
def get_whisper_model(model_size: str):
    from faster_whisper import WhisperModel

    return WhisperModel(model_size, device="cpu", compute_type="int8")

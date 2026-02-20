from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.config import Settings


class STTService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: Any | None = None

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "faster-whisper is not installed. Install backend requirements first."
            ) from exc

        self._model = WhisperModel(
            self.settings.whisper_model_size,
            compute_type=self.settings.whisper_compute_type,
        )
        return self._model

    def _transcribe_sync(self, audio_path: Path, language: str | None) -> str:
        model = self._get_model()
        segments, _ = model.transcribe(str(audio_path), language=language, beam_size=5)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise RuntimeError("Speech was not recognized. Try clearer audio.")
        return text

    async def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        return await asyncio.to_thread(self._transcribe_sync, audio_path, language)

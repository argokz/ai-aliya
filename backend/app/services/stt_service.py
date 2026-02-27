from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx

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
            self.settings.whisper_model,
            compute_type=self.settings.whisper_compute_type,
            device=self.settings.whisper_device,
        )
        return self._model

    async def _transcribe_remote(self, audio_path: Path, language: str | None) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(audio_path, "rb") as f:
                files = {"audio": (audio_path.name, f, "audio/wav")}
                data = {"language": language} if language else {}
                response = await client.post(
                    f"{self.settings.whisper_worker_url}/transcribe",
                    files=files,
                    data=data,
                )
        
        response.raise_for_status()
        result = response.json()
        return result.get("text", "").strip()

    def _transcribe_sync(self, audio_path: Path, language: str | None) -> str:
        model = self._get_model()
        segments, _ = model.transcribe(str(audio_path), language=language, beam_size=5)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise RuntimeError("Speech was not recognized. Try clearer audio.")
        return text

    async def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        if self.settings.whisper_use_remote:
            return await self._transcribe_remote(audio_path, language)
        return await asyncio.to_thread(self._transcribe_sync, audio_path, language)

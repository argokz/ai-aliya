from __future__ import annotations

import asyncio
import re
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from app.config import Settings

_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_-]+")


class VoiceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._tts: Any | None = None
        self._tts_lock = Lock()

    def _sanitize_speaker_id(self, speaker_id: str) -> str:
        cleaned = _SANITIZE_RE.sub("_", speaker_id).strip("_")
        if not cleaned:
            raise ValueError("Invalid speaker_id")
        return cleaned

    def _speaker_dir(self, speaker_id: str) -> Path:
        return self.settings.voices_dir / self._sanitize_speaker_id(speaker_id)

    async def store_reference_audio(
        self,
        speaker_id: str,
        filename: str,
        data: bytes,
    ) -> Path:
        suffix = Path(filename).suffix.lower() or ".wav"
        if suffix not in {".wav", ".mp3", ".m4a", ".ogg", ".flac"}:
            raise ValueError("Unsupported audio format")

        speaker_dir = self._speaker_dir(speaker_id)
        speaker_dir.mkdir(parents=True, exist_ok=True)

        for old_file in speaker_dir.glob("reference.*"):
            old_file.unlink(missing_ok=True)

        target = speaker_dir / f"reference{suffix}"
        await asyncio.to_thread(target.write_bytes, data)
        return target

    def _get_reference_audio(self, speaker_id: str) -> Path:
        speaker_dir = self._speaker_dir(speaker_id)
        for file_path in sorted(speaker_dir.glob("reference.*")):
            if file_path.is_file():
                return file_path
        raise FileNotFoundError(
            "Voice profile not found. Call /voice/enroll once to clone a voice."
        )

    def list_speakers(self) -> list[tuple[str, bool]]:
        speakers: list[tuple[str, bool]] = []
        if not self.settings.voices_dir.exists():
            return speakers

        for item in sorted(self.settings.voices_dir.iterdir()):
            if not item.is_dir():
                continue
            has_ref = any(item.glob("reference.*"))
            speakers.append((item.name, has_ref))
        return speakers

    def _get_tts(self) -> Any:
        if self._tts is not None:
            return self._tts

        with self._tts_lock:
            if self._tts is not None:
                return self._tts
            try:
                from TTS.api import TTS
            except Exception as exc:  # pragma: no cover
                raise RuntimeError(
                    "Coqui TTS is not installed. Install backend requirements first."
                ) from exc

            self._tts = TTS(
                model_name=self.settings.tts_model_name,
                gpu=self.settings.tts_use_gpu,
                progress_bar=False,
            )

        return self._tts

    def _synthesize_sync(
        self,
        text: str,
        speaker_id: str,
        language: str,
        output_path: Path,
    ) -> None:
        reference_audio = self._get_reference_audio(speaker_id)
        tts = self._get_tts()
        tts.tts_to_file(
            text=text,
            speaker_wav=str(reference_audio),
            language=language,
            file_path=str(output_path),
        )

    async def synthesize(self, text: str, speaker_id: str, language: str) -> Path:
        safe_speaker_id = self._sanitize_speaker_id(speaker_id)
        output_path = (
            self.settings.generated_audio_dir
            / f"{safe_speaker_id}_{uuid4().hex[:12]}.wav"
        )
        await asyncio.to_thread(
            self._synthesize_sync,
            text,
            safe_speaker_id,
            language,
            output_path,
        )
        return output_path

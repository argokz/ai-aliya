from __future__ import annotations

import asyncio
import re
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from app.config import Settings

import torch

# Back to normal imports
_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_-]+")


class VoiceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings = settings
        self._tts: Any | None = None
        self._qwen_tts: Any | None = None
        self._tts_lock = Lock()
        self._qwen_lock = Lock()

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
        # Use a lambda to avoid parameter mismatch in to_thread
        await asyncio.to_thread(lambda: target.write_bytes(data))
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
                model_name=self.settings.xtts_model_name,
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
        if speaker_id.lower() == "aliya":
            if self.settings.tts_mode == "qwen_tts":
                # Unified Qwen synthesis (Remote with Local Fallback)
                reference_audio = Path(self.settings.aliya_reference_audio)
                if not reference_audio.is_absolute():
                    reference_audio = Path(__file__).parents[2] / reference_audio
                
                output_path = (
                    self.settings.generated_audio_dir
                    / f"aliya_qwen_{uuid4().hex[:12]}.wav"
                )
                
                try:
                    if self.settings.use_remote_worker and self.settings.qwen_worker_url:
                        await self._synthesize_qwen_remote(text, reference_audio, language, output_path)
                        return output_path
                except Exception as e:
                    print(f"Remote Qwen failed, falling back to local: {e}")
                
                # Fallback to local
                await self._synthesize_qwen_local(text, reference_audio, language, output_path)
                return output_path

            elif self.settings.tts_mode == "aliya_xtts":
                # Direct XTTS with reference audio for Aliya
                reference_audio = Path(self.settings.aliya_reference_audio)
                if not reference_audio.is_absolute():
                    reference_audio = Path(__file__).parents[2] / reference_audio
                
                output_path = (
                    self.settings.generated_audio_dir
                    / f"aliya_xtts_{uuid4().hex[:12]}.wav"
                )
                
                tts = self._get_tts()
                await asyncio.to_thread(
                    lambda: tts.tts_to_file(
                        text=text,
                        speaker_wav=str(reference_audio),
                        language=language,
                        file_path=str(output_path),
                    )
                )
                return output_path
            
            elif self.settings.tts_mode == "gemini_openvoice":
                # 1. Generate speech with Gemini TTS
                # 2. Convert to Aliya's voice with OpenVoice
                base_audio = await self._generate_gemini_tts(text)
                
                reference_audio = Path(self.settings.aliya_reference_audio)
                if not reference_audio.is_absolute():
                    reference_audio = Path(__file__).parents[2] / reference_audio
                
                output_path = (
                    self.settings.generated_audio_dir
                    / f"aliya_ov_{uuid4().hex[:12]}.wav"
                )
                
                await self._convert_voice_openvoice(base_audio, reference_audio, output_path)
                return output_path

        # Default behavior: uses enrolled speaker_id
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

    async def _generate_gemini_tts(self, text: str) -> Path:
        import httpx
        import base64
        
        model_name = self.settings.gemini_tts_model or "gemini-2.5-flash-preview-tts"
        url = f"{self.settings.gemini_base_url}/models/{model_name}:generateContent?key={self.settings.gemini_api_key}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"Please speak this text clearly with a natural voice: {text}"
                }]
            }],
            "generationConfig": {
                "response_modalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": self.settings.default_gemini_voice or "Aoede"
                        }
                    }
                }
            }
        }
        
        output_path = (
            self.settings.generated_audio_dir
            / f"base_gemini_{uuid4().hex[:12]}.wav"
        )
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                print(f"Gemini TTS Error Details: {response.text}")
                response.raise_for_status()
            
            data = response.json()
            if "candidates" in data:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "inlineData" in part:
                            audio_bytes = base64.b64decode(part["inlineData"]["data"])
                            # The model often returns raw PCM (L16). 
                            # We should wrap it in a WAV header or use pydub to save correctly.
                            from pydub import AudioSegment
                            import io
                            
                            # For gemini-2.5-flash-preview-tts it's 24000Hz, 16-bit, mono
                            audio_seg = AudioSegment(
                                data=audio_bytes,
                                sample_width=2,
                                frame_rate=24000,
                                channels=1
                            )
                            await asyncio.to_thread(lambda: audio_seg.export(str(output_path), format="wav"))
                            return output_path
                            
            raise RuntimeError(f"Gemini TTS failed to return audio data. Response: {data}")
            
    async def _convert_voice_openvoice(self, input_wav: Path, reference_wav: Path, output_wav: Path) -> None:
        # OpenVoice conversion
        # Typically uses a command line like: python -m openvoice_cli single --input input.wav --ref ref.wav --output output.wav
        
        # Let's try to call the CLI
        import subprocess
        
        cmd = [
            str(Path(__file__).parents[2] / "venv" / "Scripts" / "python.exe"),
            "-m", "openvoice_cli",
            "single",
            "--input", str(input_wav),
            "--ref", str(reference_wav),
            "--output", str(output_wav),
            "--device", "cpu",
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            print(f"OpenVoice error: {stderr.decode()}")
            raise RuntimeError(f"OpenVoice conversion failed: {stderr.decode()}")

    def _get_qwen_tts(self) -> Any:
        if self._qwen_tts is not None:
            return self._qwen_tts

        with self._qwen_lock:
            if self._qwen_tts is not None:
                return self._qwen_tts
            
            from qwen_tts import Qwen3TTSModel
            self._qwen_tts = Qwen3TTSModel.from_pretrained(
                "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
                device_map=self.settings.qwen_device or "cpu",
                torch_dtype=torch.float32 if (self.settings.qwen_device or "cpu") == "cpu" else torch.bfloat16
            )
        return self._qwen_tts

    async def _synthesize_qwen_local(self, text: str, reference_audio: Path, language: str, output_path: Path) -> None:
        tts = self._get_qwen_tts()
        import soundfile as sf
        
        def _local_gen():
            audio, sample_rate = tts.generate(
                text=text,
                speaker_wav=str(reference_audio),
                language=language
            )
            sf.write(str(output_path), audio, sample_rate)
            
        await asyncio.to_thread(_local_gen)

    async def _synthesize_qwen_remote(self, text: str, reference_audio: Path, language: str, output_path: Path) -> None:
        import httpx
        url = f"{self.settings.qwen_worker_url}/synthesize"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            with reference_audio.open("rb") as f:
                files = {"reference_audio": (reference_audio.name, f, "audio/wav")}
                data = {"text": text, "language": language}
                response = await client.post(url, data=data, files=files)
                
            if response.status_code != 200:
                raise RuntimeError(f"Worker synthesis failed: {response.text}")
                
            output_path.write_bytes(response.content)

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Voice Assistant"
    api_prefix: str = "/api/v1"

    data_dir: Path = Path(__file__).resolve().parents[1] / "data"
    voices_dir: Path = data_dir / "voices"
    generated_audio_dir: Path = data_dir / "generated_audio"
    uploads_dir: Path = data_dir / "uploads"

    llm_backend: Literal["ollama", "openai_compat", "openai", "gemini"] = "openai"
    ai_priority: Literal["gpt", "gemini"] = "gpt"
    
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    openai_compat_base_url: str = "http://localhost:8001/v1"
    openai_compat_model: str = "Qwen/Qwen2.5-7B-Instruct"
    openai_compat_api_key: str = "local"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    gemini_api_key: str = ""

    # TTS (Text-to-Speech)
    tts_mode: str = "aliya_xtts"
    reference_audio_paths: str = "audio_chunks/chunk_5.wav,audio_chunks/chunk_12.wav"
    aliya_reference_audio: str = "audio_chunks/chunk_12.wav"
    xtts_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    tts_use_gpu: bool = False
    
    # Qwen3-TTS
    qwen_model_size: str = "1.7B"
    qwen_device: Optional[str] = None
    qwen_worker_url: Optional[str] = None  # URL of the remote GPU worker
    use_remote_worker: bool = False
    
    # Gemini TTS
    gemini_tts_model: Optional[str] = "gemini-2.5-flash-preview-tts"
    default_gemini_voice: Optional[str] = "Aoede"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.0-flash"
    gemini_models: str = "gemini-3-pro-preview,gemini-3-flash-preview,gemini-2.5-flash,gemini-2.5-flash-lite,gemini-2.5-pro,gemini-2.0-flash"

    system_prompt: str = (
        "Ты голосовой AI-ассистент. Отвечай кратко, полезно и дружелюбно."
    )

    whisper_model: str = "medium"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_worker_url: str = "http://100.115.128.128:8004"
    whisper_use_remote: bool = True

    tts_mode: str = "aliya_xtts"
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"
    default_gemini_voice: str = "Gacrux"
    reference_audio_paths: str = "audio_chunks/chunk_5.wav,audio_chunks/chunk_12.wav"
    aliya_reference_audio: str = "audio_chunks/chunk_12.wav"
    xtts_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    tts_use_gpu: bool = False

    cors_allow_origins: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.voices_dir.mkdir(parents=True, exist_ok=True)
    settings.generated_audio_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    return settings

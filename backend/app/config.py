from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Voice Assistant"
    api_prefix: str = "/api/v1"

    data_dir: Path = Path(__file__).resolve().parents[1] / "data"
    voices_dir: Path = data_dir / "voices"
    generated_audio_dir: Path = data_dir / "generated_audio"
    uploads_dir: Path = data_dir / "uploads"

    llm_backend: Literal["ollama", "openai_compat", "openai", "gemini"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    openai_compat_base_url: str = "http://localhost:8001/v1"
    openai_compat_model: str = "Qwen/Qwen2.5-7B-Instruct"
    openai_compat_api_key: str = "local"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.0-flash"

    system_prompt: str = (
        "Ты голосовой AI-ассистент. Отвечай кратко, полезно и дружелюбно."
    )

    whisper_model_size: str = "small"
    whisper_compute_type: str = "int8"

    tts_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
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

from functools import lru_cache

from app.config import Settings, get_settings
from app.services.emotion_service import EmotionService
from app.services.llm_service import LLMService
from app.services.stt_service import STTService
from app.services.voice_service import VoiceService


@lru_cache(maxsize=1)
def get_stt_service() -> STTService:
    return STTService(get_settings())


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    return LLMService(get_settings())


@lru_cache(maxsize=1)
def get_voice_service() -> VoiceService:
    return VoiceService(get_settings())


@lru_cache(maxsize=1)
def get_emotion_service() -> EmotionService:
    return EmotionService()


def get_app_settings() -> Settings:
    return get_settings()

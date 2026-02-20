from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EmotionType = Literal[
    "neutral",
    "happy",
    "sad",
    "thinking",
    "surprised",
    "empathetic",
]


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    text: str = Field(min_length=1)
    speaker_id: str | None = None
    language: str = "ru"
    generate_audio: bool = True
    history: list[ChatMessage] = Field(default_factory=list)


class AssistantTurnResponse(BaseModel):
    user_text: str
    assistant_text: str
    emotion: EmotionType
    audio_url: str | None = None


class VoiceEnrollResponse(BaseModel):
    speaker_id: str
    reference_audio: str


class SpeakerInfo(BaseModel):
    speaker_id: str
    has_reference: bool

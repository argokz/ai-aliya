from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.config import Settings
from app.dependencies import (
    get_app_settings,
    get_emotion_service,
    get_llm_service,
    get_stt_service,
    get_voice_service,
)
from app.schemas import AssistantTurnResponse, ChatMessage, ChatRequest
from app.services.emotion_service import EmotionService
from app.services.llm_service import LLMService
from app.services.stt_service import STTService
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _build_audio_url(settings: Settings, file_path: Path) -> str:
    return f"{settings.api_prefix}/voice/audio/{file_path.name}"


async def _run_assistant_flow(
    user_text: str,
    speaker_id: str | None,
    language: str,
    generate_audio: bool,
    history: list[ChatMessage],
    settings: Settings,
    llm_service: LLMService,
    voice_service: VoiceService,
    emotion_service: EmotionService,
) -> AssistantTurnResponse:
    assistant_text = await llm_service.generate_reply(user_text=user_text, history=history)
    emotion = emotion_service.detect(user_text=user_text, assistant_text=assistant_text)

    audio_url: str | None = None
    if generate_audio and speaker_id:
        try:
            audio_path = await voice_service.synthesize(
                text=assistant_text,
                speaker_id=speaker_id,
                language=language,
            )
            audio_url = _build_audio_url(settings, audio_path)
        except FileNotFoundError:
            audio_url = None

    return AssistantTurnResponse(
        user_text=user_text,
        assistant_text=assistant_text,
        emotion=emotion,
        audio_url=audio_url,
    )


@router.post("/chat", response_model=AssistantTurnResponse)
async def chat(
    payload: ChatRequest,
    settings: Settings = Depends(get_app_settings),
    llm_service: LLMService = Depends(get_llm_service),
    voice_service: VoiceService = Depends(get_voice_service),
    emotion_service: EmotionService = Depends(get_emotion_service),
) -> AssistantTurnResponse:
    try:
        return await _run_assistant_flow(
            user_text=payload.text,
            speaker_id=payload.speaker_id,
            language=payload.language,
            generate_audio=payload.generate_audio,
            history=payload.history,
            settings=settings,
            llm_service=llm_service,
            voice_service=voice_service,
            emotion_service=emotion_service,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/chat-stream")
async def chat_stream(
    payload: ChatRequest,
    settings: Settings = Depends(get_app_settings),
    llm_service: LLMService = Depends(get_llm_service),
    voice_service: VoiceService = Depends(get_voice_service),
    emotion_service: EmotionService = Depends(get_emotion_service),
):
    async def stream_generator():
        full_text = ""
        try:
            async for chunk in llm_service.generate_reply_stream(
                user_text=payload.text,
                history=payload.history
            ):
                full_text += chunk
                # Yield text chunk to frontend immediately
                yield json.dumps({"type": "text", "content": chunk}) + "\n"

            # Once text is finished, detect emotion and synthesize audio
            emotion = emotion_service.detect(user_text=payload.text, assistant_text=full_text)
            yield json.dumps({"type": "emotion", "content": emotion}) + "\n"

            if payload.generate_audio and payload.speaker_id:
                try:
                    # Note: GPT has added '|' separators which voice_service or worker can handle
                    audio_path = await voice_service.synthesize(
                        text=full_text,
                        speaker_id=payload.speaker_id,
                        language=payload.language,
                    )
                    audio_url = _build_audio_url(settings, audio_path)
                    yield json.dumps({"type": "audio", "content": audio_url}) + "\n"
                except Exception as e:
                    print(f"Streaming audio synthesis failed: {e}")
                    yield json.dumps({"type": "error", "content": "Audio synthesis failed"}) + "\n"

            yield json.dumps({"type": "done"}) + "\n"

        except Exception as e:
            print(f"Stream error: {e}")
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"

    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")


def _parse_history_json(history_json: str | None) -> list[ChatMessage]:
    if not history_json:
        return []
    try:
        raw = json.loads(history_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid history_json") from exc
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="history_json must be a list")

    try:
        return [ChatMessage.model_validate(item) for item in raw]
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid history item: {exc}") from exc


@router.post("/transcribe-and-chat", response_model=AssistantTurnResponse)
async def transcribe_and_chat(
    audio: UploadFile = File(...),
    speaker_id: str | None = Form(default=None),
    language: str = Form(default="ru"),
    generate_audio: bool = Form(default=True),
    history_json: str | None = Form(default=None),
    settings: Settings = Depends(get_app_settings),
    stt_service: STTService = Depends(get_stt_service),
    llm_service: LLMService = Depends(get_llm_service),
    voice_service: VoiceService = Depends(get_voice_service),
    emotion_service: EmotionService = Depends(get_emotion_service),
) -> AssistantTurnResponse:
    # Relaxed validation: Allow if starts with audio/, is octet-stream, or has no type
    # Many clients (Flutter/Mobile) might send application/octet-stream
    valid_types = ["audio/", "application/octet-stream"]
    is_valid_type = not audio.content_type or any(audio.content_type.startswith(t) for t in valid_types)
    
    if not is_valid_type:
        raise HTTPException(status_code=400, detail=f"Only audio files are allowed. Got: {audio.content_type}")

    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    temp_path = settings.uploads_dir / f"{uuid4().hex}{suffix}"
    temp_path.write_bytes(await audio.read())

    if temp_path.stat().st_size == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Audio file is empty")

    history = _parse_history_json(history_json)

    try:
        user_text = await stt_service.transcribe(temp_path, language=language)
        return await _run_assistant_flow(
            user_text=user_text,
            speaker_id=speaker_id,
            language=language,
            generate_audio=generate_audio,
            history=history,
            settings=settings,
            llm_service=llm_service,
            voice_service=voice_service,
            emotion_service=emotion_service,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

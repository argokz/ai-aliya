from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.dependencies import get_voice_service
from app.schemas import SpeakerInfo, VoiceEnrollResponse
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/enroll", response_model=VoiceEnrollResponse)
async def enroll_voice(
    speaker_id: str = Form(...),
    audio: UploadFile = File(...),
    voice_service: VoiceService = Depends(get_voice_service),
) -> VoiceEnrollResponse:
    valid_types = ["audio/", "application/octet-stream"]
    is_valid_type = not audio.content_type or any(audio.content_type.startswith(t) for t in valid_types)
    
    if not is_valid_type:
        raise HTTPException(status_code=400, detail=f"Only audio files are allowed. Got: {audio.content_type}")

    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    try:
        path = await voice_service.store_reference_audio(
            speaker_id=speaker_id,
            filename=audio.filename or "reference.wav",
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return VoiceEnrollResponse(speaker_id=speaker_id, reference_audio=str(path))


@router.get("/speakers", response_model=list[SpeakerInfo])
async def list_speakers(
    voice_service: VoiceService = Depends(get_voice_service),
) -> list[SpeakerInfo]:
    return [
        SpeakerInfo(speaker_id=speaker_id, has_reference=has_reference)
        for speaker_id, has_reference in voice_service.list_speakers()
    ]

"""Whisper Worker Service for remote GPU transcription.

Запуск на удалённом ПК с GPU через Tailscale.
По умолчанию модель medium (оптимально для GTX 1660 Ti 6GB, 32GB RAM).
"""
import os
import logging
from pathlib import Path
from typing import Optional
import aiofiles
import aiohttp
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Whisper Worker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные переменные для модели
_whisper_model = None
_model_lock = None
_whisper_device = "cpu"  # фактическое устройство после загрузки (cuda/cpu)
_whisper_model_name = "medium"  # large-v3 тяжёлый для 6GB; medium оптимален для GTX 1660 Ti


class TranscriptionRequest(BaseModel):
    """Request model for transcription."""
    language: Optional[str] = None
    callback_url: Optional[str] = None  # URL для отправки результата (опционально)


class TranscriptionResponse(BaseModel):
    """Response model for transcription."""
    status: str
    segments: list[dict]
    language: str
    duration: float
    language_probability: float
    error: Optional[str] = None


def load_whisper_model():
    """Lazy load Whisper model. По умолчанию medium — оптимально для GTX 1660 Ti (6GB) и 32GB RAM."""
    global _whisper_model, _model_lock, _whisper_device, _whisper_model_name
    if _whisper_model is None:
        import asyncio
        from faster_whisper import WhisperModel
        
        model_name = os.getenv("WHISPER_MODEL", "medium")
        _whisper_model_name = model_name
        device = os.getenv("WHISPER_DEVICE", "cuda")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "float16")
        
        if device == "cuda":
            try:
                logger.info("Loading Whisper %s on CUDA (compute_type=%s)...", model_name, compute_type)
                _whisper_model = WhisperModel(
                    model_name,
                    device="cuda",
                    compute_type=compute_type,
                )
                _whisper_device = "cuda"
                logger.info("Whisper model %s loaded on CUDA", model_name)
            except Exception as e:
                logger.warning("Failed to load on CUDA: %s, falling back to CPU", e)
                device = "cpu"
                compute_type = "int8"
        
        if device == "cpu" or _whisper_model is None:
            logger.info("Loading Whisper %s on CPU...", model_name)
            _whisper_model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
            )
            _whisper_device = "cpu"
            logger.info("Whisper model %s loaded on CPU", model_name)
        
        _model_lock = asyncio.Lock()
    return _whisper_model, _model_lock


@app.get("/")
async def root():
    """Health check."""
    model_name = _whisper_model_name if _whisper_model is not None else os.getenv("WHISPER_MODEL", "medium")
    return {
        "status": "ok",
        "service": "whisper-worker",
        "model": model_name,
        "device": os.getenv("WHISPER_DEVICE", "cuda"),
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    try:
        model, _ = load_whisper_model()
        return {
            "status": "healthy",
            "model": _whisper_model_name,
            "device": _whisper_device,
            "model_loaded": model is not None,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    callback_url: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
):
    """
    Transcribe audio file using Whisper large-v3 on GPU.
    
    Args:
        file: Audio file to transcribe
        language: Optional language code (ru, kk, en) or None for auto-detect
        callback_url: Optional URL to send result to (async)
    """
    import asyncio
    import tempfile
    
    # Сохраняем файл во временную директорию
    temp_dir = Path("/tmp/whisper_worker")
    temp_dir.mkdir(exist_ok=True)
    
    with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, suffix=Path(file.filename).suffix) as tmp_file:
        tmp_path = Path(tmp_file.name)
        
        try:
            # Сохраняем загруженный файл
            async with aiofiles.open(tmp_path, "wb") as f:
                while chunk := await file.read(1024 * 1024):  # 1MB chunks
                    await f.write(chunk)
            
            logger.info(f"File saved: {tmp_path}, size: {tmp_path.stat().st_size} bytes")
            
            # Загружаем модель
            model, lock = load_whisper_model()
            
            # Транскрибируем
            async with lock:
                logger.info(f"Starting transcription: language={language}")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    _transcribe_sync,
                    str(tmp_path),
                    language,
                    model,
                )
            
            logger.info(f"Transcription completed: {len(result['segments'])} segments")
            
            # Если указан callback_url, отправляем результат асинхронно
            if callback_url and background_tasks:
                background_tasks.add_task(send_callback, callback_url, result)
            
            return TranscriptionResponse(
                status="success",
                segments=result["segments"],
                language=result["language"],
                duration=result["duration"],
                language_probability=result["language_probability"],
            )
            
        except Exception as e:
            logger.exception(f"Transcription failed: {e}")
            return TranscriptionResponse(
                status="error",
                segments=[],
                language="",
                duration=0.0,
                language_probability=0.0,
                error=str(e),
            )
        finally:
            # Удаляем временный файл
            try:
                tmp_path.unlink()
            except Exception:
                pass


def _transcribe_sync(audio_path: str, language: Optional[str], model) -> dict:
    """Synchronous transcription."""
    lang_map = {
        "kz": "kk",
        "kazakh": "kk",
    }
    whisper_lang = lang_map.get(language, language) if language else None
    
    # beam_size=1 и condition_on_previous_text=False сильно ускоряют (10 мин аудио — в разы быстрее)
    beam_size = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
    condition_previous = os.getenv("WHISPER_CONDITION_PREVIOUS", "false").lower() in ("1", "true", "yes")
    segments_generator, info = model.transcribe(
        audio_path,
        language=whisper_lang,
        task="transcribe",
        beam_size=beam_size,
        condition_on_previous_text=condition_previous,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=int(os.getenv("WHISPER_VAD_MIN_SILENCE_MS", "300")),
        ),
        word_timestamps=False,
    )
    
    segments = []
    for segment in segments_generator:
        segments.append({
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
        })
    
    # Длительность всего аудио (из faster_whisper), не только последнего сегмента
    duration = getattr(info, "duration", None)
    if duration is None and segments:
        duration = segments[-1]["end"]
    elif duration is None:
        duration = 0.0
    return {
        "segments": segments,
        "language": info.language,
        "duration": round(float(duration), 2),
        "language_probability": round(info.language_probability, 2),
    }


async def send_callback(callback_url: str, result: dict):
    """Send transcription result to callback URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                callback_url,
                json=result,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Callback sent successfully to {callback_url}")
                else:
                    logger.warning(f"Callback failed: {resp.status}")
    except Exception as e:
        logger.error(f"Error sending callback: {e}")


if __name__ == "__main__":
    import uvicorn
    # Получаем порт из переменной окружения или используем 8004
    port = int(os.getenv("WORKER_PORT", "8004"))
    host = os.getenv("WORKER_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)


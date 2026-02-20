from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import assistant, health, voice

settings = get_settings()

app = FastAPI(title=settings.app_name)

allow_origins = ["*"] if settings.cors_allow_origins == "*" else [
    item.strip() for item in settings.cors_allow_origins.split(",") if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    f"{settings.api_prefix}/voice/audio",
    StaticFiles(directory=settings.generated_audio_dir),
    name="generated-audio",
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(voice.router, prefix=settings.api_prefix)
app.include_router(assistant.router, prefix=settings.api_prefix)

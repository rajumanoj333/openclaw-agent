from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.audio_store import path_for
from app.services.voice_prompts import path_for as static_path_for

router = APIRouter(prefix="/audio", tags=["audio"])


def _safe(name: str) -> bool:
    return "/" not in name and "\\" not in name and ".." not in name


@router.get("/static/{name}")
async def serve_static(name: str):
    """Pre-generated voice prompts (greeting, language selection, etc.)."""
    if not _safe(name):
        raise HTTPException(404)
    base = name[:-4] if name.endswith(".mp3") else name
    path = static_path_for(base)
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="audio/mpeg", filename=name)


@router.get("/{name}")
async def serve_audio(name: str):
    """One-off TTS replies (TTL cached)."""
    if not _safe(name):
        raise HTTPException(404)
    path = path_for(name)
    if not path.is_file():
        raise HTTPException(404)
    media_type = "audio/wav" if name.endswith(".wav") else "audio/mpeg"
    return FileResponse(path, media_type=media_type, filename=name)

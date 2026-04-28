from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.audio_store import path_for

router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/{name}")
async def serve_audio(name: str):
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(404)
    path = path_for(name)
    if not path.is_file():
        raise HTTPException(404)
    media_type = "audio/wav" if name.endswith(".wav") else "audio/mpeg"
    return FileResponse(path, media_type=media_type, filename=name)

"""
GET /cameras - lists all configured camera sources and their live status, so
the frontend can build one video panel per camera dynamically.

POST /cameras/{id}/load_url - for a "custom" kind camera (see config.py):
downloads whatever video is at the given URL via yt-dlp (works for YouTube
links and most direct video URLs) and points that camera at the downloaded
file, replacing whatever it was showing before. This is a plain `def` (sync)
route - FastAPI runs it in a threadpool, so the (potentially long) download
doesn't block the rest of the API, same reasoning as POST /enroll.

POST /cameras/{id}/clear - stops a "custom" camera and deletes its
downloaded video file, resetting it back to the "nothing loaded yet" state.
"""
import logging
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.camera_manager import camera_manager
from app.schemas import CameraOut, LoadUrlRequest

logger = logging.getLogger("cameras")
router = APIRouter()


def _to_out(c) -> CameraOut:
    return CameraOut(id=c.id, label=c.label, kind=c.kind, is_running=c.is_running, error=c.error)


@router.get("/cameras", response_model=list[CameraOut])
def list_cameras():
    return [_to_out(c) for c in camera_manager.sources]


@router.post("/cameras/{source_id}/load_url", response_model=CameraOut)
def load_camera_from_url(source_id: str, req: LoadUrlRequest):
    cam = camera_manager.get(source_id)
    if cam is None:
        raise HTTPException(404, f"Unknown camera source '{source_id}'. See GET /cameras for valid ids.")
    if cam.kind != "custom":
        raise HTTPException(400, f"Camera '{source_id}' is a fixed source, not a custom/URL-loaded one.")
    if shutil.which("yt-dlp") is None:
        raise HTTPException(500, "yt-dlp is not installed on the server (needed to download video URLs).")

    dest_dir = Path(settings.CUSTOM_VIDEO_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Clear any previous download for this camera id first (extension can
    # vary between videos, so a plain overwrite by name isn't reliable).
    for old in dest_dir.glob(f"{source_id}.*"):
        old.unlink()

    dest_template = str(dest_dir / f"{source_id}.%(ext)s")
    try:
        subprocess.run(
            [
                "yt-dlp", "-f", "best[height<=720]/bestvideo[height<=720]+bestaudio/best",
                "--merge-output-format", "mp4",
                "-o", dest_template, req.url,
            ],
            check=True, capture_output=True, text=True,
            timeout=settings.CUSTOM_VIDEO_DOWNLOAD_TIMEOUT_SEC,
        )
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or str(e))[-500:]
        cam.error = f"Failed to download video: {detail}"
        logger.error(f"yt-dlp failed for '{source_id}' <- {req.url}: {detail}")
        return _to_out(cam)
    except subprocess.TimeoutExpired:
        cam.error = (
            f"Download timed out after {settings.CUSTOM_VIDEO_DOWNLOAD_TIMEOUT_SEC:.0f}s "
            f"- try a shorter video or check the connection."
        )
        return _to_out(cam)

    downloaded = list(dest_dir.glob(f"{source_id}.*"))
    if not downloaded:
        cam.error = "yt-dlp reported success but no output file was found."
        return _to_out(cam)

    cam.reconfigure(str(downloaded[0]))
    logger.info(f"Camera '{source_id}' loaded from URL {req.url} -> {downloaded[0]}")
    return _to_out(cam)


@router.post("/cameras/{source_id}/clear", response_model=CameraOut)
def clear_camera(source_id: str):
    """Stops a "custom" camera and deletes its downloaded video, resetting
    it back to the "paste a URL" state."""
    cam = camera_manager.get(source_id)
    if cam is None:
        raise HTTPException(404, f"Unknown camera source '{source_id}'. See GET /cameras for valid ids.")
    if cam.kind != "custom":
        raise HTTPException(400, f"Camera '{source_id}' is a fixed source, not a custom/URL-loaded one.")

    cam.clear()

    dest_dir = Path(settings.CUSTOM_VIDEO_DIR)
    for old in dest_dir.glob(f"{source_id}.*"):
        old.unlink()

    logger.info(f"Camera '{source_id}' cleared.")
    return _to_out(cam)

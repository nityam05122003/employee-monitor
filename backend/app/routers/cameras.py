"""GET /cameras - lists all configured camera sources and their live status,
so the frontend can build one video panel per camera dynamically."""
from fastapi import APIRouter

from app.camera_manager import camera_manager
from app.schemas import CameraOut

router = APIRouter()


@router.get("/cameras", response_model=list[CameraOut])
def list_cameras():
    return [
        CameraOut(id=c.id, label=c.label, is_running=c.is_running, error=c.error)
        for c in camera_manager.sources
    ]

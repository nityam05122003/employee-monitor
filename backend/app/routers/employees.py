"""
Enrollment + employee listing.

POST /enroll captures face shots from one of the SHARED camera feeds (the
backend owns each configured camera via CameraWorker - see camera_manager.py)
rather than accepting uploaded images from the browser. That's why this is a
plain `def` (sync) route: FastAPI runs sync routes in a threadpool, so the
few seconds of time.sleep() while sampling shots doesn't block the rest of
the API.
"""
import json
import logging
import time

from fastapi import APIRouter, HTTPException
from sqlalchemy import func

from app.config import settings
from app.database import SessionLocal
from app.models import Employee, FaceEmbedding
from app.camera_manager import camera_manager
from app.face_engine import face_engine
from app.recognition_service import recognition_worker
from app.schemas import EnrollRequest, EnrollResponse, EmployeeOut

logger = logging.getLogger("employees")
router = APIRouter()


def _pick_enroll_camera(source_id: str = None):
    if source_id is not None:
        cam = camera_manager.get(source_id)
        if cam is None:
            raise HTTPException(404, f"Unknown camera source '{source_id}'. See GET /cameras for valid ids.")
        return cam
    for cam in camera_manager.sources:
        if cam.is_running:
            return cam
    return None


@router.post("/enroll", response_model=EnrollResponse)
def enroll_employee(req: EnrollRequest):
    cam = _pick_enroll_camera(req.source_id)
    if cam is None or not cam.is_running:
        raise HTTPException(503, "No running camera is available to enroll from - check GET /cameras and the server logs.")
    if not face_engine.ready:
        raise HTTPException(503, "Face recognition model is still loading - try again in a moment.")

    db = SessionLocal()
    try:
        employee = db.query(Employee).filter(Employee.employee_code == req.employee_code).first()
        if employee is None:
            employee = Employee(employee_code=req.employee_code, name=req.name)
            db.add(employee)
            db.commit()
            db.refresh(employee)
        else:
            employee.name = req.name
            db.commit()

        captured = 0
        for shot_idx in range(settings.ENROLL_SHOTS):
            face = None
            for _ in range(settings.ENROLL_MAX_RETRIES_PER_SHOT):
                frame = cam.worker.get_latest_frame()
                if frame is not None:
                    faces = face_engine.detect(frame)
                    if faces:
                        # Largest bounding box = closest/most prominent face -
                        # avoids accidentally enrolling a background face.
                        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
                        break
                time.sleep(settings.ENROLL_RETRY_SLEEP_SEC)

            if face is None:
                logger.warning(
                    f"Enroll shot {shot_idx + 1}/{settings.ENROLL_SHOTS} for "
                    f"{req.employee_code}: no face detected, skipping this shot."
                )
                continue

            db.add(FaceEmbedding(
                employee_id=employee.id,
                embedding=json.dumps(face.normed_embedding.tolist()),
            ))
            db.commit()
            captured += 1
            time.sleep(settings.ENROLL_CAPTURE_INTERVAL_SEC)

        if captured == 0:
            raise HTTPException(
                400,
                "No face was detected during enrollment. Make sure your face "
                "is clearly visible and well-lit in front of the webcam, then try again.",
            )

        recognition_worker.reload_known_embeddings()

        return EnrollResponse(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            name=employee.name,
            embeddings_captured=captured,
            shots_attempted=settings.ENROLL_SHOTS,
        )
    finally:
        db.close()


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees():
    db = SessionLocal()
    try:
        rows = (
            db.query(Employee, func.count(FaceEmbedding.id))
            .outerjoin(FaceEmbedding, FaceEmbedding.employee_id == Employee.id)
            .group_by(Employee.id)
            .all()
        )
        return [
            EmployeeOut(
                id=emp.id,
                employee_code=emp.employee_code,
                name=emp.name,
                created_at=emp.created_at,
                embeddings_count=count,
            )
            for emp, count in rows
        ]
    finally:
        db.close()

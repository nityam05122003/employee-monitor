"""
FastAPI app: boots the DB, all configured cameras, and the face model at
startup, exposes per-camera MJPEG video feeds, WebSocket live-push, and
includes the employees/attendance/alerts/cameras routers.
"""
import asyncio
import logging
import os
import time

import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.camera_manager import camera_manager
from app.face_engine import face_engine
from app.recognition_service import recognition_worker
from app.ws_manager import ws_manager
from app.routers import employees, attendance, alerts, cameras

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title="Employee Monitor - Prototype")

# Allows the Vite dev server (added in Phase 6) to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employees.router, tags=["employees"])
app.include_router(attendance.router, tags=["attendance"])
app.include_router(alerts.router, tags=["alerts"])
app.include_router(cameras.router, tags=["cameras"])

# Serves saved alert snapshot images, e.g. GET /snapshots/alert_20260101_120000_000000.jpg
os.makedirs(settings.SNAPSHOT_DIR, exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=settings.SNAPSHOT_DIR), name="snapshots")


@app.on_event("startup")
def on_startup():
    # Captured now so the recognition worker's background thread can safely
    # push WebSocket broadcasts onto THIS loop via run_coroutine_threadsafe.
    ws_manager.set_event_loop(asyncio.get_event_loop())

    init_db()

    # Every configured camera starts independently - if one fails (e.g. a
    # CCTV URL that isn't reachable yet), the others keep running.
    camera_manager.start_all()

    try:
        face_engine.load(settings.INSIGHTFACE_MODEL_NAME)
    except Exception as e:
        logger.error(
            f"InsightFace model failed to load: {e}\n"
            f"This usually means no internet connection (needed to download "
            f"the {settings.INSIGHTFACE_MODEL_NAME} model on first run) or a "
            f"missing dependency. Recognition is disabled until this is "
            f"fixed; the raw video feed(s) will still work."
        )

    if face_engine.ready:
        recognition_worker.start()
    else:
        logger.warning(
            "Recognition loop NOT started (face model not ready). "
            "Video feeds will show the raw (unannotated) footage for now."
        )


@app.on_event("shutdown")
def on_shutdown():
    recognition_worker.stop()
    camera_manager.stop_all()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.websocket("/live")
async def websocket_live(websocket: WebSocket):
    """Pushes {"type": "attendance"|"alert", "payload": {...}} events live -
    see ws_manager.py for how the background recognition thread bridges into
    this coroutine's event loop."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # We never expect the client to send anything meaningful; this
            # just blocks until the client disconnects (or sends something).
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


def _mjpeg_generator(cam):
    """Yields JPEG frames as a multipart/x-mixed-replace stream for ONE
    camera source. Prefers the annotated frame (boxes + name/unknown labels)
    produced by the recognition loop; falls back to the raw camera frame if
    recognition isn't running yet (e.g. face model still loading)."""
    frame_interval = 1.0 / settings.MJPEG_FPS
    while True:
        frame = cam.get_annotated() if recognition_worker.is_running else None
        if frame is None:
            frame = cam.worker.get_latest_frame()
        if frame is None:
            time.sleep(frame_interval)
            continue

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )
        time.sleep(frame_interval)


@app.get("/video_feed/{source_id}")
def video_feed(source_id: str):
    cam = camera_manager.get(source_id)
    if cam is None:
        raise HTTPException(404, f"Unknown camera source '{source_id}'. See GET /cameras for valid ids.")
    return StreamingResponse(
        _mjpeg_generator(cam),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/video_feed")
def video_feed_default():
    """Back-compat alias: streams the FIRST configured camera source."""
    if not camera_manager.sources:
        raise HTTPException(404, "No camera sources configured.")
    return StreamingResponse(
        _mjpeg_generator(camera_manager.sources[0]),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

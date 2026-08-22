"""
Manages one CameraWorker per configured video source (CAMERA_SOURCES in
config.py) - laptop webcam, WiFi/CCTV cameras, and/or video files can all run
simultaneously. Each source starts independently; if one fails (e.g. a CCTV
camera that isn't reachable), the others keep running rather than the whole
backend failing to start.

Also holds each camera's current ANNOTATED frame (boxes/labels drawn by
recognition_service.py), separately from CameraWorker's raw frame buffer, so
each camera gets its own /video_feed/{id} panel on the dashboard.
"""
import logging
import threading

from app.config import settings
from app.camera import CameraWorker

logger = logging.getLogger("camera_manager")


class CameraSource:
    def __init__(self, source_id: str, label: str, source: str):
        self.id = source_id
        self.label = label
        self.worker = CameraWorker(source=source)
        self.error = None  # set if start() failed - other sources still run fine

        self._annotated_lock = threading.Lock()
        self._latest_annotated = None

    def start(self):
        try:
            self.worker.start()
            self.error = None
        except RuntimeError as e:
            self.error = str(e)
            logger.error(f"Camera '{self.id}' ({self.label}) failed to start: {e}")

    def stop(self):
        self.worker.stop()

    @property
    def is_running(self) -> bool:
        return self.worker.is_running

    def set_annotated(self, frame):
        with self._annotated_lock:
            self._latest_annotated = frame

    def get_annotated(self):
        with self._annotated_lock:
            return None if self._latest_annotated is None else self._latest_annotated.copy()


class CameraManager:
    def __init__(self):
        self.sources = [
            CameraSource(cfg.id, cfg.label, cfg.source) for cfg in settings.CAMERA_SOURCES
        ]

    def start_all(self):
        for src in self.sources:
            src.start()
        running = [s.id for s in self.sources if s.is_running]
        failed = [s.id for s in self.sources if not s.is_running]
        logger.info(f"Cameras started: {running or 'none'}; failed: {failed or 'none'}")

    def stop_all(self):
        for src in self.sources:
            src.stop()

    def get(self, source_id: str) -> "CameraSource | None":
        for src in self.sources:
            if src.id == source_id:
                return src
        return None


# Single shared instance.
camera_manager = CameraManager()

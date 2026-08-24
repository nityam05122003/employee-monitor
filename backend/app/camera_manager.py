"""
Manages one CameraWorker per configured video source (CAMERA_SOURCES in
config.py) - laptop webcam, WiFi/CCTV cameras, and/or video files can all run
simultaneously. Each source starts independently; if one fails (e.g. a CCTV
camera that isn't reachable), the others keep running rather than the whole
backend failing to start.

Also holds each camera's current ANNOTATED frame (boxes/labels drawn by
recognition_service.py), separately from CameraWorker's raw frame buffer, so
each camera gets its own /video_feed/{id} panel on the dashboard.

"custom" kind sources (see CameraSourceConfig) start with an empty source and
stay unconfigured until reconfigure() points them at a downloaded video file
(see routers/cameras.py's POST /cameras/{id}/load_url) - the recognition loop
picks them up automatically on its next tick since it always iterates the
live `camera_manager.sources` list.
"""
import logging
import threading

from app.config import settings
from app.camera import CameraWorker

logger = logging.getLogger("camera_manager")


class CameraSource:
    def __init__(self, source_id: str, label: str, source: str, kind: str = "static"):
        self.id = source_id
        self.label = label
        self.kind = kind
        self.worker = CameraWorker(source=source)
        self.error = None  # set if start() failed - other sources still run fine

        self._annotated_lock = threading.Lock()
        self._latest_annotated = None

    def start(self):
        if not self.worker.source:
            # "custom" source with nothing loaded yet - not an error, just
            # waiting for a POST /cameras/{id}/load_url call.
            return
        try:
            self.worker.start()
            self.error = None
        except RuntimeError as e:
            self.error = str(e)
            logger.error(f"Camera '{self.id}' ({self.label}) failed to start: {e}")

    def stop(self):
        self.worker.stop()

    def reconfigure(self, new_source: str, new_label: str = None):
        """Swaps in a new underlying video source (e.g. a freshly downloaded
        file for a "custom" camera) - stops the old worker, if any, and
        starts a fresh one pointed at new_source."""
        self.stop()
        if new_label is not None:
            self.label = new_label
        self.worker = CameraWorker(source=new_source)
        self.start()

    def clear(self):
        """Resets a "custom" camera back to unconfigured (no video loaded) -
        stops it and clears any leftover error, ready for a fresh
        POST /cameras/{id}/load_url."""
        self.stop()
        self.worker = CameraWorker(source="")
        self.error = None

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
            CameraSource(cfg.id, cfg.label, cfg.source, cfg.kind) for cfg in settings.CAMERA_SOURCES
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

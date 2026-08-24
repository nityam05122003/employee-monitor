"""
CameraWorker owns ONE video source via OpenCV and continuously reads frames
into a lock-protected buffer on a background thread. camera_manager.py
creates one CameraWorker per configured CAMERA_SOURCES entry, so multiple
sources (webcam + CCTV + video files) can all run at once - each source is
still only ever opened once, by its own CameraWorker.

Each source string can be:
  - a plain index like "0" or "1"                        -> local webcam device
  - a URL like "rtsp://user:pass@192.168.1.50:554/..."    -> WiFi/network CCTV
    camera, opened via OpenCV's FFMPEG backend
  - a path to a video file, e.g. "data/test_videos/x.mp4" -> pre-recorded
    footage (handy for testing without a real camera - loops automatically)

Network cameras drop connections far more often than a local webcam (WiFi
hiccups, camera reboots, router issues), so for network sources this also
runs a reconnect watchdog: if no frame has arrived for
CAMERA_RECONNECT_AFTER_SEC, the stream is released and reopened automatically.
Video files instead loop back to the start the instant they hit EOF, and are
paced to the file's own frame rate so playback (and what the recognition
loop sees) runs at roughly real-time speed rather than as fast as decode allows.
"""
import os
import threading
import time
import logging

import cv2

from app.config import settings

logger = logging.getLogger("camera")


def _source_kind(source: str) -> str:
    if source.isdigit():
        return "webcam"
    if source.startswith(("rtsp://", "http://", "https://")):
        return "network"
    return "file"


class CameraWorker:
    def __init__(self, source: str = ""):
        self.source = source
        self._kind = _source_kind(self.source) if self.source else None
        self._cap = None
        self._lock = threading.Lock()
        self._latest_frame = None
        self._last_frame_at = None
        self._file_frame_interval = None  # only set for "file" sources
        self._running = False
        self._thread = None

    def _open_capture(self):
        if self._kind == "network":
            # CAP_FFMPEG handles RTSP/HTTP network streams reliably.
            return cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
        if self._kind == "file":
            return cv2.VideoCapture(self.source)
        return cv2.VideoCapture(int(self.source))

    def start(self):
        if self._kind == "file" and not os.path.exists(self.source):
            raise RuntimeError(f"Video file '{self.source}' does not exist.")

        self._cap = self._open_capture()

        if not self._cap.isOpened():
            if self._kind == "network":
                hint = (
                    "Common causes:\n"
                    "  - Wrong RTSP URL/port, or wrong username/password for the camera\n"
                    "  - This machine isn't on the same network as the camera\n"
                    "  - The camera's RTSP service is disabled (check its app/web settings)"
                )
            elif self._kind == "file":
                hint = "The file exists but OpenCV/FFMPEG couldn't open it - check it's a valid, non-corrupt video file."
            else:
                hint = (
                    "Common causes:\n"
                    "  - Another app (Zoom, FaceTime, etc.) is already using the camera\n"
                    "  - Wrong CAMERA_SOURCE in .env (try 0 or 1)\n"
                    "  - macOS camera permission not granted to this terminal app: "
                    "System Settings -> Privacy & Security -> Camera"
                )
            raise RuntimeError(f"Could not open video source '{self.source}'. {hint}")

        # Do one read to make sure frames are actually flowing (isOpened() can
        # return True even when the source is bad and reads silently fail).
        ok, frame = self._cap.read()
        if not ok or frame is None:
            self._cap.release()
            if self._kind == "network":
                hint = (
                    "The connection opened but sent no video - double check the "
                    "stream path (RTSP URLs vary by camera brand/model, e.g. "
                    "/stream1, /h264Preview_01_main, /live/ch0) in the camera's "
                    "manual or app."
                )
            elif self._kind == "file":
                hint = "The file opened but returned no frames - it may be empty or use an unsupported codec."
            else:
                hint = (
                    "This usually means macOS denied camera access to this "
                    "terminal app. Check System Settings -> Privacy & Security -> "
                    "Camera and grant access, then restart."
                )
            raise RuntimeError(f"Video source '{self.source}' opened but returned no frame. {hint}")

        self._latest_frame = frame
        self._last_frame_at = time.time()

        if self._kind == "file":
            fps = self._cap.get(cv2.CAP_PROP_FPS)
            self._file_frame_interval = (1.0 / fps) if fps and fps > 0 else (1.0 / 25)
            # Rewind - the read() above already consumed frame 0.
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info(f"Camera source '{self.source}' started (kind={self._kind}).")

    def _capture_loop(self):
        while self._running:
            ok, frame = self._cap.read()
            now = time.time()

            if ok and frame is not None:
                with self._lock:
                    self._latest_frame = frame
                self._last_frame_at = now
                if self._kind == "file":
                    time.sleep(self._file_frame_interval)
            elif self._kind == "file":
                # End of the video file - loop back to the start immediately.
                logger.info(f"Video file '{self.source}' reached the end - looping.")
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            else:
                time.sleep(0.1)  # transient read failure, avoid busy-spin

            if self._kind == "network" and (now - self._last_frame_at) > settings.CAMERA_RECONNECT_AFTER_SEC:
                logger.warning(
                    f"No frame from '{self.source}' for over "
                    f"{settings.CAMERA_RECONNECT_AFTER_SEC:.0f}s - reconnecting..."
                )
                self._reconnect()

    def _reconnect(self):
        try:
            self._cap.release()
        except Exception:
            pass
        try:
            self._cap = self._open_capture()
        except Exception as e:
            logger.error(f"Reconnect to '{self.source}' raised: {e}")
            time.sleep(settings.CAMERA_RECONNECT_AFTER_SEC)
            return

        if self._cap.isOpened():
            self._last_frame_at = time.time()  # grace period for frames to start flowing again
            logger.info(f"Reconnected to '{self.source}'.")
        else:
            logger.error(f"Reconnect to '{self.source}' failed - will retry.")
            time.sleep(settings.CAMERA_RECONNECT_AFTER_SEC)

    def get_latest_frame(self):
        """Returns the most recent raw frame, or None if not yet available."""
        with self._lock:
            return None if self._latest_frame is None else self._latest_frame.copy()

    @property
    def is_running(self) -> bool:
        return self._running

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._cap is not None:
            self._cap.release()
        logger.info("Camera stopped.")

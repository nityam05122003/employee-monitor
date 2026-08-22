"""
All tunable knobs live here, loaded from environment variables / a .env file.
Tune RECOGNITION_THRESHOLD and DETECTION_INTERVAL_SEC first when adjusting for
your webcam/lighting once recognition is added in Phase 2.
"""
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class CameraSourceConfig(BaseModel):
    id: str          # short slug, used in URLs like /video_feed/{id} - keep it simple (letters/numbers/underscore)
    label: str        # human-readable name shown in the dashboard
    source: str       # "0"/"1" (local webcam) | "rtsp://..." (network CCTV) | a video file path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- Cameras ---
    # Every configured source runs simultaneously (its own capture thread,
    # its own /video_feed/{id} panel on the dashboard) - attendance/idle/alert
    # state is still tracked per PERSON globally across all of them (see
    # recognition_service.py), not per-camera, since one person is one person
    # regardless of which camera happens to see them.
    #
    # Set via CAMERA_SOURCES as a JSON array in .env, e.g.:
    #   CAMERA_SOURCES=[{"id":"laptop","label":"Laptop Webcam","source":"0"},
    #                   {"id":"cctv","label":"Office CCTV","source":"rtsp://user:pass@192.168.1.50:554/stream1"}]
    CAMERA_SOURCES: list[CameraSourceConfig] = [
        CameraSourceConfig(id="laptop", label="Laptop Webcam", source="0"),
    ]
    # If a network camera stops delivering frames for this long, the backend
    # automatically releases and reopens the stream (WiFi cameras drop
    # connections far more often than a local webcam ever does).
    CAMERA_RECONNECT_AFTER_SEC: float = 5.0

    # --- Recognition (used starting Phase 2) ---
    DETECTION_INTERVAL_SEC: float = 0.3       # throttle: ~3fps face detection/recognition
    RECOGNITION_THRESHOLD: float = 0.45       # cosine similarity match threshold
    INSIGHTFACE_MODEL_NAME: str = "buffalo_l"
    # Detector input size (square) - raise this (e.g. 960 or 1280) for CCTV
    # footage where faces are small/far away; higher = better far-face
    # detection but slower per-frame. 640 is a good default for a close
    # laptop webcam.
    DETECTION_SIZE: int = 640
    # Minimum detector confidence to count as a face at all - lower this
    # (e.g. 0.3) to catch more small/blurry far-away faces, at the cost of
    # more false detections.
    DET_THRESH: float = 0.5

    # --- Enrollment (Phase 2) ---
    ENROLL_SHOTS: int = 4                     # number of face shots to capture per enrollment
    ENROLL_CAPTURE_INTERVAL_SEC: float = 1.0  # pause between shots so pose/lighting varies a bit
    ENROLL_MAX_RETRIES_PER_SHOT: int = 8       # retries if no face found in a given shot slot
    ENROLL_RETRY_SLEEP_SEC: float = 0.3

    # --- Attendance / alerts (used starting Phase 3/4) ---
    UNKNOWN_ALERT_SECONDS: float = 3.0        # unknown face must persist this long to alert
    ALERT_COOLDOWN_SECONDS: float = 30.0      # min gap between repeat alerts

    # --- Idle / "relaxing" detection ---
    # Heuristic only: a webcam can't know if someone is actually working, just
    # whether their face is present and which way it's pointing. Two things
    # count as idle time for an already-checked-in employee: face not visible
    # at all ("away"), or face visible but turned away from the screen beyond
    # these yaw/pitch thresholds ("distracted" - e.g. looking down at a phone).
    # Laptop webcams sit below eye level, so normal screen-facing pitch is
    # already noticeably non-zero (~20-25 deg looking down at the screen) -
    # these thresholds have headroom for that; tune per your own camera angle.
    HEAD_YAW_THRESHOLD_DEG: float = 35.0
    HEAD_PITCH_THRESHOLD_DEG: float = 35.0
    IDLE_ALERT_SECONDS: float = 60.0          # continuous idle time before alerting
    IDLE_ALERT_COOLDOWN_SECONDS: float = 120.0  # min gap between repeat idle alerts per employee

    # --- Video streaming ---
    MJPEG_FPS: int = 15

    # --- Storage ---
    DATABASE_URL: str = "sqlite:///./data/app.db"
    SNAPSHOT_DIR: str = "./data/snapshots"


settings = Settings()

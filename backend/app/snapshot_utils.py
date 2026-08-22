"""Shared snapshot-saving helper, used by both alert_service.py
(unauthorized-face alerts) and idle_service.py (employee-idle alerts)."""
import datetime
import logging
import os

import cv2

from app.config import settings

logger = logging.getLogger("snapshot")

os.makedirs(settings.SNAPSHOT_DIR, exist_ok=True)


def save_snapshot(frame, timestamp: datetime.datetime, prefix: str) -> str | None:
    """Saves frame as a JPEG in SNAPSHOT_DIR and returns just the filename
    (not the full path - it's served via the /snapshots static mount, see
    main.py), or None if there was no frame or the save failed."""
    if frame is None:
        return None

    filename = f"{prefix}_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    full_path = os.path.join(settings.SNAPSHOT_DIR, filename)
    if not cv2.imwrite(full_path, frame):
        logger.warning(f"Failed to save snapshot to {full_path}")
        return None
    return filename

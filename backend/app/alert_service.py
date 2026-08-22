"""
Unknown-face ("unauthorized person") alert logic.

Approximation (no cross-frame face tracking/re-identification in this
prototype): a single rolling "unknown streak" is tracked rather than
per-person timers. Each recognition tick reports whether >=1 unmatched face
was seen. If that has been true on every tick continuously for
UNKNOWN_ALERT_SECONDS, ONE alert fires (+ a snapshot is saved), then
ALERT_COOLDOWN_SECONDS must pass before another alert can fire even if the
unknown face is still there - this avoids spamming an alert per tick.

Known limitation (documented, not a bug): this can't tell "one person
lingering" apart from "two different unknown people back to back" - real
identity tracking across frames is out of scope for the prototype.

See idle_service.py for the separate "employee has been idle/away too long"
alert type - both share the alerts table (distinguished by alert_type).
"""
import datetime
import logging
import threading

from app.config import settings
from app.database import SessionLocal
from app.models import Alert
from app.snapshot_utils import save_snapshot

logger = logging.getLogger("alerts")


class AlertTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._unknown_streak_start = None  # datetime the current streak began, or None
        self._last_alert_at = None         # datetime of the last fired alert, or None

    def report_tick(self, unknown_seen: bool, frame_for_snapshot=None, source_id: str = None):
        """Call once per recognition round (across all cameras combined).
        Returns a dict payload (ready for the API/WS response) if an alert
        fired this round, else None. source_id is whichever camera had the
        unknown face, for display only."""
        now = datetime.datetime.now()

        with self._lock:
            if not unknown_seen:
                self._unknown_streak_start = None
                return None

            if self._unknown_streak_start is None:
                self._unknown_streak_start = now

            streak_duration = (now - self._unknown_streak_start).total_seconds()
            if streak_duration < settings.UNKNOWN_ALERT_SECONDS:
                return None

            if self._last_alert_at is not None:
                since_last = (now - self._last_alert_at).total_seconds()
                if since_last < settings.ALERT_COOLDOWN_SECONDS:
                    return None

            self._last_alert_at = now

        # DB write + disk I/O done outside the lock.
        return self._fire_alert(now, frame_for_snapshot, source_id)

    def _fire_alert(self, timestamp: datetime.datetime, frame, source_id: str):
        snapshot_filename = save_snapshot(frame, timestamp, prefix="alert")

        db = SessionLocal()
        try:
            alert = Alert(
                timestamp=timestamp, snapshot_path=snapshot_filename, status="new",
                alert_type="unauthorized_face", employee_id=None, source_id=source_id,
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            logger.warning(f"ALERT #{alert.id} (unauthorized_face) fired at {timestamp.isoformat()} (source={source_id}, snapshot={snapshot_filename})")
            return {
                "id": alert.id,
                "timestamp": alert.timestamp,
                "snapshot_path": alert.snapshot_path,
                "status": alert.status,
                "alert_type": alert.alert_type,
                "employee_id": None,
                "employee_name": None,
                "employee_code": None,
                "source_id": source_id,
            }
        finally:
            db.close()


# Single shared instance.
alert_tracker = AlertTracker()

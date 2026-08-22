"""
Per-employee idle/"relaxing" tracking.

Heuristic only - a webcam can't know if someone is actually working, just
whether their face is present and which way it's pointing. Two things count
as idle time for an already-checked-in employee (see
attendance_service.get_checked_in_employee_ids_today):

  - "away"       - face not visible to the camera at all
  - "distracted" - face visible but head turned away from the screen beyond
                   HEAD_YAW_THRESHOLD_DEG / HEAD_PITCH_THRESHOLD_DEG (e.g.
                   looking down at a phone, turned to talk to someone)

Both accumulate into the same per-day idle_seconds total. Once one employee's
continuous idle streak crosses IDLE_ALERT_SECONDS, ONE alert fires (type
"employee_idle", + a snapshot), then IDLE_ALERT_COOLDOWN_SECONDS must pass
before another fires for THAT employee even if still idle - same
streak+cooldown pattern as alert_service.py's unknown-face alerts, just
tracked per-employee instead of as one global streak.

Known false-positive sources (documented, not bugs): glancing at a second
monitor, reading a physical document, or talking to a coworker will all look
like "distracted" - tune the thresholds in config.py if this fires too often.
"""
import datetime
import logging
import threading

from app.config import settings
from app.database import SessionLocal
from app.models import Alert, Employee
from app.snapshot_utils import save_snapshot
from app import attendance_service

logger = logging.getLogger("idle")


class _EmployeeIdleState:
    __slots__ = ("streak_start", "reason", "last_alert_at")

    def __init__(self):
        self.streak_start = None   # datetime the current idle streak began, or None
        self.reason = None         # "away" | "distracted"
        self.last_alert_at = None  # datetime of the last fired alert for this employee, or None


class IdleTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._state: dict[int, _EmployeeIdleState] = {}

    def report_tick(
        self, employee_id: int, is_idle: bool, reason: str, tick_seconds: float,
        frame_for_snapshot=None, source_id: str = None,
    ):
        """Call once per recognition round (across all cameras combined) for
        every checked-in employee. Returns a dict payload if an idle alert
        fired this round, else None. source_id is whichever camera last saw
        them (only meaningful when reason="distracted" - "away" means no
        camera saw them at all), for display only."""
        now = datetime.datetime.now()

        with self._lock:
            state = self._state.setdefault(employee_id, _EmployeeIdleState())

            if not is_idle:
                state.streak_start = None
                state.reason = None
                return None

            attendance_service.add_idle_seconds(employee_id, tick_seconds, at=now)

            if state.streak_start is None:
                state.streak_start = now
            state.reason = reason

            streak_duration = (now - state.streak_start).total_seconds()
            if streak_duration < settings.IDLE_ALERT_SECONDS:
                return None

            if state.last_alert_at is not None:
                since_last = (now - state.last_alert_at).total_seconds()
                if since_last < settings.IDLE_ALERT_COOLDOWN_SECONDS:
                    return None

            state.last_alert_at = now
            current_reason = state.reason

        return self._fire_alert(employee_id, now, current_reason, frame_for_snapshot, source_id)

    def _fire_alert(self, employee_id: int, timestamp: datetime.datetime, reason: str, frame, source_id: str):
        snapshot_filename = save_snapshot(frame, timestamp, prefix="idle")

        db = SessionLocal()
        try:
            employee = db.query(Employee).filter(Employee.id == employee_id).first()
            alert = Alert(
                timestamp=timestamp, snapshot_path=snapshot_filename, status="new",
                alert_type="employee_idle", employee_id=employee_id, source_id=source_id,
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)

            name = employee.name if employee else None
            code = employee.employee_code if employee else None
            logger.warning(
                f"ALERT #{alert.id} (employee_idle): {name} ({code}) has been "
                f"{reason} for {settings.IDLE_ALERT_SECONDS:.0f}s+ (source={source_id}, snapshot={snapshot_filename})"
            )
            return {
                "id": alert.id,
                "timestamp": alert.timestamp,
                "snapshot_path": alert.snapshot_path,
                "status": alert.status,
                "alert_type": alert.alert_type,
                "employee_id": employee_id,
                "employee_name": name,
                "employee_code": code,
                "reason": reason,
                "source_id": source_id,
            }
        finally:
            db.close()


# Single shared instance.
idle_tracker = IdleTracker()

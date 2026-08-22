"""
Attendance write-side logic.

- record_sighting(): called by the recognition loop every time a face is
  matched to an employee. First sighting of the day -> creates the
  attendance_daily row (entry_time = now) and a matching AttendanceEvent
  "entry" row. Every later sighting that same day just bumps last_seen_time.
- close_day(): converts each employee's last_seen_time into a formal "exit"
  AttendanceEvent - either called on demand (POST /attendance/close_day) or
  you could later wire it to a scheduler (out of scope for this prototype).

Uses local wall-clock time (not UTC) since "today" for a physical
attendance log should match the clock on the wall, not a UTC day boundary.
"""
import datetime
import logging

from app.database import SessionLocal
from app.models import AttendanceDaily, AttendanceEvent, Employee

logger = logging.getLogger("attendance")


def record_sighting(employee_id: int, seen_at: datetime.datetime = None, source_id: str = None):
    """Returns a dict describing the new entry (for WS broadcast) if this
    sighting created today's first entry for this employee, else None.
    source_id (which configured camera saw them - see camera_manager.py) is
    informational only, stored for display, and doesn't affect the logic."""
    seen_at = seen_at or datetime.datetime.now()
    today = seen_at.date()

    db = SessionLocal()
    try:
        row = (
            db.query(AttendanceDaily)
            .filter(AttendanceDaily.employee_id == employee_id, AttendanceDaily.date == today)
            .first()
        )
        if row is None:
            row = AttendanceDaily(
                employee_id=employee_id, date=today,
                entry_time=seen_at, last_seen_time=seen_at, last_seen_source=source_id,
            )
            db.add(row)
            db.add(AttendanceEvent(
                employee_id=employee_id, event_type="entry", timestamp=seen_at, source_id=source_id,
            ))
            db.commit()
            logger.info(f"ENTRY logged for employee_id={employee_id} at {seen_at.isoformat()} (source={source_id})")

            employee = db.query(Employee).filter(Employee.id == employee_id).first()
            return {
                "employee_id": employee_id,
                "employee_code": employee.employee_code,
                "name": employee.name,
                "entry_time": seen_at,
                "source_id": source_id,
            }
        else:
            row.last_seen_time = seen_at
            row.last_seen_source = source_id
            db.commit()
            return None
    finally:
        db.close()


def add_idle_seconds(employee_id: int, seconds: float, at: datetime.datetime = None):
    """Accumulates idle/distracted time (see idle_service.py) onto today's
    attendance_daily row for this employee. No-op if they don't have an open
    attendance day today (haven't been recognized at all yet)."""
    at = at or datetime.datetime.now()
    today = at.date()

    db = SessionLocal()
    try:
        row = (
            db.query(AttendanceDaily)
            .filter(AttendanceDaily.employee_id == employee_id, AttendanceDaily.date == today)
            .first()
        )
        if row is None:
            return
        row.idle_seconds = (row.idle_seconds or 0) + seconds
        db.commit()
    finally:
        db.close()


def get_checked_in_employee_ids_today() -> list[int]:
    """Employee ids with an open attendance_daily row today - i.e. who have
    been recognized at least once today, used by the recognition loop to
    know who to track idle time for even on ticks where they're not detected."""
    today = datetime.datetime.now().date()
    db = SessionLocal()
    try:
        rows = db.query(AttendanceDaily.employee_id).filter(AttendanceDaily.date == today).all()
        return [r[0] for r in rows]
    finally:
        db.close()


def close_day(target_date: datetime.date = None):
    """Writes one 'exit' event per employee with an attendance_daily row on
    target_date (default: today), skipping employees who already have an
    exit event for that date. Returns the list of employee_ids closed."""
    target_date = target_date or datetime.datetime.now().date()

    db = SessionLocal()
    try:
        daily_rows = db.query(AttendanceDaily).filter(AttendanceDaily.date == target_date).all()

        closed_ids = []
        for row in daily_rows:
            existing_exits = (
                db.query(AttendanceEvent)
                .filter(AttendanceEvent.employee_id == row.employee_id, AttendanceEvent.event_type == "exit")
                .all()
            )
            if any(e.timestamp.date() == target_date for e in existing_exits):
                continue  # already closed for this date

            db.add(AttendanceEvent(
                employee_id=row.employee_id, event_type="exit", timestamp=row.last_seen_time,
                source_id=row.last_seen_source,
            ))
            closed_ids.append(row.employee_id)

        db.commit()
        logger.info(f"close_day({target_date}): exit events written for employee_ids={closed_ids}")
        return closed_ids
    finally:
        db.close()

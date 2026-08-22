"""GET /attendance/today reads the fast 'today' table directly. POST
/attendance/close_day is the on-demand way to convert last_seen_time into a
formal 'exit' AttendanceEvent for each employee (see attendance_service.py)."""
import datetime

from fastapi import APIRouter

from app.database import SessionLocal
from app.models import AttendanceDaily, Employee
from app.schemas import AttendanceTodayOut
from app.attendance_service import close_day

router = APIRouter()


@router.get("/attendance/today", response_model=list[AttendanceTodayOut])
def attendance_today():
    today = datetime.datetime.now().date()
    db = SessionLocal()
    try:
        rows = (
            db.query(AttendanceDaily, Employee)
            .join(Employee, AttendanceDaily.employee_id == Employee.id)
            .filter(AttendanceDaily.date == today)
            .all()
        )
        return [
            AttendanceTodayOut(
                employee_id=emp.id,
                employee_code=emp.employee_code,
                name=emp.name,
                entry_time=daily.entry_time,
                last_seen_time=daily.last_seen_time,
                idle_seconds=daily.idle_seconds,
                last_seen_source=daily.last_seen_source,
            )
            for daily, emp in rows
        ]
    finally:
        db.close()


@router.post("/attendance/close_day")
def attendance_close_day():
    closed_ids = close_day()
    return {"closed_employee_ids": closed_ids}

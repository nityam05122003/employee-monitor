"""Pydantic request/response models for the API (kept separate from the
SQLAlchemy models in models.py, per the usual FastAPI convention)."""
import datetime

from pydantic import BaseModel


class EnrollRequest(BaseModel):
    employee_code: str
    name: str
    source_id: str | None = None  # which camera to capture from - defaults to the first running one


class EnrollResponse(BaseModel):
    employee_id: int
    employee_code: str
    name: str
    embeddings_captured: int
    shots_attempted: int


class EmployeeOut(BaseModel):
    id: int
    employee_code: str
    name: str
    created_at: datetime.datetime
    embeddings_count: int


class AttendanceTodayOut(BaseModel):
    employee_id: int
    employee_code: str
    name: str
    entry_time: datetime.datetime
    last_seen_time: datetime.datetime
    idle_seconds: float
    last_seen_source: str | None


class AlertOut(BaseModel):
    id: int
    timestamp: datetime.datetime
    snapshot_path: str | None
    status: str
    acknowledged_at: datetime.datetime | None
    alert_type: str
    employee_id: int | None
    employee_name: str | None
    employee_code: str | None
    source_id: str | None


class CameraOut(BaseModel):
    id: str
    label: str
    is_running: bool
    error: str | None

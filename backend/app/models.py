"""
SQLAlchemy ORM models. Full schema is defined now (Phase 1) even though
attendance/alert logic is wired up in later phases, so the DB doesn't need
migrations as we go.
"""
import datetime

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, ForeignKey, Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    embeddings = relationship("FaceEmbedding", back_populates="employee", cascade="all, delete-orphan")
    daily_records = relationship("AttendanceDaily", back_populates="employee", cascade="all, delete-orphan")
    events = relationship("AttendanceEvent", back_populates="employee", cascade="all, delete-orphan")


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    # Stored as a JSON-encoded list of floats (e.g. "[0.01, -0.23, ...]").
    # Kept as TEXT rather than a vector type so this works unchanged on Postgres too.
    embedding = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    employee = relationship("Employee", back_populates="embeddings")


class AttendanceDaily(Base):
    """Fast-read 'today' table: one row per employee per date, upserted on
    every recognized frame. GET /attendance/today reads this directly."""
    __tablename__ = "attendance_daily"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    entry_time = Column(DateTime, nullable=False)
    last_seen_time = Column(DateTime, nullable=False)
    # Cumulative seconds today the employee was checked-in but idle - either
    # away from the camera entirely, or facing away from the screen beyond
    # the configured head-pose threshold. See idle_service.py. Float since
    # it accumulates in DETECTION_INTERVAL_SEC-sized fractional increments.
    idle_seconds = Column(Float, nullable=False, default=0)
    # Which configured camera (CameraSourceConfig.id) most recently saw this
    # employee - informational only, doesn't affect attendance/idle logic
    # (which is tracked per-person globally across all cameras).
    last_seen_source = Column(String, nullable=True)

    employee = relationship("Employee", back_populates="daily_records")


class AttendanceEvent(Base):
    """History table: one 'entry' event per employee per day (first
    recognition), and an 'exit' event when the day is closed."""
    __tablename__ = "attendance_events"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)  # "entry" | "exit"
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    source_id = Column(String, nullable=True)  # which camera saw this event, if applicable

    employee = relationship("Employee", back_populates="events")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    snapshot_path = Column(String, nullable=True)
    status = Column(String, default="new")  # "new" | "acknowledged"
    acknowledged_at = Column(DateTime, nullable=True)
    # "unauthorized_face" (unenrolled face detected, employee_id is None) or
    # "employee_idle" (an enrolled employee has been idle/away too long).
    alert_type = Column(String, nullable=False, default="unauthorized_face")
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    source_id = Column(String, nullable=True)  # which camera this alert came from, if known

    employee = relationship("Employee")

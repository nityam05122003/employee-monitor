"""GET /alerts (newest first) + POST /alerts/{id}/ack to acknowledge.
snapshot_path is just a filename - served via the /snapshots static mount
(see main.py), so the frontend can show it as
`{API_BASE}/snapshots/{snapshot_path}`."""
import datetime

from fastapi import APIRouter, HTTPException

from app.database import SessionLocal
from app.models import Alert
from app.schemas import AlertOut

router = APIRouter()


def _to_out(a: Alert) -> AlertOut:
    return AlertOut(
        id=a.id, timestamp=a.timestamp, snapshot_path=a.snapshot_path,
        status=a.status, acknowledged_at=a.acknowledged_at,
        alert_type=a.alert_type,
        employee_id=a.employee_id,
        employee_name=a.employee.name if a.employee else None,
        employee_code=a.employee.employee_code if a.employee else None,
        source_id=a.source_id,
    )


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts():
    db = SessionLocal()
    try:
        alerts = db.query(Alert).order_by(Alert.timestamp.desc()).all()
        return [_to_out(a) for a in alerts]
    finally:
        db.close()


@router.post("/alerts/{alert_id}/ack", response_model=AlertOut)
def acknowledge_alert(alert_id: int):
    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if alert is None:
            raise HTTPException(404, f"Alert {alert_id} not found")
        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.datetime.now()
        db.commit()
        db.refresh(alert)
        return _to_out(alert)
    finally:
        db.close()

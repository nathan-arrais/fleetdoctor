from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from ..deps import get_db
from ..models import Vehicle, Event
from ..schemas import VehicleOut, EventOut

router = APIRouter()


def _parse_date(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(value)


@router.get("/vehicles/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return VehicleOut.model_validate(vehicle)


@router.get("/vehicles/{vehicle_id}/events", response_model=list[EventOut])
def get_vehicle_events(
    vehicle_id: int,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    end_dt = _parse_date(end, datetime.utcnow()) + timedelta(days=1)
    start_dt = _parse_date(start, end_dt - timedelta(days=30))

    events = (
        db.query(Event)
        .filter(Event.vehicle_id == vehicle_id, Event.timestamp >= start_dt, Event.timestamp <= end_dt)
        .order_by(desc(Event.timestamp))
        .all()
    )
    return [EventOut.model_validate(e) for e in events]

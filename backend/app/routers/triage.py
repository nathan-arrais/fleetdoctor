from datetime import datetime, timedelta
from math import ceil
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from ..deps import get_db
from ..models import Event, Vehicle, Trip
from ..schemas import TriageResponse, TriageEventOut

router = APIRouter()


def _parse_date(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(value)


@router.get("/triage/events", response_model=TriageResponse)
def triage_events(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    region: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    event_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    end_dt = _parse_date(end, datetime.utcnow()) + timedelta(days=1)
    start_dt = _parse_date(start, end_dt - timedelta(days=7))

    query = (
        db.query(Event, Vehicle, Trip)
        .join(Vehicle, Event.vehicle_id == Vehicle.id)
        .outerjoin(Trip, Event.trip_id == Trip.id)
    )
    if not event_id:
        query = query.filter(Event.timestamp >= start_dt, Event.timestamp <= end_dt)
    if type:
        query = query.filter(Event.type == type)
    if severity:
        query = query.filter(Event.severity == severity)
    if region:
        query = query.filter(Event.region == region)
    if status:
        query = query.filter(Vehicle.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Event.description.ilike(like),
                Vehicle.plate.ilike(like),
                Trip.origin.ilike(like),
                Trip.destination.ilike(like),
                Trip.driver_name.ilike(like),
            )
        )
    if event_id:
        query = query.filter(Event.id == event_id)

    total = query.count()
    pages = max(1, ceil(total / page_size))
    items = (
        query.order_by(desc(Event.timestamp))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    def to_item(row) -> TriageEventOut:
        event, vehicle, trip = row
        return TriageEventOut(
            id=event.id,
            trip_id=event.trip_id,
            vehicle_id=event.vehicle_id,
            vehicle_plate=vehicle.plate,
            vehicle_status=vehicle.status,
            trip_status=trip.status if trip else None,
            origin=trip.origin if trip else None,
            destination=trip.destination if trip else None,
            driver_name=trip.driver_name if trip else None,
            timestamp=event.timestamp,
            type=event.type,
            severity=event.severity,
            region=event.region,
            description=event.description,
            value=event.value,
            threshold=event.threshold,
            unit=event.unit,
        )

    return TriageResponse(
        items=[to_item(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )

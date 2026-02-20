from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..deps import get_db
from ..models import Vehicle, Trip, Event
from ..schemas import DashboardMetrics

router = APIRouter()


def _parse_date(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(value)


@router.get("/dashboard/metrics", response_model=DashboardMetrics)
def dashboard_metrics(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    region: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    end_dt = _parse_date(end, datetime.utcnow()) + timedelta(days=1)
    start_dt = _parse_date(start, end_dt - timedelta(days=7))

    vehicles_query = db.query(Vehicle)
    if region:
        vehicles_query = vehicles_query.filter(Vehicle.region == region)
    if status:
        vehicles_query = vehicles_query.filter(Vehicle.status == status)

    vehicles = vehicles_query.all()

    trips_query = db.query(Trip).filter(Trip.start_time >= start_dt, Trip.start_time <= end_dt)
    if region:
        trips_query = trips_query.join(Vehicle).filter(Vehicle.region == region)
    trips = trips_query.all()

    events_query = db.query(Event).filter(Event.timestamp >= start_dt, Event.timestamp <= end_dt)
    if region:
        events_query = events_query.filter(Event.region == region)
    events = events_query.all()

    total_vehicles = len(vehicles)
    active_vehicles = len([v for v in vehicles if v.status == "active"])
    trips_completed = len([t for t in trips if t.status == "completed"])
    events_total = len(events)
    events_critical = len([e for e in events if e.severity in ("high", "critical")])
    delays_total = len([e for e in events if e.type == "delay"])
    temp_alerts_total = len([e for e in events if e.type == "temp_out_of_range"])
    stops_total = len([e for e in events if e.type == "excessive_stops"])
    on_time = len([t for t in trips if t.actual_duration_min <= t.planned_duration_min])
    on_time_rate = round((on_time / len(trips)) * 100, 1) if trips else 0.0

    sample_telemetry = []
    for i in range(7):
        day = (start_dt + timedelta(days=i)).date().isoformat()
        day_events = [e for e in events if e.timestamp.date().isoformat() == day]
        sample_telemetry.append(
            {
                "day": day[5:],
                "delays": len([e for e in day_events if e.type == "delay"]),
                "temp_alerts": len([e for e in day_events if e.type == "temp_out_of_range"]),
            }
        )

    recent_events = (
        db.query(Event, Vehicle)
        .join(Vehicle, Event.vehicle_id == Vehicle.id)
        .filter(Event.timestamp >= start_dt, Event.timestamp <= end_dt)
        .order_by(Event.timestamp.desc())
        .limit(8)
        .all()
    )

    recent_payload = [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat(),
            "type": e.type,
            "severity": e.severity,
            "description": e.description,
            "vehicle_id": e.vehicle_id,
            "vehicle_plate": v.plate,
            "trip_id": e.trip_id,
        }
        for e, v in recent_events
    ]

    return DashboardMetrics(
        total_vehicles=total_vehicles,
        active_vehicles=active_vehicles,
        trips_completed=trips_completed,
        events_total=events_total,
        events_critical=events_critical,
        delays_total=delays_total,
        temp_alerts_total=temp_alerts_total,
        stops_total=stops_total,
        on_time_rate=on_time_rate,
        sample_telemetry=sample_telemetry,
        recent_events=recent_payload,
    )

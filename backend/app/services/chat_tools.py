from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..models import Event, Trip, Vehicle


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _event_payload(event: Event) -> dict[str, Any]:
    return {
        "id": event.id,
        "trip_id": event.trip_id,
        "vehicle_id": event.vehicle_id,
        "timestamp": event.timestamp.isoformat(),
        "type": event.type,
        "severity": event.severity,
        "region": event.region,
        "description": event.description,
        "value": event.value,
        "threshold": event.threshold,
        "unit": event.unit,
    }


class ChatTools:
    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_snapshot(
        self,
        start: str | None = None,
        end: str | None = None,
        region: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        end_dt = _parse_datetime(end) or datetime.utcnow()
        start_dt = _parse_datetime(start) or (end_dt - timedelta(days=7))
        end_dt = end_dt + timedelta(days=1)

        vehicles_query = self.db.query(Vehicle)
        if region:
            vehicles_query = vehicles_query.filter(Vehicle.region == region)
        if status:
            vehicles_query = vehicles_query.filter(Vehicle.status == status)
        vehicles = vehicles_query.all()

        trips_query = self.db.query(Trip).filter(Trip.start_time >= start_dt, Trip.start_time <= end_dt)
        if region or status:
            trips_query = trips_query.join(Vehicle)
        if region:
            trips_query = trips_query.filter(Vehicle.region == region)
        if status:
            trips_query = trips_query.filter(Vehicle.status == status)
        trips = trips_query.all()

        events_query = self.db.query(Event).filter(Event.timestamp >= start_dt, Event.timestamp <= end_dt)
        if region:
            events_query = events_query.filter(Event.region == region)
        events = events_query.all()

        on_time = len([trip for trip in trips if trip.actual_duration_min <= trip.planned_duration_min])
        on_time_rate = round((on_time / len(trips)) * 100, 1) if trips else 0.0

        top_types = (
            events_query.with_entities(Event.type, func.count(Event.id).label("count"))
            .group_by(Event.type)
            .order_by(desc("count"))
            .limit(5)
            .all()
        )

        return {
            "window_start": start_dt.isoformat(),
            "window_end": end_dt.isoformat(),
            "filters": {"region": region, "status": status},
            "kpis": {
                "total_vehicles": len(vehicles),
                "active_vehicles": len([vehicle for vehicle in vehicles if vehicle.status == "active"]),
                "trips_completed": len([trip for trip in trips if trip.status == "completed"]),
                "events_total": len(events),
                "events_critical": len([event for event in events if event.severity in ("high", "critical")]),
                "delays_total": len([event for event in events if event.type == "delay"]),
                "temp_alerts_total": len([event for event in events if event.type == "temp_out_of_range"]),
                "stops_total": len([event for event in events if event.type == "excessive_stops"]),
                "on_time_rate": on_time_rate,
            },
            "top_event_types": [{"type": item[0], "count": item[1]} for item in top_types],
        }

    def search_events(
        self,
        *,
        q: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        region: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query = self.db.query(Event).join(Vehicle, Event.vehicle_id == Vehicle.id)
        if event_type:
            query = query.filter(Event.type == event_type)
        if severity:
            query = query.filter(Event.severity == severity)
        if region:
            query = query.filter(Event.region == region)
        if status:
            query = query.filter(Vehicle.status == status)
        if q:
            like = f"%{q.strip()}%"
            query = query.filter(
                Event.description.ilike(like)
                | Vehicle.plate.ilike(like)
                | Vehicle.code.ilike(like)
            )
        events = query.order_by(desc(Event.timestamp)).limit(max(1, min(limit, 100))).all()
        return [_event_payload(event) for event in events]

    def get_vehicle_overview(self, vehicle_id: int) -> dict[str, Any]:
        vehicle = self.db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        if not vehicle:
            raise ValueError("Veículo não encontrado")

        events = (
            self.db.query(Event)
            .filter(Event.vehicle_id == vehicle_id)
            .order_by(desc(Event.timestamp))
            .limit(10)
            .all()
        )
        trips = (
            self.db.query(Trip)
            .filter(Trip.vehicle_id == vehicle_id)
            .order_by(desc(Trip.start_time))
            .limit(5)
            .all()
        )

        return {
            "vehicle": {
                "id": vehicle.id,
                "code": vehicle.code,
                "plate": vehicle.plate,
                "status": vehicle.status,
                "region": vehicle.region,
                "odometer_km": vehicle.odometer_km,
                "type": vehicle.type,
            },
            "recent_events": [_event_payload(event) for event in events],
            "recent_trips": [
                {
                    "id": trip.id,
                    "start_time": trip.start_time.isoformat(),
                    "origin": trip.origin,
                    "destination": trip.destination,
                    "driver_name": trip.driver_name,
                    "status": trip.status,
                }
                for trip in trips
            ],
        }

    def get_trip_overview(self, trip_id: int) -> dict[str, Any]:
        row = self.db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id == Vehicle.id).filter(Trip.id == trip_id).first()
        if not row:
            raise ValueError("Viagem não encontrada")
        trip, vehicle = row

        events = (
            self.db.query(Event)
            .filter(Event.trip_id == trip_id)
            .order_by(desc(Event.timestamp))
            .all()
        )
        return {
            "trip": {
                "id": trip.id,
                "vehicle_id": trip.vehicle_id,
                "origin": trip.origin,
                "destination": trip.destination,
                "driver_name": trip.driver_name,
                "status": trip.status,
                "planned_duration_min": trip.planned_duration_min,
                "actual_duration_min": trip.actual_duration_min,
                "distance_km": trip.distance_km,
                "avg_temp_c": trip.avg_temp_c,
                "stops_count": trip.stops_count,
                "idle_minutes": trip.idle_minutes,
            },
            "vehicle": {
                "id": vehicle.id,
                "code": vehicle.code,
                "plate": vehicle.plate,
                "status": vehicle.status,
                "region": vehicle.region,
            },
            "events": [_event_payload(event) for event in events],
        }

    def get_top_risks(self, window_days: int = 7) -> dict[str, Any]:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=max(1, window_days))
        events_query = self.db.query(Event).filter(Event.timestamp >= start_dt, Event.timestamp <= end_dt)
        events = events_query.all()

        by_severity = (
            events_query.with_entities(Event.severity, func.count(Event.id).label("count"))
            .group_by(Event.severity)
            .order_by(desc("count"))
            .all()
        )
        by_type = (
            events_query.with_entities(Event.type, func.count(Event.id).label("count"))
            .group_by(Event.type)
            .order_by(desc("count"))
            .all()
        )
        return {
            "window_days": window_days,
            "total_events": len(events),
            "events_by_severity": [{"severity": item[0], "count": item[1]} for item in by_severity],
            "events_by_type": [{"type": item[0], "count": item[1]} for item in by_type],
        }


def list_chat_tool_names() -> list[str]:
    return [
        "get_dashboard_snapshot",
        "search_events",
        "get_vehicle_overview",
        "get_trip_overview",
        "get_top_risks",
    ]

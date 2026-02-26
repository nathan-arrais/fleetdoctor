from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..models import Event, Trip, Vehicle


def _event_to_dict(event: Event) -> dict[str, Any]:
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


class DiagnosisTools:
    def __init__(self, db: Session):
        self.db = db

    def get_event_context(self, event_id: int) -> dict[str, Any]:
        row = (
            self.db.query(Event, Vehicle, Trip)
            .join(Vehicle, Event.vehicle_id == Vehicle.id)
            .outerjoin(Trip, Event.trip_id == Trip.id)
            .filter(Event.id == event_id)
            .first()
        )
        if not row:
            raise ValueError("Evento nao encontrado para montagem de contexto")

        event, vehicle, trip = row
        return {
            "event": _event_to_dict(event),
            "vehicle": {
                "id": vehicle.id,
                "code": vehicle.code,
                "plate": vehicle.plate,
                "status": vehicle.status,
                "region": vehicle.region,
                "odometer_km": vehicle.odometer_km,
            },
            "trip": (
                {
                    "id": trip.id,
                    "origin": trip.origin,
                    "destination": trip.destination,
                    "driver_name": trip.driver_name,
                    "status": trip.status,
                    "planned_duration_min": trip.planned_duration_min,
                    "actual_duration_min": trip.actual_duration_min,
                }
                if trip
                else None
            ),
        }

    def get_trip_context(self, trip_id: int) -> dict[str, Any]:
        row = self.db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id == Vehicle.id).filter(Trip.id == trip_id).first()
        if not row:
            raise ValueError("Viagem nao encontrada para montagem de contexto")

        trip, vehicle = row
        trip_events = (
            self.db.query(Event)
            .filter(Event.trip_id == trip.id)
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
                "stops_count": trip.stops_count,
                "idle_minutes": trip.idle_minutes,
                "avg_temp_c": trip.avg_temp_c,
            },
            "vehicle": {
                "id": vehicle.id,
                "code": vehicle.code,
                "plate": vehicle.plate,
                "status": vehicle.status,
                "region": vehicle.region,
            },
            "events": [_event_to_dict(event) for event in trip_events],
        }

    def get_similar_events(self, event_type: str, region: str, limit: int = 5) -> list[dict[str, Any]]:
        query = self.db.query(Event).filter(Event.type == event_type)
        if region:
            query = query.filter(Event.region == region)
        events = query.order_by(desc(Event.timestamp)).limit(limit).all()
        return [_event_to_dict(event) for event in events]

    def get_vehicle_recent_history(self, vehicle_id: int, days: int = 30) -> dict[str, Any]:
        start = datetime.utcnow() - timedelta(days=days)
        events = (
            self.db.query(Event)
            .filter(Event.vehicle_id == vehicle_id, Event.timestamp >= start)
            .order_by(desc(Event.timestamp))
            .all()
        )
        by_type = Counter(event.type for event in events)
        by_severity = Counter(event.severity for event in events)
        return {
            "window_days": days,
            "total_events": len(events),
            "events_by_type": dict(by_type),
            "events_by_severity": dict(by_severity),
            "last_events": [_event_to_dict(event) for event in events[:5]],
        }


def list_tool_names() -> list[str]:
    return [
        "get_event_context",
        "get_trip_context",
        "get_similar_events",
        "get_vehicle_recent_history",
    ]

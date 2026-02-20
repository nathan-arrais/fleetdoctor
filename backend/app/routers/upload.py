from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import csv
import io
import os

from ..deps import get_db
from ..db import DB_PATH, engine
from ..models import Vehicle, Trip, Event
from .. import seed as seed_module

router = APIRouter()

REQUIRED_COLUMNS = [
    "vehicle_id",
    "plate",
    "trip_id",
    "event_type",
    "severity",
    "timestamp",
    "description",
]

ALLOWED_TYPES = {"delay", "temp_out_of_range", "excessive_stops", "excessive_idle", "route_deviation"}
ALLOWED_SEVERITY = {"low", "medium", "high", "critical"}


def _build_unique_vehicle_code(db: Session, raw_vehicle_id: str) -> str:
    base_code = raw_vehicle_id or f"IMPORT-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    code = base_code
    suffix = 1
    while db.query(Vehicle).filter(Vehicle.code == code).first():
        code = f"{base_code}-{suffix}"
        suffix += 1
    return code


def _build_unique_vehicle_plate(db: Session, plate: str, raw_vehicle_id: str) -> str:
    base_plate = plate or (f"PLT-{raw_vehicle_id[:6]}" if raw_vehicle_id else "PLT-IMPORT")
    safe_plate = base_plate
    suffix = 1
    while db.query(Vehicle).filter(Vehicle.plate == safe_plate).first():
        safe_plate = f"{base_plate}-{suffix}"
        suffix += 1
    return safe_plate


def _read_csv(file: UploadFile):
    content = file.file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV deve estar em UTF-8")
    reader = csv.DictReader(io.StringIO(text))
    rows = [row for row in reader]
    return reader.fieldnames or [], rows


def _validate_columns(columns: list[str]):
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Colunas obrigatorias faltando: {', '.join(missing)}",
        )


def _parse_timestamp(value: str, row_number: int) -> tuple[datetime, bool]:
    try:
        return datetime.fromisoformat(value), False
    except Exception:
        print(
            f"[upload/import] warning: timestamp invalido na linha {row_number}; "
            f"usando utcnow(). valor={value!r}"
        )
        return datetime.utcnow(), True


@router.post("/upload/preview")
def upload_preview(file: UploadFile = File(...)):
    columns, rows = _read_csv(file)
    _validate_columns(columns)
    preview = rows[:10]
    return {"columns": columns, "rows": preview}


@router.post("/upload/import")
def upload_import(file: UploadFile = File(...), db: Session = Depends(get_db)):
    columns, rows = _read_csv(file)
    _validate_columns(columns)

    created_events = 0
    invalid_timestamp_rows = 0
    for index, row in enumerate(rows):
        raw_vehicle_id = (row.get("vehicle_id") or "").strip()
        plate = (row.get("plate") or "").strip()
        raw_trip_id = (row.get("trip_id") or "").strip()
        event_type = (row.get("event_type") or "").strip().lower()
        severity = (row.get("severity") or "").strip().lower()
        timestamp, timestamp_invalid = _parse_timestamp((row.get("timestamp") or "").strip(), index + 2)
        if timestamp_invalid:
            invalid_timestamp_rows += 1
        description = (row.get("description") or "").strip()
        value_num = row.get("value_num")

        if event_type and event_type not in ALLOWED_TYPES:
            event_type = "route_deviation"
        if severity and severity not in ALLOWED_SEVERITY:
            severity = "low"

        vehicle = None
        if raw_vehicle_id:
            vehicle = db.query(Vehicle).filter(Vehicle.code == raw_vehicle_id).first()
        if not vehicle and raw_vehicle_id.isdigit():
            vehicle = db.query(Vehicle).filter(Vehicle.id == int(raw_vehicle_id)).first()
        if not vehicle and plate:
            vehicle = db.query(Vehicle).filter(Vehicle.plate == plate).first()

        if not vehicle:
            safe_plate = _build_unique_vehicle_plate(db, plate, raw_vehicle_id)
            vehicle = Vehicle(
                code=_build_unique_vehicle_code(db, raw_vehicle_id),
                plate=safe_plate,
                uf="NA",
                type="truck",
                region="Importado",
                status="active",
                last_service_date=datetime.utcnow().date().isoformat(),
                odometer_km=0.0,
            )
            db.add(vehicle)
            db.flush()

        trip = None
        if raw_trip_id.isdigit():
            trip = db.query(Trip).filter(Trip.id == int(raw_trip_id)).first()
            if trip and trip.vehicle_id != vehicle.id:
                trip = None
        if raw_trip_id and not trip:
            trip = (
                db.query(Trip)
                .filter(Trip.origin == f"IMPORT-{raw_trip_id}", Trip.vehicle_id == vehicle.id)
                .first()
            )
        if raw_trip_id and not trip:
            trip = Trip(
                vehicle_id=vehicle.id,
                start_time=timestamp,
                end_time=timestamp,
                origin=f"IMPORT-{raw_trip_id}",
                destination="IMPORT",
                region=vehicle.region,
                driver_name="Importado",
                planned_duration_min=0,
                actual_duration_min=0,
                distance_km=0.0,
                status="completed",
                avg_temp_c=0.0,
                stops_count=0,
                idle_minutes=0,
            )
            db.add(trip)
            db.flush()

        value = None
        if value_num not in (None, ""):
            try:
                value = float(value_num)
            except ValueError:
                value = None

        event = Event(
            trip_id=trip.id if trip else None,
            vehicle_id=vehicle.id,
            timestamp=timestamp,
            type=event_type or "route_deviation",
            severity=severity or "low",
            region=vehicle.region,
            description=description or "Evento importado",
            value=value,
            threshold=None,
            unit=None,
        )
        db.add(event)
        created_events += 1

    db.commit()
    response = {"imported": created_events}
    if invalid_timestamp_rows > 0:
        warning_message = (
            f"{invalid_timestamp_rows} linhas com timestamp invalido; usado utcnow()"
        )
        print(f"[upload/import] warning: {warning_message}")
        response["warnings"] = [warning_message]
    return response


@router.post("/upload/reset")
def upload_reset():
    try:
        engine.dispose()
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao resetar banco: {exc}") from exc
    seed_module.seed()
    return {"status": "reset", "message": "Banco recriado com seed demo."}

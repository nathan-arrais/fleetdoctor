from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..deps import get_db
from ..models import Event, Trip
from ..schemas import DiagnosisRequest, DiagnosisResponse
from ..services.diagnosis_engine import diagnose_event_with_engine, diagnose_trip_with_engine

router = APIRouter()


@router.post("/diagnosis", response_model=DiagnosisResponse)
def create_diagnosis(payload: DiagnosisRequest, db: Session = Depends(get_db)):
    if payload.event_id:
        event = db.query(Event).filter(Event.id == payload.event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return diagnose_event_with_engine(
            db,
            event,
            debug=payload.debug,
            force_deterministic=payload.force_deterministic,
        )

    if payload.trip_id:
        trip = db.query(Trip).filter(Trip.id == payload.trip_id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        return diagnose_trip_with_engine(
            db,
            trip,
            debug=payload.debug,
            force_deterministic=payload.force_deterministic,
        )

    raise HTTPException(status_code=400, detail="event_id or trip_id required")

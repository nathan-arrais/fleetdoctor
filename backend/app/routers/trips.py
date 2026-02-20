from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from ..deps import get_db
from ..models import Trip, Event
from ..schemas import TripOut, EventOut

router = APIRouter()


@router.get("/trips/{trip_id}", response_model=TripOut)
def get_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripOut.model_validate(trip)


@router.get("/trips/{trip_id}/events", response_model=list[EventOut])
def get_trip_events(trip_id: int, db: Session = Depends(get_db)):
    events = (
        db.query(Event)
        .filter(Event.trip_id == trip_id)
        .order_by(desc(Event.timestamp))
        .all()
    )
    return [EventOut.model_validate(e) for e in events]

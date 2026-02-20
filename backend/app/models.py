from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from .db import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    plate = Column(String, unique=True, index=True)
    uf = Column(String)
    type = Column(String)
    region = Column(String)
    status = Column(String)
    last_service_date = Column(String)
    odometer_km = Column(Float)

    trips = relationship("Trip", back_populates="vehicle")
    events = relationship("Event", back_populates="vehicle")


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    origin = Column(String)
    destination = Column(String)
    region = Column(String)
    driver_name = Column(String)
    planned_duration_min = Column(Integer)
    actual_duration_min = Column(Integer)
    distance_km = Column(Float)
    status = Column(String)
    avg_temp_c = Column(Float)
    stops_count = Column(Integer)
    idle_minutes = Column(Integer)

    vehicle = relationship("Vehicle", back_populates="trips")
    events = relationship("Event", back_populates="trip")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    timestamp = Column(DateTime)
    type = Column(String)
    severity = Column(String)
    region = Column(String)
    description = Column(String)
    value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    unit = Column(String, nullable=True)

    trip = relationship("Trip", back_populates="events")
    vehicle = relationship("Vehicle", back_populates="events")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime)
    report_type = Column(String)
    start = Column(String)
    end = Column(String)
    region = Column(String, nullable=True)
    status_filter = Column(String, nullable=True)
    type_filter = Column(String, nullable=True)
    severity_filter = Column(String, nullable=True)
    query_filter = Column(String, nullable=True)
    html_content = Column(Text)
    file_name = Column(String)
    file_path = Column(String)

import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .db import Base, engine, SessionLocal
from .models import Vehicle, Trip, Event

UF_TO_REGION = {
    "AC": "Norte",
    "AL": "Nordeste",
    "AP": "Norte",
    "AM": "Norte",
    "BA": "Nordeste",
    "CE": "Nordeste",
    "DF": "Centro-Oeste",
    "ES": "Sudeste",
    "GO": "Centro-Oeste",
    "MA": "Nordeste",
    "MT": "Centro-Oeste",
    "MS": "Centro-Oeste",
    "MG": "Sudeste",
    "PA": "Norte",
    "PB": "Nordeste",
    "PR": "Sul",
    "PE": "Nordeste",
    "PI": "Nordeste",
    "RJ": "Sudeste",
    "RN": "Nordeste",
    "RS": "Sul",
    "RO": "Norte",
    "RR": "Norte",
    "SC": "Sul",
    "SP": "Sudeste",
    "SE": "Nordeste",
    "TO": "Norte",
}
UF_POOL = sorted(UF_TO_REGION.keys())
VEHICLE_TYPES = ["truck", "van"]
STATUS = ["active", "in_maintenance", "out_of_service"]


def seed():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    if db.query(Vehicle).count() > 0:
        db.close()
        print("Seed já existe. Nada a fazer.")
        return

    random.seed(42)

    vehicles = []
    for i in range(1, 26):
        uf = random.choice(UF_POOL)
        vehicle = Vehicle(
            code=f"FD-{1000 + i}",
            plate=f"ABC{i:04d}",
            uf=uf,
            type=random.choice(VEHICLE_TYPES),
            region=UF_TO_REGION[uf],
            status=random.choices(STATUS, weights=[0.75, 0.2, 0.05])[0],
            last_service_date=(datetime.utcnow() - timedelta(days=random.randint(10, 120))).date().isoformat(),
            odometer_km=round(random.uniform(40000, 220000), 1),
        )
        vehicles.append(vehicle)
    db.add_all(vehicles)
    db.commit()

    trips = []
    now = datetime.utcnow()
    for i in range(1, 51):
        vehicle = random.choice(vehicles)
        start_time = now - timedelta(days=random.randint(1, 30), hours=random.randint(0, 12))
        planned = random.randint(120, 480)
        delay = random.randint(-20, 120)
        actual = max(60, planned + delay)
        status = "completed" if actual <= planned * 1.2 else "delayed"
        avg_temp = round(random.uniform(0, 12), 1)
        stops = random.randint(2, 10)
        idle = random.randint(10, 140)

        trip = Trip(
            vehicle_id=vehicle.id,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=actual),
            origin=random.choice(["Porto Alegre", "Curitiba", "Goiania", "Recife", "Manaus"]),
            destination=random.choice(["Sao Paulo", "Belo Horizonte", "Salvador", "Belem", "Brasilia"]),
            region=vehicle.region,
            driver_name=random.choice(
                ["Camila Rocha", "Joao Silva", "Renata Lima", "Carlos Souza", "Patricia Melo", "Andre Costa"]
            ),
            planned_duration_min=planned,
            actual_duration_min=actual,
            distance_km=round(random.uniform(180, 1200), 1),
            status=status,
            avg_temp_c=avg_temp,
            stops_count=stops,
            idle_minutes=idle,
        )
        trips.append(trip)
    db.add_all(trips)
    db.commit()

    events = []

    def add_event(trip, vehicle, etype, severity, description, value, threshold, unit):
        events.append(
            Event(
                trip_id=trip.id if trip else None,
                vehicle_id=vehicle.id,
                timestamp=(trip.start_time + timedelta(minutes=random.randint(0, trip.actual_duration_min)))
                if trip
                else datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                type=etype,
                severity=severity,
                region=vehicle.region,
                description=description,
                value=value,
                threshold=threshold,
                unit=unit,
            )
        )

    for trip in trips:
        vehicle = next(v for v in vehicles if v.id == trip.vehicle_id)
        if trip.actual_duration_min > trip.planned_duration_min + 30:
            delay = trip.actual_duration_min - trip.planned_duration_min
            severity = "medium" if delay < 60 else "high" if delay < 90 else "critical"
            add_event(
                trip,
                vehicle,
                "delay",
                severity,
                "Atraso acima do limite",
                delay,
                30,
                "min",
            )
        if trip.avg_temp_c < 2 or trip.avg_temp_c > 8:
            severity = "medium" if abs(trip.avg_temp_c - 5) < 3 else "high"
            threshold = 8 if trip.avg_temp_c > 8 else 2
            add_event(
                trip,
                vehicle,
                "temp_out_of_range",
                severity,
                "Temperatura fora da faixa",
                trip.avg_temp_c,
                threshold,
                "C",
            )
        if trip.stops_count > 6:
            severity = "low" if trip.stops_count < 8 else "medium"
            add_event(
                trip,
                vehicle,
                "excessive_stops",
                severity,
                "Excesso de paradas",
                trip.stops_count,
                6,
                "stops",
            )
        if trip.idle_minutes > 60:
            severity = "medium" if trip.idle_minutes < 90 else "high"
            add_event(
                trip,
                vehicle,
                "excessive_idle",
                severity,
                "Tempo parado elevado",
                trip.idle_minutes,
                60,
                "min",
            )

    event_types = [
        ("delay", "Atraso acima do limite", "min", 30),
        ("temp_out_of_range", "Temperatura fora da faixa", "C", 8),
        ("excessive_stops", "Excesso de paradas", "stops", 6),
        ("excessive_idle", "Tempo parado elevado", "min", 60),
    ]

    while len(events) < 220:
        trip = random.choice(trips)
        vehicle = next(v for v in vehicles if v.id == trip.vehicle_id)
        etype, desc, unit, threshold = random.choice(event_types)
        value = threshold + random.randint(1, 20)
        severity = random.choice(["low", "medium", "high"])
        add_event(trip, vehicle, etype, severity, desc, value, threshold, unit)

    db.add_all(events)
    db.commit()
    db.close()
    print(f"Seed concluído: {len(vehicles)} veiculos, {len(trips)} viagens, {len(events)} eventos")


if __name__ == "__main__":
    seed()

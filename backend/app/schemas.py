from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class VehicleOut(BaseModel):
    id: int
    code: str
    plate: str
    type: str
    region: str
    status: str
    last_service_date: str
    odometer_km: float

    class Config:
        from_attributes = True


class TripOut(BaseModel):
    id: int
    vehicle_id: int
    start_time: datetime
    end_time: datetime
    origin: str
    destination: str
    driver_name: str
    planned_duration_min: int
    actual_duration_min: int
    distance_km: float
    status: str
    avg_temp_c: float
    stops_count: int
    idle_minutes: int

    class Config:
        from_attributes = True


class EventOut(BaseModel):
    id: int
    trip_id: Optional[int]
    vehicle_id: int
    timestamp: datetime
    type: str
    severity: str
    region: str
    description: str
    value: Optional[float]
    threshold: Optional[float]
    unit: Optional[str]

    class Config:
        from_attributes = True


class TriageEventOut(BaseModel):
    id: int
    trip_id: Optional[int]
    vehicle_id: int
    vehicle_plate: str
    vehicle_status: str
    trip_status: Optional[str]
    origin: Optional[str]
    destination: Optional[str]
    driver_name: Optional[str]
    timestamp: datetime
    type: str
    severity: str
    region: str
    description: str
    value: Optional[float]
    threshold: Optional[float]
    unit: Optional[str]


class TriageResponse(BaseModel):
    items: List[TriageEventOut]
    total: int
    page: int
    page_size: int
    pages: int


class DiagnosisRequest(BaseModel):
    event_id: Optional[int] = None
    trip_id: Optional[int] = None
    debug: bool = False
    force_deterministic: bool = False


class DiagnosisResponse(BaseModel):
    severity: str
    summary: str
    probable_causes: List[str]
    recommended_actions: List[str]
    evidence: List[str]
    source: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    used_tools: List[str] = Field(default_factory=list)
    fallback_reason: Optional[str] = None
    validation_warnings: List[str] = Field(default_factory=list)


class ReportOut(BaseModel):
    id: int
    report_id: Optional[int] = None
    created_at: datetime
    report_type: str
    start: str
    end: str
    region: Optional[str]
    status_filter: Optional[str]
    type_filter: Optional[str]
    severity_filter: Optional[str]
    query_filter: Optional[str]
    file_name: str
    preview_url: Optional[str] = None
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


class ReportGenerateRequest(BaseModel):
    type: str
    start: str
    end: str
    region: Optional[str] = None
    status: Optional[str] = None
    event_type: Optional[str] = None
    severity: Optional[str] = None
    q: Optional[str] = None


class DashboardMetrics(BaseModel):
    total_vehicles: int
    active_vehicles: int
    trips_completed: int
    events_total: int
    events_critical: int
    delays_total: int
    temp_alerts_total: int
    stops_total: int
    on_time_rate: float
    sample_telemetry: List[dict]
    recent_events: List[dict]

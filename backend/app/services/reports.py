import html
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from ..models import Event, Trip, Vehicle


def safe(value) -> str:
    return html.escape(str(value))


def generate_report_html(
    session: Session,
    start: str,
    end: str,
    region: str | None,
    status: str | None,
    event_type: str | None,
    severity: str | None,
    query: str | None,
) -> str:
    parsed_end = _parse_date(end, datetime.utcnow())
    end_dt = parsed_end if _has_explicit_time(end) else parsed_end + timedelta(days=1)
    start_dt = _parse_date(start, end_dt - timedelta(days=14))
    like = f"%{query.strip()}%" if query and query.strip() else None

    vehicles_query = session.query(Vehicle)
    if region:
        vehicles_query = vehicles_query.filter(Vehicle.region == region)
    if status:
        vehicles_query = vehicles_query.filter(Vehicle.status == status)

    events_query = (
        session.query(Event)
        .join(Vehicle, Event.vehicle_id == Vehicle.id)
        .outerjoin(Trip, Event.trip_id == Trip.id)
        .filter(Event.timestamp >= start_dt, Event.timestamp <= end_dt)
    )
    if region:
        events_query = events_query.filter(Event.region == region)
    if status:
        events_query = events_query.filter(Vehicle.status == status)
    if event_type:
        events_query = events_query.filter(Event.type == event_type)
    if severity:
        events_query = events_query.filter(Event.severity == severity)
    if like:
        events_query = events_query.filter(
            or_(
                Event.description.ilike(like),
                Vehicle.plate.ilike(like),
                Trip.driver_name.ilike(like),
                Trip.origin.ilike(like),
                Trip.destination.ilike(like),
            )
        )
    events = events_query.all()
    if like:
        vehicle_ids = [vehicle_id for vehicle_id, in events_query.with_entities(Event.vehicle_id).distinct().all()]
        if vehicle_ids:
            vehicles_query = vehicles_query.filter(Vehicle.id.in_(vehicle_ids))
        else:
            vehicles_query = vehicles_query.filter(Vehicle.id == -1)
    vehicles = vehicles_query.all()

    trips_query = (
        session.query(Trip)
        .join(Vehicle, Trip.vehicle_id == Vehicle.id)
        .filter(Trip.start_time >= start_dt, Trip.start_time <= end_dt)
    )
    if region:
        trips_query = trips_query.filter(Vehicle.region == region)
    if status:
        trips_query = trips_query.filter(Vehicle.status == status)
    if like:
        trips_query = trips_query.filter(
            or_(
                Vehicle.plate.ilike(like),
                Trip.driver_name.ilike(like),
                Trip.origin.ilike(like),
                Trip.destination.ilike(like),
            )
        )
    trips = trips_query.all()

    events_total = len(events)
    events_critical = len([e for e in events if e.severity in ("high", "critical")])
    trips_completed = len([t for t in trips if t.status == "completed"])

    delays_total = len([e for e in events if e.type == "delay"])
    temp_alerts_total = len([e for e in events if e.type == "temp_out_of_range"])
    stops_total = len([e for e in events if e.type == "excessive_stops"])
    top_event_vehicles = (
        events_query.with_entities(Vehicle.code, Vehicle.region, func.count(Event.id).label("cnt"))
        .group_by(Event.vehicle_id, Vehicle.code, Vehicle.region)
        .order_by(desc("cnt"))
        .limit(10)
        .all()
    )

    top_vehicles = (
        events_query.with_entities(Event.vehicle_id, func.count(Event.id).label("cnt"))
        .filter(Event.severity.in_(["high", "critical"]))
        .group_by(Event.vehicle_id)
        .order_by(desc("cnt"))
        .limit(5)
        .all()
    )

    top_trips = (
        events_query.with_entities(Event.trip_id, func.count(Event.id).label("cnt"))
        .filter(Event.trip_id.isnot(None))
        .filter(Event.severity.in_(["high", "critical"]))
        .group_by(Event.trip_id)
        .order_by(desc("cnt"))
        .limit(5)
        .all()
    )

    top_types = (
        events_query.with_entities(Event.type, func.count(Event.id).label("cnt"))
        .group_by(Event.type)
        .order_by(desc("cnt"))
        .limit(5)
        .all()
    )

    recommendations = _aggregate_recommendations(events)
    safe_start = safe(start)
    safe_end = safe(end)
    safe_region = safe(region) if region else "Todas"
    safe_status = safe(status) if status else "Todos"
    safe_event_type = safe(event_type) if event_type else "Todos"
    safe_severity = safe(severity) if severity else "Todas"
    safe_query = safe(query) if query else "-"

    return f"""
<!DOCTYPE html>
<html lang=\"pt-br\">
<head>
  <meta charset=\"UTF-8\" />
  <title>FleetDoctor Report</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: #e2e8f0;
      --accent: #4f46e5;
      --accent-soft: #eef2ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 24px; color: var(--text); background: var(--bg); }}
    h1 {{ margin: 0 0 4px 0; font-size: 24px; }}
    h2 {{ margin: 20px 0 8px 0; font-size: 16px; }}
    .subtitle {{ color: var(--muted); font-size: 13px; }}
    .header {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 16px; }}
    .filters {{ margin-top: 12px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; font-size: 12px; color: var(--muted); }}
    .card {{ border: 1px solid var(--border); border-radius: 14px; padding: 14px; margin: 12px 0; background: var(--card); }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .kpi {{ border: 1px solid var(--border); border-radius: 12px; padding: 12px; background: var(--card); }}
    .kpi .label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }}
    .kpi .value {{ font-size: 20px; font-weight: 700; margin-top: 6px; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }}
    .badge.low {{ background: #e2e8f0; color: #334155; }}
    .badge.medium {{ background: #fde68a; color: #92400e; }}
    .badge.high {{ background: #fecaca; color: #991b1b; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--border); padding: 8px; text-align: left; }}
    th {{ background: #f1f5f9; text-transform: uppercase; font-size: 11px; color: var(--muted); letter-spacing: 0.06em; }}
    tbody tr:nth-child(even) {{ background: #f8fafc; }}
    .recommendations {{ background: var(--accent-soft); border: 1px solid #c7d2fe; }}
    .footer {{ margin-top: 16px; color: var(--muted); font-size: 11px; }}
    @media print {{
      body {{ margin: 12mm; background: #ffffff; }}
      .header, .card, .kpi {{ break-inside: avoid; page-break-inside: avoid; }}
      table {{ page-break-inside: auto; }}
      tr {{ page-break-inside: avoid; page-break-after: auto; }}
    }}
    @media (max-width: 900px) {{
      .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .filters {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class=\"header\">
    <h1>FleetDoctor</h1>
    <div class=\"subtitle\">Relatorio Operacional (Mock IA)</div>
    <div class=\"subtitle\">Gerado em {datetime.utcnow().isoformat()} UTC</div>
    <div class=\"filters\">
      <div><strong>Periodo:</strong> {safe_start} - {safe_end}</div>
      <div><strong>Regiao:</strong> {safe_region}</div>
      <div><strong>Status:</strong> {safe_status}</div>
      <div><strong>Tipo:</strong> {safe_event_type}</div>
      <div><strong>Severidade:</strong> {safe_severity}</div>
      <div><strong>Busca:</strong> {safe_query}</div>
    </div>
  </div>

  <h2>KPIs principais</h2>
  <div class=\"kpi-grid\">
    <div class=\"kpi\">
      <div class=\"label\">Veiculos monitorados</div>
      <div class=\"value\">{len(vehicles)}</div>
    </div>
    <div class=\"kpi\">
      <div class=\"label\">Eventos totais</div>
      <div class=\"value\">{events_total}</div>
    </div>
    <div class=\"kpi\">
      <div class=\"label\">Eventos criticos</div>
      <div class=\"value\">{events_critical}</div>
    </div>
    <div class=\"kpi\">
      <div class=\"label\">Viagens concluidas</div>
      <div class=\"value\">{trips_completed}</div>
    </div>
  </div>

  <div class=\"kpi-grid\" style=\"margin-top: 12px;\">
    <div class=\"kpi\">
      <div class=\"label\">Com atraso</div>
      <div class=\"value\">{delays_total}</div>
    </div>
    <div class=\"kpi\">
      <div class=\"label\">Temp fora</div>
      <div class=\"value\">{temp_alerts_total}</div>
    </div>
    <div class=\"kpi\">
      <div class=\"label\">Paradas excessivas</div>
      <div class=\"value\">{stops_total}</div>
    </div>
    <div class=\"kpi\">
      <div class=\"label\">Severidades</div>
      <div style=\"margin-top: 6px;\">
        <span class=\"badge low\">low</span>
        <span class=\"badge medium\">medium</span>
        <span class=\"badge high\">high</span>
      </div>
    </div>
  </div>

  <h2>Top veiculos com eventos</h2>
  <table>
    <thead>
      <tr>
        <th>Veiculo</th>
        <th>Regiao</th>
        <th>Eventos</th>
      </tr>
    </thead>
    <tbody>
      {"".join(_top_event_vehicle_rows(top_event_vehicles))}
    </tbody>
  </table>

  <h2>Top 5 veiculos criticos</h2>
  <table>
    <thead>
      <tr>
        <th>Veiculo</th>
        <th>Criticos</th>
      </tr>
    </thead>
    <tbody>
      {"".join(_top_vehicle_rows(session, top_vehicles))}
    </tbody>
  </table>

  <h2>Top 5 viagens criticas</h2>
  <table>
    <thead>
      <tr>
        <th>Viagem</th>
        <th>Criticos</th>
      </tr>
    </thead>
    <tbody>
      {"".join(_top_trip_rows(session, top_trips))}
    </tbody>
  </table>

  <h2>Top tipos de ocorrencia</h2>
  <ul>
    {"".join([f"<li>{safe(t[0])} ({safe(t[1])})</li>" for t in top_types])}
  </ul>

  <h2>Recomendacoes (Mock IA)</h2>
  <ul class=\"card recommendations\">
    {"".join([f"<li>{safe(item)}</li>" for item in recommendations])}
  </ul>

  <div class=\"footer\">
    Gerado por regras deterministicas (sem LLM).
  </div>
</body>
</html>
"""


def _parse_date(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return fallback


def _has_explicit_time(value: str | None) -> bool:
    if not value:
        return False
    value = value.strip()
    return "T" in value or " " in value


def _top_event_vehicle_rows(rows_data: list[tuple]) -> list[str]:
    rows = []
    for code, region, count in rows_data:
        rows.append(f"<tr><td>{safe(code)}</td><td>{safe(region)}</td><td>{safe(count)}</td></tr>")
    return rows


def _top_vehicle_rows(session: Session, vehicle_rows: list[tuple]) -> list[str]:
    rows = []
    for vehicle_id, count in vehicle_rows:
        vehicle = session.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        name = vehicle.code if vehicle else f"#{vehicle_id}"
        rows.append(f"<tr><td>{safe(name)}</td><td>{safe(count)}</td></tr>")
    return rows


def _top_trip_rows(session: Session, trip_rows: list[tuple]) -> list[str]:
    rows = []
    for trip_id, count in trip_rows:
        rows.append(f"<tr><td>{safe(f'#{trip_id}')}</td><td>{safe(count)}</td></tr>")
    return rows


def _aggregate_recommendations(events: list[Event]) -> list[str]:
    actions = []
    for event in events:
        if event.type == "delay":
            actions.append("Revisar rota e ajustar buffers de entrega.")
        elif event.type == "temp_out_of_range":
            actions.append("Inspecionar sistema de refrigeracao e vedacao.")
        elif event.type == "excessive_stops":
            actions.append("Revisar planejamento de paradas e compliance do motorista.")
        elif event.type == "excessive_idle":
            actions.append("Configurar alertas de tempo parado e revisar docas.")
    unique = []
    for item in actions:
        if item not in unique:
            unique.append(item)
    return unique[:5] if unique else ["Manter monitoramento e auditoria operacional."]

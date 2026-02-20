import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiGet } from "../api/client";

type Trip = {
  id: number;
  vehicle_id: number;
  start_time: string;
  end_time: string;
  origin: string;
  destination: string;
  driver_name: string;
  planned_duration_min: number;
  actual_duration_min: number;
  distance_km: number;
  status: string;
  avg_temp_c: number;
  stops_count: number;
  idle_minutes: number;
};

type EventItem = {
  id: number;
  timestamp: string;
  type: string;
  severity: string;
  description: string;
};

export default function TripPage() {
  const { trip_id } = useParams();
  const [trip, setTrip] = useState<Trip | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);

  useEffect(() => {
    if (!trip_id) return;
    apiGet<Trip>(`/api/trips/${trip_id}`).then(setTrip);
    apiGet<EventItem[]>(`/api/trips/${trip_id}/events`).then(setEvents);
  }, [trip_id]);

  if (!trip) {
    return <div className="text-slate-500">Carregando viagem...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Viagem #{trip.id}</h1>
        <p className="text-slate-600">{trip.origin} → {trip.destination}</p>
      </div>

      <div className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-4 md:grid-cols-3">
        <div>
          <div className="text-xs uppercase text-slate-400">Veiculo</div>
          <div className="text-sm font-semibold">#{trip.vehicle_id}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-400">Status</div>
          <div className="text-sm font-semibold">{trip.status}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-400">Motorista</div>
          <div className="text-sm font-semibold">{trip.driver_name}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-400">Distancia</div>
          <div className="text-sm font-semibold">{trip.distance_km} km</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-400">Duracao planejada</div>
          <div className="text-sm font-semibold">{trip.planned_duration_min} min</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-400">Duracao real</div>
          <div className="text-sm font-semibold">{trip.actual_duration_min} min</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-400">Temperatura media</div>
          <div className="text-sm font-semibold">{trip.avg_temp_c} °C</div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Eventos da viagem</div>
        <ul className="divide-y divide-slate-100">
          {events.map((event) => (
            <li key={event.id} className="px-4 py-3 text-sm">
              <div className="font-medium">{event.description}</div>
              <div className="text-xs text-slate-500">
                {event.type} • {event.severity} • {new Date(event.timestamp).toLocaleString()}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

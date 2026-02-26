import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiGet } from "../api/client";

type Vehicle = {
  id: number;
  code: string;
  plate: string;
  type: string;
  region: string;
  status: string;
  last_service_date: string;
  odometer_km: number;
};

type EventItem = {
  id: number;
  timestamp: string;
  type: string;
  severity: string;
  description: string;
};

export default function VehiclePage() {
  const { vehicle_id } = useParams();
  const [vehicle, setVehicle] = useState<Vehicle | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);

  useEffect(() => {
    if (!vehicle_id) return;
    apiGet<Vehicle>(`/api/vehicles/${vehicle_id}`).then(setVehicle);
    apiGet<EventItem[]>(`/api/vehicles/${vehicle_id}/events`).then(setEvents);
  }, [vehicle_id]);

  if (!vehicle) {
    return <div className="text-slate-500">Carregando veículo...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Veículo #{vehicle.id}</h1>
        <p className="text-slate-600">{vehicle.code} • {vehicle.plate}</p>
      </div>

      <div className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-4 md:grid-cols-3">
        <div>
          <div className="text-xs uppercase text-slate-400">Tipo</div>
          <div className="text-sm font-semibold">{vehicle.type}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-400">Região</div>
          <div className="text-sm font-semibold">{vehicle.region}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-400">Status</div>
          <div className="text-sm font-semibold">{vehicle.status}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-400">Ultima manutencao</div>
          <div className="text-sm font-semibold">{vehicle.last_service_date}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-slate-400">Odometro</div>
          <div className="text-sm font-semibold">{vehicle.odometer_km} km</div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Eventos recentes</div>
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

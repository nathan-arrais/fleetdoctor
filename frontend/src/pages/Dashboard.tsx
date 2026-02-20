import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { apiGet } from "../api/client";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type RecentEvent = {
  id: number;
  timestamp: string;
  type: string;
  severity: string;
  description: string;
  vehicle_id: number;
  vehicle_plate: string;
  trip_id: number | null;
};

type DashboardMetrics = {
  total_vehicles: number;
  active_vehicles: number;
  trips_completed: number;
  events_total: number;
  events_critical: number;
  delays_total: number;
  temp_alerts_total: number;
  stops_total: number;
  on_time_rate: number;
  sample_telemetry: { day: string; delays: number; temp_alerts: number }[];
  recent_events: RecentEvent[];
};

function toDateInput(d: Date) {
  return d.toISOString().slice(0, 10);
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const end = useMemo(() => new Date(), []);
  const start = useMemo(() => new Date(Date.now() - 7 * 86400000), []);

  const [startDate, setStartDate] = useState(searchParams.get("start") ?? toDateInput(start));
  const [endDate, setEndDate] = useState(searchParams.get("end") ?? toDateInput(end));
  const [region, setRegion] = useState(searchParams.get("region") ?? "");
  const [status, setStatus] = useState(searchParams.get("status") ?? "");

  const params = useMemo(() => {
    const p = new URLSearchParams({ start: startDate, end: endDate });
    if (region) p.set("region", region);
    if (status) p.set("status", status);
    return p;
  }, [startDate, endDate, region, status]);

  useEffect(() => {
    if (searchParams.toString() !== params.toString()) {
      setSearchParams(params, { replace: true });
    }
  }, [params, searchParams, setSearchParams]);

  useEffect(() => {
    apiGet<DashboardMetrics>(`/api/dashboard/metrics?${params.toString()}`)
      .then(setMetrics)
      .catch(() => setMetrics(null));
  }, [params]);

  const buildTriageLink = (extra: Record<string, string>) => {
    const p = new URLSearchParams(params.toString());
    Object.entries(extra).forEach(([key, value]) => p.set(key, value));
    return `/triage?${p.toString()}`;
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Visao geral</h1>
        <p className="text-slate-600">Resumo operacional dos ultimos 7 dias.</p>
      </div>

      <div className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-4 md:grid-cols-4">
        <label className="text-sm">
          Inicio
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
          />
        </label>
        <label className="text-sm">
          Fim
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
          />
        </label>
        <label className="text-sm">
          Região
          <input
            type="text"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="Ex: Sul, Sudeste, Norte"
            className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
          />
        </label>
        <label className="text-sm">
          Operacao
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
          >
            <option value="">Todas</option>
            <option value="active">Ativo</option>
            <option value="in_maintenance">Manutencao</option>
            <option value="out_of_service">Fora de servico</option>
          </select>
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Link
          to={buildTriageLink({ type: "delay", severity: "high" })}
          className="rounded-2xl border border-slate-200 bg-white p-4 transition hover:shadow"
        >
          <div className="text-sm text-slate-500">Com atraso</div>
          <div className="text-2xl font-semibold">{metrics?.delays_total ?? "--"}</div>
          <div className="text-xs text-slate-400">Filtro: atraso alto</div>
        </Link>
        <Link
          to={buildTriageLink({ type: "temp_out_of_range" })}
          className="rounded-2xl border border-slate-200 bg-white p-4 transition hover:shadow"
        >
          <div className="text-sm text-slate-500">Temp fora</div>
          <div className="text-2xl font-semibold">{metrics?.temp_alerts_total ?? "--"}</div>
          <div className="text-xs text-slate-400">Risco de carga</div>
        </Link>
        <Link
          to={buildTriageLink({ type: "excessive_stops" })}
          className="rounded-2xl border border-slate-200 bg-white p-4 transition hover:shadow"
        >
          <div className="text-sm text-slate-500">Paradas excessivas</div>
          <div className="text-2xl font-semibold">{metrics?.stops_total ?? "--"}</div>
          <div className="text-xs text-slate-400">Paradas acima do limite</div>
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="text-sm text-slate-500">Veiculos ativos</div>
          <div className="text-2xl font-semibold">{metrics?.active_vehicles ?? "--"}</div>
          <div className="text-xs text-slate-400">Total {metrics?.total_vehicles ?? "--"}</div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="text-sm text-slate-500">Viagens concluidas</div>
          <div className="text-2xl font-semibold">{metrics?.trips_completed ?? "--"}</div>
          <div className="text-xs text-slate-400">On-time {metrics?.on_time_rate ?? "--"}%</div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="text-sm text-slate-500">Eventos criticos</div>
          <div className="text-2xl font-semibold">{metrics?.events_critical ?? "--"}</div>
          <div className="text-xs text-slate-400">Total {metrics?.events_total ?? "--"}</div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="text-sm text-slate-500">Tendencia de alertas</div>
              <div className="text-lg font-semibold">Atrasos e temperatura</div>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics?.sample_telemetry ?? []}>
                <XAxis dataKey="day" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="delays" stroke="#f59e0b" strokeWidth={2} />
                <Line type="monotone" dataKey="temp_alerts" stroke="#14b8a6" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Ocorrencias recentes</div>
          <ul className="divide-y divide-slate-100">
            {(metrics?.recent_events ?? []).map((event) => (
              <li
                key={event.id}
                className="cursor-pointer px-4 py-3 text-sm hover:bg-slate-50"
                onClick={() => navigate(buildTriageLink({ event_id: String(event.id) }))}
              >
                <div className="font-medium text-slate-900">{event.description}</div>
                <div className="text-xs text-slate-500">
                  {event.vehicle_plate} • {event.type} • {new Date(event.timestamp).toLocaleString()}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}


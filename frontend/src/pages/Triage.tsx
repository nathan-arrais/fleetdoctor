import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";

const severityColor: Record<string, string> = {
  low: "bg-slate-100 text-slate-700",
  medium: "bg-amber-100 text-amber-800",
  high: "bg-rose-100 text-rose-800",
  critical: "bg-rose-200 text-rose-900",
};

const statusColor: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  in_maintenance: "bg-amber-100 text-amber-800",
  out_of_service: "bg-rose-100 text-rose-800",
  completed: "bg-emerald-100 text-emerald-700",
  delayed: "bg-rose-100 text-rose-800",
};

type TriageEvent = {
  id: number;
  timestamp: string;
  type: string;
  severity: string;
  region: string;
  vehicle_id: number;
  vehicle_plate: string;
  vehicle_status: string;
  trip_id: number | null;
  trip_status: string | null;
  origin: string | null;
  destination: string | null;
  driver_name: string | null;
  description: string;
  value: number | null;
  threshold: number | null;
  unit: string | null;
};

type TriageResponse = {
  items: TriageEvent[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

type Diagnosis = {
  severity: string;
  summary: string;
  probable_causes: string[];
  recommended_actions: string[];
  evidence: string[];
  source?: "llm" | "deterministic_fallback";
  model?: string | null;
  latency_ms?: number | null;
  used_tools?: string[];
  fallback_reason?: string | null;
};

function toDateInput(d: Date) {
  return d.toISOString().slice(0, 10);
}

const quickFilters = [
  { label: "Atraso", value: "delay" },
  { label: "Temperatura", value: "temp_out_of_range" },
  { label: "Paradas", value: "excessive_stops" },
  { label: "Tempo parado", value: "excessive_idle" },
];

export default function Triage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const today = useMemo(() => new Date(), []);
  const weekAgo = useMemo(() => new Date(Date.now() - 7 * 86400000), []);

  const [start, setStart] = useState(searchParams.get("start") ?? toDateInput(weekAgo));
  const [end, setEnd] = useState(searchParams.get("end") ?? toDateInput(today));
  const [type, setType] = useState(searchParams.get("type") ?? "");
  const [severity, setSeverity] = useState(searchParams.get("severity") ?? "");
  const [region, setRegion] = useState(searchParams.get("region") ?? "");
  const [status, setStatus] = useState(searchParams.get("status") ?? "");
  const [q, setQ] = useState(searchParams.get("q") ?? "");
  const [page, setPage] = useState(Number(searchParams.get("page") ?? "1"));
  const [pageSize, setPageSize] = useState(Number(searchParams.get("page_size") ?? "10"));
  const [data, setData] = useState<TriageResponse | null>(null);
  const [selected, setSelected] = useState<TriageEvent | null>(null);
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);

  const eventId = searchParams.get("event_id");

  const params = useMemo(() => {
    const p = new URLSearchParams({
      start,
      end,
      page: String(page),
      page_size: String(pageSize),
    });
    if (type) p.set("type", type);
    if (severity) p.set("severity", severity);
    if (region) p.set("region", region);
    if (status) p.set("status", status);
    if (q) p.set("q", q);
    if (eventId) p.set("event_id", eventId);
    return p;
  }, [start, end, type, severity, region, status, q, page, pageSize, eventId]);

  useEffect(() => {
    if (searchParams.toString() !== params.toString()) {
      setSearchParams(params, { replace: true });
    }
  }, [params, searchParams, setSearchParams]);

  useEffect(() => {
    apiGet<TriageResponse>(`/api/triage/events?${params.toString()}`)
      .then(setData)
      .catch(() => setData(null));
  }, [params]);

  useEffect(() => {
    if (!eventId) return;
    apiGet<TriageResponse>(`/api/triage/events?event_id=${eventId}`)
      .then((res) => setSelected(res.items[0] ?? null))
      .catch(() => setSelected(null));
  }, [eventId]);

  useEffect(() => {
    if (!selected) {
      setDiagnosis(null);
      return;
    }
    apiPost<Diagnosis>("/api/diagnosis", { event_id: selected.id })
      .then(setDiagnosis)
      .catch(() => setDiagnosis(null));
  }, [selected]);

  const clearFilters = () => {
    setType("");
    setSeverity("");
    setRegion("");
    setStatus("");
    setQ("");
    setPage(1);
  };

  const total = data?.total ?? 0;
  const startIndex = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endIndex = Math.min(page * pageSize, total);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Triagem de ocorrências</h1>
        <p className="text-slate-600">Filtre, priorize e visualize diagnósticos.</p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <input
            type="text"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
            placeholder="Buscar por placa, motorista, origem/destino ou evento..."
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm md:max-w-md"
          />
          <div className="flex flex-wrap gap-2">
            {quickFilters.map((filter) => (
              <button
                key={filter.value}
                onClick={() => {
                  setType(filter.value);
                  setPage(1);
                }}
                className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                  type === filter.value
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {filter.label}
              </button>
            ))}
            <button
              onClick={clearFilters}
              className="rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              Limpar filtros
            </button>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-6">
          <label className="text-sm">
            Início
            <input
              type="date"
              value={start}
              onChange={(e) => {
                setStart(e.target.value);
                setPage(1);
              }}
              className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
            />
          </label>
          <label className="text-sm">
            Fim
            <input
              type="date"
              value={end}
              onChange={(e) => {
                setEnd(e.target.value);
                setPage(1);
              }}
              className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
            />
          </label>
          <label className="text-sm">
            Tipo
            <select
              value={type}
              onChange={(e) => {
                setType(e.target.value);
                setPage(1);
              }}
              className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
            >
              <option value="">Todos</option>
              <option value="delay">Atraso</option>
              <option value="temp_out_of_range">Temp fora</option>
              <option value="excessive_stops">Excesso paradas</option>
              <option value="excessive_idle">Tempo parado</option>
            </select>
          </label>
          <label className="text-sm">
            Severidade
            <select
              value={severity}
              onChange={(e) => {
                setSeverity(e.target.value);
                setPage(1);
              }}
              className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
            >
              <option value="">Todas</option>
              <option value="low">Baixa</option>
              <option value="medium">Média</option>
              <option value="high">Alta</option>
              <option value="critical">Critica</option>
            </select>
          </label>
          <label className="text-sm">
            Região
            <input
              type="text"
              value={region}
              onChange={(e) => {
                setRegion(e.target.value);
                setPage(1);
              }}
              placeholder="Ex: Sul, Sudeste, Norte"
              className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
            />
          </label>
          <label className="text-sm">
            Operação
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
              className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
            >
              <option value="">Todas</option>
              <option value="active">Ativo</option>
              <option value="in_maintenance">Manutencao</option>
              <option value="out_of_service">Fora de servico</option>
            </select>
          </label>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <table className="w-full table-fixed text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="w-[140px] px-4 py-3">Data/Hora</th>
              <th className="w-[120px] px-4 py-3">Veículo</th>
              <th className="w-[110px] px-4 py-3">Viagem</th>
              <th className="w-[140px] px-4 py-3">Tipo</th>
              <th className="w-[110px] px-4 py-3">Severidade</th>
              <th className="w-[120px] px-4 py-3">Status</th>
              <th className="px-4 py-3">Resumo curto</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).map((item) => {
              const statusLabel = item.trip_status ?? item.vehicle_status;
              const summary = item.value
                ? `${item.description} (${item.value}${item.unit ? ` ${item.unit}` : ""})`
                : item.description;
              return (
                <tr
                  key={item.id}
                  className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                  onClick={() => setSelected(item)}
                >
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {new Date(item.timestamp).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-sm font-semibold text-slate-900">{item.vehicle_plate}</div>
                    <div className="text-xs text-slate-500">#{item.vehicle_id}</div>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">
                    {item.trip_id ? `#${item.trip_id}` : "-"}
                    {item.origin && item.destination ? (
                      <div className="text-xs text-slate-500">
                        {item.origin} → {item.destination}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">{item.type}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-semibold ${
                        severityColor[item.severity] ?? "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {item.severity}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-semibold ${
                        statusColor[statusLabel] ?? "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {statusLabel}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">{summary}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
          <div>
            Mostrando {startIndex}–{endIndex} de {total}
          </div>
          <div>
            Página {data?.page ?? 1} de {data?.pages ?? 1}
          </div>
          <div className="flex items-center gap-2">
            <button
              className="rounded-lg border border-slate-200 px-2 py-1"
              onClick={() => setPage(Math.max(1, page - 1))}
            >
              Anterior
            </button>
            <button
              className="rounded-lg border border-slate-200 px-2 py-1"
              onClick={() => setPage(Math.min(data?.pages ?? page + 1, page + 1))}
            >
              Proxima
            </button>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="rounded border border-slate-200 px-2 py-1"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>
        </div>
      </div>

      {selected && (
        <div className="fixed inset-0 z-20 flex justify-end bg-slate-900/30 p-4">
          <div className="h-full w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-sm text-slate-500">Evento #{selected.id}</div>
                <div className="text-lg font-semibold">{selected.description}</div>
              </div>
              <button
                className="rounded-full border border-slate-200 px-2 py-1 text-xs"
                onClick={() => {
                  setSelected(null);
                  if (eventId) {
                    const next = new URLSearchParams(params);
                    next.delete("event_id");
                    setSearchParams(next, { replace: true });
                  }
                }}
              >
                Fechar
              </button>
            </div>

            <div className="mt-4 space-y-2 text-sm text-slate-700">
              <div>
                <strong>Tipo:</strong> {selected.type}
              </div>
              <div>
                <strong>Severidade:</strong> {selected.severity}
              </div>
              <div>
                <strong>Região do veículo:</strong> {selected.region}
              </div>
              <div>
                <strong>Trip:</strong> {selected.trip_id ?? "-"}
              </div>
              <div>
                <strong>Motorista:</strong> {selected.driver_name ?? "-"}
              </div>
              <div>
                <strong>Valor:</strong> {selected.value ?? "-"} {selected.unit ?? ""}
              </div>
              <div>
                <strong>Limite:</strong> {selected.threshold ?? "-"} {selected.unit ?? ""}
              </div>
            </div>

            <div className="mt-4 flex gap-2">
              <button
                className="rounded-full border border-slate-200 px-3 py-1 text-xs"
                onClick={() => navigate(`/vehicle/${selected.vehicle_id}`)}
              >
                Abrir veículo
              </button>
              <button
                className="rounded-full border border-slate-200 px-3 py-1 text-xs"
                onClick={() => selected.trip_id && navigate(`/trip/${selected.trip_id}`)}
                disabled={!selected.trip_id}
              >
                Abrir viagem
              </button>
            </div>

            <div className="mt-6">
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-slate-800">Diagnóstico IA</div>
                {diagnosis?.source ? (
                  <span
                    className={`rounded-full px-2 py-1 text-xs font-semibold ${
                      diagnosis.source === "llm"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {diagnosis.source === "llm" ? "LLM local" : "Fallback determinístico"}
                  </span>
                ) : null}
              </div>
              {diagnosis ? (
                <div className="mt-2 space-y-4 text-sm text-slate-700">
                  {(diagnosis.model || diagnosis.latency_ms) && (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                      {diagnosis.model ? <div><strong>Modelo:</strong> {diagnosis.model}</div> : null}
                      {diagnosis.latency_ms ? <div><strong>Latencia:</strong> {diagnosis.latency_ms} ms</div> : null}
                    </div>
                  )}
                  <div>
                    <div className="text-xs uppercase text-slate-400">Resumo</div>
                    <p className="mt-1 text-sm leading-6">{diagnosis.summary}</p>
                  </div>
                  <div>
                    <div className="text-xs uppercase text-slate-400">Causas prováveis</div>
                    <ul className="mt-1 list-disc pl-4">
                      {diagnosis.probable_causes.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="text-xs uppercase text-slate-400">Acoes recomendadas</div>
                    <ul className="mt-1 list-disc pl-4">
                      {diagnosis.recommended_actions.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="text-xs uppercase text-slate-400">Evidencias</div>
                    <ul className="mt-1 list-disc pl-4">
                      {diagnosis.evidence.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  {diagnosis.used_tools && diagnosis.used_tools.length > 0 ? (
                    <div>
                      <div className="text-xs uppercase text-slate-400">Tools usadas</div>
                      <div className="mt-1 text-xs text-slate-600">{diagnosis.used_tools.join(", ")}</div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="mt-2 text-sm text-slate-500">Carregando diagnóstico...</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

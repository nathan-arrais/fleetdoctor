import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../api/client";

type Report = {
  id: number;
  created_at: string;
  report_type: string;
  start: string;
  end: string;
  region: string | null;
  status_filter: string | null;
  type_filter: string | null;
  severity_filter: string | null;
  query_filter: string | null;
  file_name: string;
  preview_url?: string;
  download_url?: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function toDateInput(d: Date) {
  return d.toISOString().slice(0, 10);
}

export default function Reports() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  const today = useMemo(() => new Date(), []);
  const twoWeeksAgo = useMemo(() => new Date(Date.now() - 14 * 86400000), []);

  const [start, setStart] = useState(toDateInput(twoWeeksAgo));
  const [end, setEnd] = useState(toDateInput(today));
  const [region, setRegion] = useState("");
  const [status, setStatus] = useState("");
  const [eventType, setEventType] = useState("");
  const [severity, setSeverity] = useState("");
  const [q, setQ] = useState("");

  const load = () => {
    setLoading(true);
    return apiGet<Report[]>("/api/reports")
      .then(setReports)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const generate = async () => {
    setGenerating(true);
    try {
      await apiPost<Report>("/api/reports/generate", {
        type: "executive",
        start,
        end,
        region: region || null,
        status: status || null,
        event_type: eventType || null,
        severity: severity || null,
        q: q || null,
      });
      await load();
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Relatorios</h1>
        <p className="text-slate-600">Gere um relatorio executivo com resumo operacional.</p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="grid gap-4 md:grid-cols-4">
          <label className="text-sm">
            Inicio
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
            />
          </label>
          <label className="text-sm">
            Fim
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
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
          <label className="text-sm">
            Tipo
            <select
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
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
              onChange={(e) => setSeverity(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
            >
              <option value="">Todas</option>
              <option value="low">Baixa</option>
              <option value="medium">Media</option>
              <option value="high">Alta</option>
              <option value="critical">Critica</option>
            </select>
          </label>
          <label className="text-sm md:col-span-2">
            Buscar
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Placa, motorista, origem/destino..."
              className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1"
            />
          </label>
        </div>
        <button
          onClick={generate}
          disabled={generating}
          className="mt-4 rounded-full bg-slate-900 px-4 py-2 text-sm text-white"
        >
          {generating ? "Gerando..." : "Gerar relatorio"}
        </button>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold">Relatorios gerados</div>
        {loading ? (
          <div className="px-4 py-6 text-sm text-slate-500">Carregando...</div>
        ) : reports.length === 0 ? (
          <div className="px-4 py-6 text-sm text-slate-500">
            Nenhum relatorio gerado. Use os filtros acima e clique em "Gerar relatorio".
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Criado</th>
                <th className="px-4 py-3">Periodo</th>
                <th className="px-4 py-3">Filtros</th>
                <th className="px-4 py-3">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <tr key={report.id} className="border-t border-slate-100">
                  <td className="px-4 py-3">{new Date(report.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3">{report.start} - {report.end}</td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {report.region ?? "Todas"} • {report.status_filter ?? "Todas"} • {report.type_filter ?? "Todos"} • {report.severity_filter ?? "Todas"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-3 text-sm font-semibold text-slate-700">
                      <a
                        href={`${API_BASE}${report.preview_url}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Preview
                      </a>
                      <a
                        href={`${API_BASE}${report.download_url}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Download
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}


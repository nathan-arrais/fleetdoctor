import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const requiredColumns = [
  "vehicle_id",
  "plate",
  "trip_id",
  "event_type",
  "severity",
  "timestamp",
  "description",
];

type PreviewResponse = {
  columns: string[];
  rows: Record<string, string>[];
};

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const missing = requiredColumns.filter((c) => !preview?.columns?.includes(c));

  const handleFile = async (selected: File) => {
    setFile(selected);
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const form = new FormData();
      form.append("file", selected);
      const res = await fetch(`${API_BASE}/api/upload/preview`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || "Falha no preview");
      }
      const data = (await res.json()) as PreviewResponse;
      setPreview(data);
    } catch (err) {
      setPreview(null);
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    setError(null);
    setSuccess(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/api/upload/import`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || "Falha na importação");
      }
      const data = await res.json();
      setSuccess(`Importado com sucesso: ${data.imported} eventos.`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setImporting(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await fetch(`${API_BASE}/api/upload/reset`, { method: "POST" });
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || "Falha no reset");
      }
      setSuccess("Dados demo carregados novamente.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Upload de CSV</h1>
        <p className="text-slate-600">Envie um CSV para importar eventos na base.</p>
      </div>

      <div
        className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const dropped = e.dataTransfer.files?.[0];
          if (dropped) {
            handleFile(dropped);
          }
        }}
      >
        <input
          type="file"
          accept=".csv"
          onChange={(e) => {
            const selected = e.target.files?.[0];
            if (selected) {
              handleFile(selected);
            }
          }}
          className="hidden"
          id="csv-input"
        />
        <label htmlFor="csv-input" className="cursor-pointer text-sm font-semibold text-slate-700">
          Arraste seu CSV aqui ou clique para selecionar
        </label>
      </div>

      {loading && <div className="text-sm text-slate-500">Lendo arquivo...</div>}
      {error && <div className="text-sm text-rose-600">Erro: {error}</div>}
      {success && <div className="text-sm text-emerald-600">{success}</div>}

      {preview && (
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-semibold">Validação de colunas</div>
          <ul className="mt-2 text-sm">
            {requiredColumns.map((col) => (
              <li key={col} className={preview.columns.includes(col) ? "text-emerald-600" : "text-rose-600"}>
                {preview.columns.includes(col) ? "✓" : "✗"} {col}
              </li>
            ))}
          </ul>

          <div className="mt-4 text-sm font-semibold">Preview (top 10 linhas)</div>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-[10px] uppercase text-slate-500">
                <tr>
                  {preview.columns.map((col) => (
                    <th key={col} className="px-2 py-2">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, idx) => (
                  <tr key={idx} className="border-t border-slate-100">
                    {preview.columns.map((col) => (
                      <td key={col} className="px-2 py-2">
                        {row[col]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              onClick={handleImport}
              disabled={importing || missing.length > 0}
              className="rounded-full bg-slate-900 px-4 py-2 text-sm text-white"
            >
              {importing ? "Importando..." : "Importar"}
            </button>
            <button
              onClick={() => setConfirmReset(true)}
              disabled={resetting}
              className="rounded-full border border-slate-200 px-4 py-2 text-sm text-slate-700"
            >
              {resetting ? "Carregando..." : "Apagar importados e voltar ao demo"}
            </button>
          </div>
        </div>
      )}

      {confirmReset && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="text-lg font-semibold">Confirmar reset</div>
            <p className="mt-2 text-sm text-slate-600">
              Isso apaga dados importados e restaura o dataset demo. Deseja continuar?
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                className="rounded-full border border-slate-200 px-4 py-2 text-sm text-slate-700"
                onClick={() => setConfirmReset(false)}
              >
                Cancelar
              </button>
              <button
                className="rounded-full bg-slate-900 px-4 py-2 text-sm text-white"
                onClick={() => {
                  setConfirmReset(false);
                  handleReset();
                }}
              >
                Confirmar reset
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="text-xs text-slate-500">
        Baixe um exemplo: <a className="underline" href="/sample_upload.csv">sample_upload.csv</a>
      </div>
    </div>
  );
}

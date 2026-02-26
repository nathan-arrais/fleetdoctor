import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost } from "../api/client";

type ChatSession = {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
};

type ChatMessage = {
  id: number;
  session_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  source?: "llm" | "deterministic_fallback" | null;
  model?: string | null;
  latency_ms?: number | null;
  used_tools: string[];
  fallback_reason?: string | null;
  validation_warnings: string[];
  citations: string[];
  follow_up_questions: string[];
};

type ChatAskResponse = {
  session_id: number;
  answer: string;
  citations: string[];
  follow_up_questions: string[];
  source?: "llm" | "deterministic_fallback" | null;
  model?: string | null;
  latency_ms?: number | null;
  used_tools: string[];
  fallback_reason?: string | null;
  validation_warnings: string[];
  user_message: ChatMessage;
  assistant_message: ChatMessage;
};

export default function Chat() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? null,
    [sessions, activeSessionId],
  );

  useEffect(() => {
    void bootstrapSessions();
  }, []);

  useEffect(() => {
    if (!activeSessionId) return;
    void fetchMessages(activeSessionId);
  }, [activeSessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function bootstrapSessions() {
    setLoadingSessions(true);
    setError(null);
    try {
      const loaded = await apiGet<ChatSession[]>("/api/chat/sessions");
      if (loaded.length > 0) {
        setSessions(loaded);
        setActiveSessionId((current) => current ?? loaded[0].id);
      } else {
        const created = await apiPost<ChatSession>("/api/chat/sessions", { title: null });
        setSessions([created]);
        setActiveSessionId(created.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar sessões");
    } finally {
      setLoadingSessions(false);
    }
  }

  async function fetchMessages(sessionId: number) {
    setLoadingMessages(true);
    setError(null);
    try {
      const loaded = await apiGet<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages?limit=200`);
      setMessages(loaded);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar mensagens");
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  }

  async function createSession() {
    setError(null);
    try {
      const created = await apiPost<ChatSession>("/api/chat/sessions", { title: null });
      setSessions((current) => [created, ...current]);
      setActiveSessionId(created.id);
      setMessages([]);
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar sessão");
    }
  }

  async function submitMessage(event: FormEvent) {
    event.preventDefault();
    if (sending) return;
    if (!draft.trim()) return;

    let sessionId = activeSessionId;
    if (!sessionId) {
      try {
        const created = await apiPost<ChatSession>("/api/chat/sessions", { title: null });
        setSessions((current) => [created, ...current]);
        sessionId = created.id;
        setActiveSessionId(created.id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Falha ao criar sessão");
        return;
      }
    }

    const message = draft.trim();
    setDraft("");
    setSending(true);
    setError(null);
    try {
      const response = await apiPost<ChatAskResponse>("/api/chat/ask", {
        session_id: sessionId,
        message,
      });

      setMessages((current) => [...current, response.user_message, response.assistant_message]);
      setSessions((current) =>
        current
          .map((session) =>
            session.id === response.session_id
              ? { ...session, updated_at: response.assistant_message.created_at }
              : session,
          )
          .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao enviar mensagem");
      setDraft(message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[280px,1fr]">
      <aside className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">Chat da frota</h1>
            <p className="text-xs text-slate-500">Perguntas sobre KPI, triagem, veículos e viagens.</p>
          </div>
          <button
            onClick={createSession}
            className="rounded-lg border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Nova
          </button>
        </div>
        <div className="space-y-2">
          {loadingSessions ? (
            <div className="text-sm text-slate-500">Carregando sessões...</div>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => setActiveSessionId(session.id)}
                className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition ${
                  activeSessionId === session.id
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-200 text-slate-700 hover:bg-slate-50"
                }`}
              >
                <div className="truncate font-semibold">{session.title}</div>
                <div className={`text-xs ${activeSessionId === session.id ? "text-slate-200" : "text-slate-500"}`}>
                  {new Date(session.updated_at).toLocaleString()}
                </div>
              </button>
            ))
          )}
        </div>
      </aside>

      <section className="flex min-h-[70vh] flex-col rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-4 py-3">
          <div className="text-sm font-semibold text-slate-800">{activeSession?.title ?? "Conversa"}</div>
          <div className="text-xs text-slate-500">Agente com LLM local + fallback determinístico</div>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {loadingMessages ? <div className="text-sm text-slate-500">Carregando mensagens...</div> : null}
          {!loadingMessages && messages.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">
              Pergunte algo como:
              <div className="mt-2 space-y-1 text-xs">
                <div>- "Quais os principais riscos da semana?"</div>
                <div>- "Resumo do dashboard dos últimos 7 dias"</div>
                <div>- "Analise o veículo 3"</div>
                <div>- "Como foi a viagem 12?"</div>
              </div>
            </div>
          ) : null}

          {messages.map((message) => {
            const isUser = message.role === "user";
            return (
              <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[92%] rounded-2xl border px-4 py-3 text-sm ${
                    isUser
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 bg-slate-50 text-slate-800"
                  }`}
                >
                  <div className="whitespace-pre-wrap leading-6">{message.content}</div>
                  {!isUser ? (
                    <div className="mt-3 space-y-2 text-xs text-slate-600">
                      <div className="flex flex-wrap items-center gap-2">
                        {message.source ? (
                          <span
                            className={`rounded-full px-2 py-1 font-semibold ${
                              message.source === "llm"
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {message.source === "llm" ? "LLM local" : "Fallback"}
                          </span>
                        ) : null}
                        {message.model ? <span>Modelo: {message.model}</span> : null}
                        {message.latency_ms ? <span>Latência: {message.latency_ms} ms</span> : null}
                      </div>
                      {message.used_tools.length > 0 ? <div>Tools: {message.used_tools.join(", ")}</div> : null}
                      {message.citations.length > 0 ? <div>Citações: {message.citations.join(", ")}</div> : null}
                      {message.validation_warnings.length > 0 ? (
                        <div className="text-amber-700">
                          Avisos: {message.validation_warnings.join(" | ")}
                        </div>
                      ) : null}
                      {message.follow_up_questions.length > 0 ? (
                        <div className="space-y-1">
                          <div className="font-semibold text-slate-700">Sugestões:</div>
                          {message.follow_up_questions.map((question) => (
                            <div key={question}>- {question}</div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}

          {sending ? <div className="text-xs text-slate-500">Agente analisando contexto...</div> : null}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={submitMessage} className="border-t border-slate-100 p-4">
          <div className="flex gap-2">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Pergunte sobre eventos, veículos, viagens ou KPIs..."
              rows={2}
              className="w-full resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={sending || !draft.trim()}
              className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              Enviar
            </button>
          </div>
          {error ? <div className="mt-2 text-xs text-rose-700">{error}</div> : null}
        </form>
      </section>
    </div>
  );
}

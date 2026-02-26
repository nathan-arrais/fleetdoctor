# FleetDoctor

Assistente de diagnóstico operacional para frotas com **IA generativa local** integrada ao fluxo de triagem.

## 1) Problema e solução

Em operações de frota, o gargalo não é detectar evento, e sim transformar sinal em decisão acionável.

Problemas comuns:
- alertas demais e pouca priorização
- investigação lenta entre telas/sistemas
- diagnóstico inconsistente entre analistas

Solução no FleetDoctor:
- triagem operacional com filtros e drill-down
- diagnóstico por evento/viagem usando **LLM local + fallback determinístico**
- chat operacional para perguntas livres sobre KPI, triagem, veículos e viagens
- geração de relatório executivo em HTML
- importação de eventos por CSV

## 2) Arquitetura de LLM

Fluxo de diagnóstico (`POST /api/diagnosis`):

```mermaid
flowchart TD
    A[Usuario seleciona evento/viagem] --> B[FastAPI /api/diagnosis]
    B --> C[LangGraph]
    C --> C1[prepare_context]
    C --> C2[execute_tools]
    C --> C3[run_llm Ollama]
    C --> C4[validate_output JSON/schema]
    C4 -->|ok| D[Resposta source=llm]
    C4 -->|erro/timeout/json inválido| E[fallback determinístico]
    E --> F[Resposta source=deterministic_fallback]
```

Stack:
- Frontend: React + Vite + TypeScript + Tailwind + Recharts
- Backend: FastAPI + SQLAlchemy
- LLM orchestration: LangGraph
- Modelo local: Ollama
- Persistencia: SQLite local

## 3) Modelo local escolhido e trade-offs

Escolha: **Ollama** com modelo primário + fallback de modelo.

Modelos recomendados para esta versão:
- primário: `qwen2.5:7b`
- fallback: `llama3.1:8b`

Comandos sugeridos:
```bash
ollama pull qwen2.5:7b
ollama pull llama3.1:8b
```

Motivos:
- custo zero por chamada
- privacidade local
- controle de latência e disponibilidade

Trade-offs:
- qualidade textual pode variar mais que APIs pagas
- modelos menores tendem a ser mais genericos
- setup local exige ambiente preparado

Se trocar para API paga:
- ganho esperado: qualidade de raciocínio e tool calling mais robusto
- perda esperada: custo por uso e menor controle de dados locais

## 4) Framework escolhido

Escolha: **LangGraph simples** (single graph) em vez de multiagente.

Justificativa:
- controla explicitamente o fluxo de contexto -> tools -> modelo -> validação -> fallback
- menor complexidade operacional para prazo curto
- suficiente para demonstrar decisão de engenharia de framework

Implementação do grafo:
- [backend/app/agents/langgraph_diagnosis_graph.py](backend/app/agents/langgraph_diagnosis_graph.py)

## 5) Prompts e estratégia de prompting

Arquivos:
- [prompts/system_prompt.txt](prompts/system_prompt.txt)
- [prompts/diagnosis_event_template.txt](prompts/diagnosis_event_template.txt)
- [prompts/diagnosis_trip_template.txt](prompts/diagnosis_trip_template.txt)
- [prompts/chat_system_prompt.txt](prompts/chat_system_prompt.txt)
- [prompts/chat_response_template.txt](prompts/chat_response_template.txt)

Estrategia aplicada:
- system prompt com regras de comportamento e formato JSON estrito
- templates separados por modo (evento vs viagem)
- delimitação clara entre instruções e dados operacionais
- mitigação de prompt injection: campos textuais tratados como dados, nunca como instrução

## 6) Tools disponibilizadas ao LLM

Especificação completa:
- [tools/diagnosis_tools_spec.md](tools/diagnosis_tools_spec.md)
- [tools/chat_tools_spec.md](tools/chat_tools_spec.md)

Tools:
- `get_event_context(event_id)`
- `get_trip_context(trip_id)`
- `get_similar_events(event_type, region, limit)`
- `get_vehicle_recent_history(vehicle_id, days)`

Implementação backend:
- [backend/app/services/diagnosis_tools.py](backend/app/services/diagnosis_tools.py)

## 7) Parametros do modelo

Configurações por ambiente:
- `LLM_PROVIDER` (default `ollama`)
- `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- `OLLAMA_MODEL_PRIMARY` (default `qwen2.5:7b`)
- `OLLAMA_MODEL_FALLBACK` (default `llama3.1:8b`)
- `OLLAMA_CHAT_MODEL_PRIMARY` (default `qwen3:4b`)
- `OLLAMA_CHAT_MODEL_FALLBACK` (default `qwen2.5:7b`)
- `LLM_TEMPERATURE` (default `0.2`)
- `LLM_TOP_P` (default `0.9`)
- `LLM_MAX_TOKENS` (default `500`)
- `LLM_TIMEOUT_MS` (default `30000`)
- `LLM_CONNECT_TIMEOUT_MS` (default `2000`)
- `LLM_READ_TIMEOUT_MS` (default `30000`)
- `LLM_CHAT_TIMEOUT_MS` (default `120000`)
- `LLM_CHAT_MAX_TOKENS` (default `220`)
- `LLM_CHAT_DISABLE_THINKING` (default `true`)
- `OLLAMA_KEEP_ALIVE` (default `10m`)
- `LLM_WARMUP_ON_STARTUP` (default `true`)
- `LLM_RETRY_JSON_INVALID` (default `1`)
- `LLM_CHAT_RETRY_JSON_INVALID` (default `1`)
- `LLM_FORCE_DETERMINISTIC` (força fallback para testes/demo)

Racional:
- temperatura baixa para consistência
- top-p moderado para manter variação controlada
- timeout maior para absorver cold start local dos modelos
- chat com modelo menor e timeout próprio para reduzir fallback por timeout
- chat com `thinking` desativado para reduzir latência e variabilidade de formato
- warmup para reduzir fallback por primeira chamada (incluindo modelos de diagnóstico e de chat)
- chat com até 3 tentativas por requisição e retry de timeout transitório (cold start) antes de trocar de modelo
- retry curto para respostas sem JSON válido

## 8) Contrato de API de diagnóstico

Endpoint: `POST /api/diagnosis`

Request:
```json
{
  "event_id": 12,
  "debug": false,
  "force_deterministic": false
}
```

Response (compativel + metadados opcionais):
```json
{
  "severity": "high",
  "summary": "...",
  "probable_causes": ["..."],
  "recommended_actions": ["..."],
  "evidence": ["..."],
  "source": "llm",
  "model": "qwen2.5:7b",
  "latency_ms": 842,
  "used_tools": ["get_event_context", "get_similar_events", "get_vehicle_recent_history"],
  "fallback_reason": null,
  "validation_warnings": []
}
```

Health da camada LLM:
- `GET /api/llm/health`

## 9) Contrato de API de chat

Criar sessão:
```bash
curl -X POST "http://localhost:8000/api/chat/sessions" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Análise operacional\"}"
```

Enviar pergunta:
```bash
curl -X POST "http://localhost:8000/api/chat/ask" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":1,\"message\":\"Quais os principais riscos da semana?\"}"
```

Resposta (resumo):
```json
{
  "session_id": 1,
  "answer": "...",
  "citations": ["get_dashboard_snapshot", "get_top_risks"],
  "source": "llm",
  "used_tools": ["get_dashboard_snapshot", "get_top_risks"]
}
```

## 10) O que funcionou

- arquitetura híbrida evitou quebra funcional quando modelo local falha
- JSON schema + validação reduziu respostas malformadas
- tools de contexto melhoraram utilidade das recomendações
- contrato da API foi mantido para o frontend existente

## 11) O que não funcionou / limitações

- modelo local pequeno pode produzir recomendações genéricas
- sem RAG nesta versão (usa somente contexto transacional atual)
- sem score probabilístico calibrado
- `upload/reset` continua destrutivo para contexto produtivo

## 12) Estrutura do repositorio

```text
fleetdoctor/
  prompts/
    system_prompt.txt
    diagnosis_event_template.txt
    diagnosis_trip_template.txt
    chat_system_prompt.txt
    chat_response_template.txt
  tools/
    diagnosis_tools_spec.md
    chat_tools_spec.md
  agents/
    README.md
  backend/
    app/
      agents/
        langgraph_diagnosis_graph.py
        langgraph_chat_graph.py
      routers/
        diagnosis.py
        llm.py
        chat.py
      services/
        diagnosis_engine.py
        diagnosis_tools.py
        chat_engine.py
        chat_tools.py
        llm_provider.py
        output_validation.py
        diagnostics.py
    tests/
      routers/
        test_health.py
        test_diagnosis.py
        test_reports.py
        test_upload.py
        test_llm.py
        test_chat.py
      services/
        test_output_validation.py
  frontend/
    src/pages/
      Triage.tsx
      Chat.tsx
  docs/
    pitch_3min.md
```

## 13) Como executar

### Requisitos
- Python 3.11+
- Node.js 20+
- npm 10+
- Ollama instalado localmente

### Backend
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.seed
uvicorn app.main:app --reload
```

Observação:
- o backend carrega automaticamente `backend/.env` no startup (sem precisar exportar variáveis no terminal)

Validação rápida da camada LLM:
```bash
curl "http://localhost:8000/api/llm/health"
```

### Frontend
```bash
cd frontend
copy .env.example .env
npm install
npm run dev
```

Rota de chat:
- `http://localhost:5173/chat`

### Testes backend
```bash
cd backend
pip install -r requirements-dev.txt
pytest -q tests -p no:cacheprovider
```

## 14) CI

Workflow em:
- `.github/workflows/ci.yml`

Executa:
- `pytest` backend
- `npm run build` frontend

## 15) Roteiro de apresentação

- [docs/pitch_3min.md](docs/pitch_3min.md)
- [docs/checklist_apresentacao_3min.md](docs/checklist_apresentacao_3min.md)

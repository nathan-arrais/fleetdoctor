# Checklist de Apresentação (3 minutos)

## 1) Roteiro por tempo

### 0:00-0:30 — Problema e solução (1 frase)
- "O FleetDoctor transforma eventos de frota em diagnóstico acionável usando LLM local com fallback determinístico."
- "A IA entra em dois fluxos: diagnóstico por evento/viagem e chat operacional com tools."

### 0:30-2:30 — Decisões de engenharia de LLM (núcleo)
- Modelo/provedor:
  - Ollama local.
  - Motivos: custo zero por chamada, privacidade local, autonomia de ambiente.
  - Trade-off: maior variação de qualidade e latência que API paga.
- Framework:
  - LangGraph (single graph), não multiagente.
  - Motivo: fluxo explícito e controlado (`contexto -> tools -> LLM -> validação -> fallback`).
- Prompting:
  - System prompt separado em arquivo (`prompts/system_prompt.txt` e `prompts/chat_system_prompt.txt`).
  - Regras claras de comportamento, anti-injection e saída JSON estrita.
- Parâmetros:
  - Temperatura baixa (`0.2`), `top_p` moderado (`0.9`), timeouts explícitos.
  - Chat com timeout próprio (`LLM_CHAT_TIMEOUT_MS=120000`), `disable_thinking=true`, retry de JSON e retry de timeout transitório.
- Tools:
  - Diagnóstico: `get_event_context`, `get_trip_context`, `get_similar_events`, `get_vehicle_recent_history`.
  - Chat: `get_dashboard_snapshot`, `search_events`, `get_vehicle_overview`, `get_trip_overview`, `get_top_risks`.
  - Motivo: ancorar resposta em dados transacionais e reduzir alucinação.
- Structured output e fallback:
  - Saída validada por schema/parse.
  - Se falhar: fallback determinístico com metadados (`source`, `fallback_reason`, `validation_warnings`).

### 2:30-3:00 — O que funcionou e não funcionou
- Funcionou:
  - Resposta contextualizada com citação de tools.
  - Robustez por fallback sem quebrar contrato de API.
- Não funcionou:
  - Timeout/cold start e respostas genéricas em modelo local menor.
- Mitigações:
  - Warmup no startup, timeout maior no chat, retry de timeout, validação de JSON.

## 2) Frases curtas para justificar trade-offs
- "Preferi previsibilidade de fluxo com LangGraph em vez de complexidade de multiagente."
- "Tool calling foi desenhado para reduzir alucinação e aumentar rastreabilidade."
- "Temperatura baixa prioriza consistência operacional em vez de criatividade."
- "Fallback determinístico evita indisponibilidade funcional quando o modelo local falha."
- "Modelo local prioriza custo e privacidade; API paga elevaria qualidade e robustez de tool calling."

## 3) Perguntas prováveis e respostas rápidas

### "Por que temperatura 0.2 e não 0.7?"
- Porque o caso é operacional: consistência e repetibilidade são mais importantes que criatividade.

### "Por que LangGraph e não chamada direta?"
- Porque preciso controlar etapas e fallback explicitamente; isso facilita depuração e confiabilidade.

### "Como você trata prompt injection?"
- O prompt força tratamento de input do usuário como dado, com contexto estruturado vindo de tools e validação de saída.

### "O que muda se usar API paga?"
- Melhora qualidade textual, tool calling e estabilidade; perde em custo por uso e privacidade local.

### "Quando cai no fallback?"
- Em timeout, resposta vazia ou JSON inválido; o sistema devolve resposta segura e sinaliza metadados de falha.

## 4) Checklist de pré-apresentação (5 minutos antes)
- Backend e frontend no ar.
- `GET /api/llm/health` respondendo com `provider=ollama` e modelos carregados.
- Um exemplo de diagnóstico funcionando (`POST /api/diagnosis`).
- Um exemplo de chat funcionando (`POST /api/chat/ask`).
- Plano B pronto: se LLM falhar, demonstrar fallback e explicar por que ele existe.

## 5) Comandos de conferência rápida

```bash
# Backend
cd backend
pytest -q tests -p no:cacheprovider

# Health da camada LLM
curl "http://localhost:8000/api/llm/health"

# Frontend
cd ../frontend
npm run build
```

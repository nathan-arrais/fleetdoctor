# Pitch de 3 minutos

## 1) O que o sistema faz (30s)
- FleetDoctor prioriza ocorrências de frota, gera diagnóstico operacional com IA e oferece chat para perguntas livres sobre a operação.
- O backend combina contexto de eventos/viagens/KPIs e produz respostas acionáveis.

## 2) Decisões de engenharia de LLM (2min)
- Modelo: local via Ollama (custo zero por chamada e privacidade).
- Framework: LangGraph simples para controlar fluxo e fallback.
- Prompt: system prompt com JSON estrito, guardrails anti-injeção e estilo operacional.
- Parâmetros: perfis dedicados por fluxo.
  - Diagnóstico: `qwen3:4b`, `LLM_DIAG_TIMEOUT_MS=60000`, `response_format_json=true`, `disable_thinking=true`.
  - Chat: `qwen3:4b` com fallback `qwen2.5:7b`, `LLM_CHAT_TIMEOUT_MS=120000`.
- Tools: diagnóstico com contexto operacional e chat com ferramentas de dashboard/triagem/veículo/viagem, incluindo `get_driver_last_trip`.
- Fallback: se modelo falhar ou JSON vier inválido, usa motor determinístico sem quebrar contrato da API.

## 3) O que funcionou e não funcionou (30s)
- Funcionou: respostas mais contextualizadas mantendo contrato de API.
- Não funcionou: com modelo local pequeno, algumas respostas vieram genéricas.
- Mitigação: validação estrutural, warmup e fallback determinístico.

Checklist completo:
- [checklist_apresentacao_3min.md](checklist_apresentacao_3min.md)

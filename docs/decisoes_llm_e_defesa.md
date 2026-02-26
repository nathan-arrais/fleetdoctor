# Decisões de Engenharia de LLM e Guia de Defesa

## 1) Escolha dos modelos

### Diagnóstico (endpoint `/api/diagnosis`)
- Modelo primário: `qwen3:4b`
- Modelo fallback: `qwen3:4b` (perfil estável por padrão)

Motivos:
- Menor latência para uso no drawer sem sacrificar consistência de saída.
- Perfil dedicado para diagnóstico com timeout e parâmetros próprios.
- Saída em JSON estrito para reduzir fallback por erro de formatação.

Trade-offs aceitos:
- Modelo menor pode gerar texto mais simples em casos ambíguos.
- Em hardware local fraco, ainda pode haver timeout em picos.

### Chat operacional (endpoint `/api/chat/ask`)
- Modelo primário: `qwen3:4b`
- Modelo fallback: `qwen2.5:7b`

Motivos:
- Baixa latência para perguntas frequentes.
- Fallback para modelo diferente quando houver erro/timeout.
- Suporte a consultas por motorista via `get_driver_last_trip`.

Trade-offs aceitos:
- Perguntas muito abertas podem vir com respostas mais conservadoras.
- Dependência de disponibilidade local do Ollama.

## 2) Por que LangGraph

Escolha: **LangGraph single-graph** (sem multiagente).

Motivos principais:
- Fluxo explícito e auditável: `prepare_context -> execute_tools -> run_llm -> validate_output -> fallback`.
- Controle de erros por etapa, com retry e fallback claros.
- Menor complexidade operacional para o escopo do projeto.

Por que não chamada direta simples:
- Ficaria mais frágil para orquestrar validação, retries condicionais e fallback consistente.

## 3) Estratégia de prompts

Arquivos:
- `prompts/system_prompt.txt` (diagnóstico)
- `prompts/chat_system_prompt.txt` (chat)
- `prompts/diagnosis_event_template.txt`
- `prompts/diagnosis_trip_template.txt`
- `prompts/chat_response_template.txt`

Decisões adotadas:
- Prompt separado por contexto (diagnóstico vs chat).
- Instruções de segurança para tratar entrada como dado, não instrução.
- Requisito de saída JSON estrita.
- Templates com contexto estruturado das tools.

Efeito esperado:
- Menos alucinação.
- Resposta mais rastreável (`used_tools`, `citations`).
- Menor variabilidade de formato.

## 4) Escolha de parâmetros

Parâmetros base:
- `LLM_TEMPERATURE = 0.2`
- `LLM_TOP_P = 0.9`
- `LLM_MAX_TOKENS = 500`
- `LLM_TIMEOUT_MS = 30000`

Perfil de diagnóstico:
- `OLLAMA_DIAG_MODEL_PRIMARY = qwen3:4b`
- `OLLAMA_DIAG_MODEL_FALLBACK = qwen3:4b`
- `LLM_DIAG_TIMEOUT_MS = 60000`
- `LLM_DIAG_MAX_TOKENS = 320`
- `LLM_DIAG_DISABLE_THINKING = true`
- `LLM_DIAG_RETRY_JSON_INVALID = 1`

Perfil de chat:
- `OLLAMA_CHAT_MODEL_PRIMARY = qwen3:4b`
- `OLLAMA_CHAT_MODEL_FALLBACK = qwen2.5:7b`
- `LLM_CHAT_TIMEOUT_MS = 120000`
- `LLM_CHAT_MAX_TOKENS = 220`
- `LLM_CHAT_DISABLE_THINKING = true`
- `LLM_CHAT_RETRY_JSON_INVALID = 1`

Racional:
- Temperatura baixa para consistência operacional.
- Timeout dedicado por fluxo para reduzir fallback indevido.
- `disable_thinking=true` para reduzir risco de saída fora de JSON.

## 5) Confiabilidade e fallback

Mecanismos:
- Validação estruturada da saída (`output_validation.py`).
- Retry curto para JSON inválido.
- Retry de timeout transitório no chat.
- Fallback determinístico com metadados (`source`, `fallback_reason`, `validation_warnings`).
- Warmup no startup com modelos de diagnóstico e chat.

Por que isso importa:
- Em operação, disponibilidade e previsibilidade são prioridades.
- Mesmo com falha de LLM, o usuário recebe resposta útil.

## 6) Ferramentas (tools) e ancoragem em dados

Diagnóstico:
- `get_event_context`
- `get_trip_context`
- `get_similar_events`
- `get_vehicle_recent_history`

Chat:
- `get_dashboard_snapshot`
- `search_events`
- `get_driver_last_trip`
- `get_vehicle_overview`
- `get_trip_overview`
- `get_top_risks`

## 7) Se migrar para API paga, o que muda

Ganhos esperados:
- Melhor qualidade média de resposta.
- Maior robustez de structured output e tool calling.
- Menor incidência de timeout/cold start.

Custos/perdas:
- Custo recorrente por requisição.
- Menor controle de privacidade local.
- Dependência externa maior.

## 8) Perguntas prováveis do professor e respostas adequadas

### 1. "Por que usar modelo local em vez de API paga?"
Porque priorizamos custo zero por chamada, privacidade local e autonomia de ambiente.

### 2. "Por que LangGraph e não chamada direta?"
Porque o fluxo com validação, retry e fallback precisa ser explícito e auditável.

### 3. "Como você reduz prompt injection?"
Com system prompt restritivo e contexto vindo de tools estruturadas.

### 4. "Como garante JSON válido?"
Com validação pós-modelo, retry curto e fallback determinístico quando necessário.

### 5. "Quando o fallback é acionado?"
Em timeout, resposta vazia, parse inválido ou ausência de campos obrigatórios.

### 6. "Como você monitora a camada LLM?"
Via `GET /api/llm/health`, que expõe `chat` e `diagnosis`, modelos e timeouts.

### 7. "Por que diagnóstico e chat têm perfis diferentes?"
Porque o comportamento de uso é diferente: diagnóstico precisa estabilidade no drawer; chat precisa baixa latência com perguntas diversas.

### 8. "Quais limitações observadas?"
Respostas mais conservadoras em perguntas abertas e sensibilidade a hardware local.

### 9. "Como mitigou essas limitações?"
Warmup, timeout dedicado por fluxo, validação estrutural e fallback transparente.

### 10. "O que foi adicionado no chat recentemente?"
Consulta por motorista (`get_driver_last_trip`) com desambiguação por trip/placa.

## 9) Resumo para fechar a defesa

"A solução foi desenhada para operação real: respostas úteis, auditáveis e resilientes. Quando a LLM falha, o sistema degrada com segurança e mantém continuidade."

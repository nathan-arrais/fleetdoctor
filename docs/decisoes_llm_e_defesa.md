# Decisões de Engenharia de LLM e Guia de Defesa

## 1) Visão geral da arquitetura de IA

O projeto tem dois fluxos de IA separados:
- Diagnóstico (`POST /api/diagnosis`): foco em explicar um evento ou uma viagem com saída estruturada.
- Chat (`POST /api/chat/ask`): foco em perguntas operacionais livres (KPI, triagem, veículo, viagem, motorista).

Os dois fluxos seguem o mesmo princípio:
1. Coletar contexto real do banco via tools.
2. Montar prompts com esse contexto estruturado.
3. Chamar a LLM local (Ollama) pedindo JSON.
4. Validar saída.
5. Se falhar, fazer fallback determinístico.

Isso reduz alucinação e mantém previsibilidade operacional.

## 2) Como o agente escolhe qual prompt usar

Essa decisão é feita pelo backend, não pela LLM.

### Diagnóstico (`/api/diagnosis`)

A escolha acontece em duas etapas:
1. No router:
- Se vier `event_id`, chama `diagnose_event_with_engine`.
- Se vier `trip_id`, chama `diagnose_trip_with_engine`.
2. No engine:
- O `system prompt` é sempre `prompts/system_prompt.txt`.
- O `user template` muda pelo modo:
  - modo `event` -> `prompts/diagnosis_event_template.txt`
  - modo `trip` -> `prompts/diagnosis_trip_template.txt`

Resumo: o tipo de entrada (`event_id` vs `trip_id`) define automaticamente qual template de diagnóstico será usado.

### Chat (`/api/chat/ask`)

No chat:
1. O sistema usa sempre `prompts/chat_system_prompt.txt`.
2. O template de resposta é sempre `prompts/chat_response_template.txt`.
3. O que muda é o conteúdo injetado no template:
- intenção detectada (`intent`)
- histórico da sessão
- resultados das tools para aquela intenção

Resumo: no chat, o arquivo de prompt não muda; o contexto dinâmico dentro do template é que muda.

## 3) Como a intenção do chat é detectada (e por que isso importa)

O chat classifica a pergunta antes de executar tools:
- `driver_trip` para frases como "última viagem da ..."
- `dashboard`, `triage`, `vehicle`, `trip`, `risks`, ou `general` por palavras-chave

Essa intenção controla duas coisas:
1. Quais tools serão executadas.
2. Qual contexto vai para o prompt da LLM.

Isso evita mandar contexto irrelevante e melhora qualidade/latência.

## 4) Estrutura dos prompts e por que funciona

## 4.1 System prompts (política)

Os system prompts definem regras estáveis:
- responder só em JSON válido
- não inventar fatos
- tratar texto do usuário como dado (defesa contra prompt injection)
- tom operacional objetivo

Por que funciona:
- separa "política de comportamento" do conteúdo dinâmico.
- reduz deriva de formato.

## 4.2 Templates (tarefa + dados)

Os templates carregam:
- pergunta do usuário
- contexto retornado pelas tools (JSON)
- instruções específicas da tarefa

Por que funciona:
- a LLM recebe dados estruturados, não texto solto.
- as evidências vêm de consultas reais do banco.

## 4.3 Contrato de saída

Diagnóstico exige:
- `severity`, `summary`, `probable_causes`, `recommended_actions`, `evidence`

Chat exige:
- `answer`, `citations`, `follow_up_questions`

Por que funciona:
- facilita validação automática no backend.
- permite fallback seguro quando faltar campo.

## 4.4 Retry de JSON

Se a resposta vier inválida, o backend aplica um hint adicional exigindo JSON estrito e tenta de novo.

Por que funciona:
- corrige casos em que o modelo entendeu a tarefa, mas respondeu em formato livre.

## 5) Tools de diagnóstico: como cada uma funciona

## 5.1 `get_event_context(event_id)`

Entrada:
- `event_id`

Busca:
- join de `Event`, `Vehicle` e `Trip` (quando houver)

Saída principal:
- `event` completo
- dados do `vehicle`
- dados resumidos da `trip` relacionada (opcional)

Uso:
- é a base para diagnóstico por evento.

## 5.2 `get_trip_context(trip_id)`

Entrada:
- `trip_id`

Busca:
- `Trip` + `Vehicle` + todos os `Event` da viagem

Saída principal:
- bloco `trip`
- bloco `vehicle`
- lista `events`

Uso:
- é a base para diagnóstico por viagem.

## 5.3 `get_similar_events(event_type, region, limit)`

Entrada:
- tipo de evento, região e limite

Busca:
- eventos do mesmo tipo/região, ordenados por recência

Saída:
- lista de eventos similares

Uso:
- ajuda a LLM comparar recorrência e padrão.

## 5.4 `get_vehicle_recent_history(vehicle_id, days)`

Entrada:
- `vehicle_id`, janela em dias

Busca:
- eventos recentes do veículo

Saída:
- total de eventos
- contagem por tipo e severidade
- últimos eventos

Uso:
- adiciona contexto temporal e histórico operacional.

## 6) Tools de chat: como cada uma funciona

## 6.1 `get_dashboard_snapshot(start?, end?, region?, status?)`

Retorna KPIs agregados:
- eventos totais/críticos
- veículos ativos
- taxa de pontualidade
- top tipos de evento

Uso típico:
- perguntas de visão geral e indicadores.

## 6.2 `search_events(q?, event_type?, severity?, region?, status?, limit)`

Busca eventos com filtros + texto livre.

Uso típico:
- triagem e investigação operacional.

## 6.3 `get_driver_last_trip(driver_name)`

Fluxo:
1. normaliza acentuação e caixa do nome
2. busca viagens por motorista
3. retorna status:
- `ok`: encontrou 1 candidato canônico
- `not_found`: não encontrou
- `ambiguous`: mais de um candidato

Uso típico:
- pergunta "qual a última viagem da Renata Lima?"

## 6.4 `get_vehicle_overview(vehicle_id)`

Retorna:
- estado atual do veículo
- eventos recentes
- viagens recentes

Uso típico:
- perguntas por ID de veículo.

## 6.5 `get_trip_overview(trip_id)`

Retorna:
- dados da viagem
- dados do veículo
- eventos da viagem

Uso típico:
- perguntas por ID da viagem.

## 6.6 `get_top_risks(window_days)`

Retorna:
- total de eventos na janela
- distribuição por severidade e tipo

Uso típico:
- perguntas sobre risco da semana/período.

## 7) Mapeamento de intenção -> tools (chat)

- `dashboard`: `get_dashboard_snapshot` + `get_top_risks`
- `triage`: `search_events` + `get_top_risks`
- `vehicle`: `get_vehicle_overview`
- `trip`: `get_trip_overview`
- `driver_trip`: `get_driver_last_trip`
- `risks`: `get_dashboard_snapshot` + `get_top_risks`
- `general`: `get_dashboard_snapshot` + `search_events` + `get_top_risks`

Observação:
- esse roteamento é determinístico no backend.
- a LLM não decide quais tools chamar.

## 8) Por que essa estratégia de tools + prompts funciona

1. Dados ancorados:
- toda resposta parte de SQL/transacional, não de memória do modelo.
2. Contexto certo para a pergunta:
- intenção define toolset e reduz ruído.
3. Formato controlado:
- JSON estrito + validação evita saída quebrada.
4. Robustez:
- retries e fallback evitam indisponibilidade funcional.

## 9) Parâmetros e perfis de modelo

Perfil diagnóstico:
- `OLLAMA_DIAG_MODEL_PRIMARY = qwen3:4b`
- `OLLAMA_DIAG_MODEL_FALLBACK = qwen3:4b`
- `LLM_DIAG_TIMEOUT_MS = 60000`
- `LLM_DIAG_MAX_TOKENS = 320`
- `LLM_DIAG_DISABLE_THINKING = true`
- `LLM_DIAG_RETRY_JSON_INVALID = 1`

Perfil chat:
- `OLLAMA_CHAT_MODEL_PRIMARY = qwen3:4b`
- `OLLAMA_CHAT_MODEL_FALLBACK = qwen2.5:7b`
- `LLM_CHAT_TIMEOUT_MS = 120000`
- `LLM_CHAT_MAX_TOKENS = 220`
- `LLM_CHAT_DISABLE_THINKING = true`
- `LLM_CHAT_RETRY_JSON_INVALID = 1`

Racional:
- diagnóstico com timeout dedicado para reduzir fallback no drawer.
- chat com latência baixa e fallback secundário para robustez.

## 10) Como validar em tempo real

1. Checar health:
- `GET /api/llm/health`
- validar blocos `chat` e `diagnosis`
- confirmar `force_deterministic = false`

2. Testar diagnóstico:
- `POST /api/diagnosis` com `event_id` e depois `trip_id`
- verificar `source`, `model`, `validation_warnings`

3. Testar chat com motorista:
- `POST /api/chat/ask` com pergunta de última viagem
- verificar `citations` e `used_tools` contendo `get_driver_last_trip`

## 11) Perguntas prováveis do professor e respostas objetivas

### "Como o agente sabe qual prompt usar?"
No diagnóstico, o router escolhe `event` ou `trip` e isso define o template. No chat, o arquivo de prompt é fixo e o backend muda o contexto (intenção + tools) injetado no template.

### "As tools são chamadas pelo modelo?"
Não. O backend chama tools de forma determinística antes da LLM e entrega os resultados no prompt.

### "Por que separar system prompt e template?"
System prompt define política estável. Template define tarefa e dados da requisição. Isso melhora controle e manutenção.

### "Por que o fallback ainda é necessário?"
Porque modelo local pode falhar por timeout, resposta vazia ou JSON inválido. O fallback garante continuidade operacional.

## 12) Resumo para defesa

"O projeto prioriza confiabilidade operacional: tools determinísticas para buscar dados, prompts estruturados para orientar a LLM e validação/fallback para garantir resposta útil mesmo em falha."

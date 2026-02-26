# Tools disponibilizadas ao LLM

## `get_event_context(event_id)`
- **Objetivo:** montar contexto completo de um evento específico (evento + veículo + viagem associada).
- **Por que existe:** evita alucinação e ancora o modelo em dados reais do banco.

## `get_trip_context(trip_id)`
- **Objetivo:** consolidar contexto de uma viagem com seus eventos.
- **Por que existe:** o diagnóstico de viagem depende de correlação entre eventos.

## `get_similar_events(event_type, region, limit=5)`
- **Objetivo:** trazer amostras recentes de eventos semelhantes por tipo/região.
- **Por que existe:** melhora consistência das causas prováveis e ações recomendadas.

## `get_vehicle_recent_history(vehicle_id, days=30)`
- **Objetivo:** resumir padrões recentes do veículo (volume e severidade de eventos).
- **Por que existe:** permite recomendações menos genéricas e mais direcionadas.

## Estrategia de fallback
- Se qualquer tool falhar, o fluxo ainda pode seguir com o que estiver disponivel.
- Se a resposta final do LLM ficar inválida, o sistema usa fallback determinístico.

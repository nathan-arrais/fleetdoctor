# Tools disponibilizadas ao LLM

## `get_event_context(event_id)`
- **Objetivo:** montar contexto completo de um evento especifico (evento + veiculo + viagem associada).
- **Por que existe:** evita alucinacao e ancora o modelo em dados reais do banco.

## `get_trip_context(trip_id)`
- **Objetivo:** consolidar contexto de uma viagem com seus eventos.
- **Por que existe:** o diagnostico de viagem depende de correlacao entre eventos.

## `get_similar_events(event_type, region, limit=5)`
- **Objetivo:** trazer amostras recentes de eventos semelhantes por tipo/regiao.
- **Por que existe:** melhora consistencia das causas provaveis e acoes recomendadas.

## `get_vehicle_recent_history(vehicle_id, days=30)`
- **Objetivo:** resumir padroes recentes do veiculo (volume e severidade de eventos).
- **Por que existe:** permite recomendacoes menos genericas e mais direcionadas.

## Estrategia de fallback
- Se qualquer tool falhar, o fluxo ainda pode seguir com o que estiver disponivel.
- Se a resposta final do LLM ficar invalida, o sistema usa fallback deterministico.

# Chat Tools (Frota Q&A)

## `get_dashboard_snapshot(start?, end?, region?, status?)`
- Entrega KPIs agregados para responder perguntas de visão geral.

## `search_events(q?, event_type?, severity?, region?, status?, limit)`
- Busca eventos de triagem com filtros e texto livre.

## `get_vehicle_overview(vehicle_id)`
- Retorna estado atual do veículo, últimos eventos e últimas viagens.

## `get_trip_overview(trip_id)`
- Retorna dados da viagem + eventos associados + contexto do veículo.

## `get_top_risks(window_days)`
- Resume concentração de risco por severidade e tipo no período.

## Observações de segurança
- Todas as respostas do chat são ancoradas em dados SQL retornados por tools.
- Se uma tool falhar, o chat sinaliza limitação e usa fallback determinístico.

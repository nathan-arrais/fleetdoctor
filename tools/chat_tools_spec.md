# Chat Tools (Frota Q&A)

## `get_dashboard_snapshot(start?, end?, region?, status?)`
- Entrega KPIs agregados para responder perguntas de visao geral.

## `search_events(q?, event_type?, severity?, region?, status?, limit)`
- Busca eventos de triagem com filtros e texto livre.

## `get_vehicle_overview(vehicle_id)`
- Retorna estado atual do veiculo, ultimos eventos e ultimas viagens.

## `get_trip_overview(trip_id)`
- Retorna dados da viagem + eventos associados + contexto do veiculo.

## `get_top_risks(window_days)`
- Resume concentracao de risco por severidade e tipo no periodo.

## Observacoes de seguranca
- Todas as respostas do chat sao ancoradas em dados SQL retornados por tools.
- Se uma tool falhar, o chat sinaliza limitacao e usa fallback deterministico.

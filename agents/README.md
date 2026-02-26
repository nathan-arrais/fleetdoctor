# Agentes

O grafo de diagnostico foi implementado em:

- `backend/app/agents/langgraph_diagnosis_graph.py`
- `backend/app/agents/langgraph_chat_graph.py`

## Topologia
1. `prepare_context`
2. `execute_tools`
3. `run_llm`
4. `validate_output`
5. `run_fallback` (condicional)

## Topologia do chat
1. `load_memory`
2. `route_intent`
3. `execute_tools`
4. `run_llm`
5. `validate_output`
6. `fallback_response` (condicional)

## Decisao de arquitetura
- Foi escolhido **LangGraph simples** (single graph), sem multiagente, para reduzir risco e complexidade.
- O fallback deterministico garante continuidade operacional quando o modelo local falha.

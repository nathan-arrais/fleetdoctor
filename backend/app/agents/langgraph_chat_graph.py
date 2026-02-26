from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph


class ChatGraphState(TypedDict, total=False):
    session_id: int
    question: str
    history: list[dict[str, Any]]
    intent: str
    extracted_ids: dict[str, int]
    tool_results: dict[str, Any]
    used_tools: list[str]
    system_prompt: str
    user_prompt: str
    llm_text: str
    llm_model: str | None
    llm_latency_ms: int | None
    answer_payload: dict[str, Any] | None
    validation_errors: list[str]
    fallback_reason: str | None


def build_chat_graph(
    load_memory: Callable[[ChatGraphState], ChatGraphState],
    route_intent: Callable[[ChatGraphState], ChatGraphState],
    execute_tools: Callable[[ChatGraphState], ChatGraphState],
    run_llm: Callable[[ChatGraphState], ChatGraphState],
    validate_output: Callable[[ChatGraphState], ChatGraphState],
    fallback_response: Callable[[ChatGraphState], ChatGraphState],
):
    graph = StateGraph(ChatGraphState)
    graph.add_node("load_memory", load_memory)
    graph.add_node("route_intent", route_intent)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("run_llm", run_llm)
    graph.add_node("validate_output", validate_output)
    graph.add_node("fallback_response", fallback_response)

    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "route_intent")
    graph.add_edge("route_intent", "execute_tools")
    graph.add_edge("execute_tools", "run_llm")
    graph.add_edge("run_llm", "validate_output")

    def route_after_validation(state: ChatGraphState):
        if state.get("answer_payload") and not state.get("validation_errors"):
            return END
        return "fallback_response"

    graph.add_conditional_edges("validate_output", route_after_validation, {END: END, "fallback_response": "fallback_response"})
    graph.add_edge("fallback_response", END)
    return graph.compile()

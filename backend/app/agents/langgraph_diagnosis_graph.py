from typing import Any, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class DiagnosisGraphState(TypedDict, total=False):
    mode: Literal["event", "trip"]
    context: dict[str, Any]
    tool_results: dict[str, Any]
    system_prompt: str
    user_prompt: str
    llm_text: str
    llm_model: str | None
    llm_latency_ms: int | None
    llm_attempts_used: int
    llm_attempted_models: list[str]
    diagnosis: dict[str, Any] | None
    validation_errors: list[str]
    used_tools: list[str]
    source: str
    fallback_reason: str | None


def build_diagnosis_graph(
    prepare_context: Callable[[DiagnosisGraphState], DiagnosisGraphState],
    execute_tools: Callable[[DiagnosisGraphState], DiagnosisGraphState],
    run_llm: Callable[[DiagnosisGraphState], DiagnosisGraphState],
    validate_output: Callable[[DiagnosisGraphState], DiagnosisGraphState],
    run_fallback: Callable[[DiagnosisGraphState], DiagnosisGraphState],
):
    graph = StateGraph(DiagnosisGraphState)
    graph.add_node("prepare_context", prepare_context)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("run_llm", run_llm)
    graph.add_node("validate_output", validate_output)
    graph.add_node("run_fallback", run_fallback)

    graph.add_edge(START, "prepare_context")
    graph.add_edge("prepare_context", "execute_tools")
    graph.add_edge("execute_tools", "run_llm")
    graph.add_edge("run_llm", "validate_output")

    def route_after_validation(state: DiagnosisGraphState):
        if state.get("diagnosis") and not state.get("validation_errors"):
            return END
        return "run_fallback"

    graph.add_conditional_edges("validate_output", route_after_validation, {END: END, "run_fallback": "run_fallback"})
    graph.add_edge("run_fallback", END)
    return graph.compile()

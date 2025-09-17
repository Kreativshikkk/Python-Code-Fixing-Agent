from typing import Literal, Any

from langgraph.constants import END
from langgraph.graph import StateGraph

from agent.model import AgentState
from agent.nodes import analyze_code, run_code, analyze_error, fix_code, add_iter, create_tests, postprocess_code


def decide_after_run(state: AgentState) -> Literal["ok", "has_error"]:
    rr = state.get("run_result") or {}
    return "ok" if rr.get("success") and rr.get("return_code") == 0 else "has_error"


def decide_next(state: AgentState) -> Literal["continue", "stop"]:
    if state["iter"] >= state["max_iter"]:
        return "stop"
    return "continue"


def tests_edge(state: AgentState) -> Literal["yes", "no"]:
    return "no" if state["tests"] else "yes"


def after_tests(state: AgentState) -> Literal["yes", "no"]:
    if state["tests"]:
        return "yes"
    return "no"


def build_graph(generic_type: Any) -> StateGraph:
    workflow = StateGraph(generic_type)

    workflow.set_entry_point("analyze_code")

    workflow.add_node("analyze_code", analyze_code)
    workflow.add_node("create_tests", create_tests)
    workflow.add_node("run_code", run_code)
    workflow.add_node("analyze_error", analyze_error)
    workflow.add_node("fix_code", fix_code)
    workflow.add_node("add_iter", add_iter)
    workflow.add_node("postprocess_code", postprocess_code)

    workflow.add_edge("analyze_error", "fix_code")
    workflow.add_edge("fix_code", "postprocess_code")
    workflow.add_edge("postprocess_code", "add_iter")

    workflow.add_conditional_edges(
        "add_iter",
        decide_next,
        {
            "continue": "run_code",
            "stop": END,
        }
    )

    workflow.add_conditional_edges(
        "run_code",
        decide_after_run,
        {
            "ok": END,
            "has_error": "analyze_error",
        }
    )

    workflow.add_conditional_edges(
        "analyze_code",
        tests_edge,
        {
            "yes": "create_tests",
            "no": "run_code",
        }
    )

    workflow.add_conditional_edges(
        "create_tests",
        after_tests,
        {
            "yes": "run_code",
            "no": "create_tests",
        }
    )

    return workflow

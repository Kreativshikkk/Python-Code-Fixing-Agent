import argparse
import logging
import sys

from langchain_core.messages import SystemMessage

from utils.utils import parse_config
from agent.graph import build_graph
from agent.model import AgentState


def run_agent(buggy_code: str, docstring: str, max_iter: int, recursion_limit: int, run_inspections: bool = False) -> AgentState:
    app = build_graph(AgentState).compile()
    _state: AgentState = {
        "messages": [SystemMessage(content="Be extremely laconic in your responses.")],
        "code": buggy_code,
        "docstring": docstring,
        "tests": None,
        "run_result": None,
        "error_summary": None,
        "phase": "analyze_code",
        "iter": 0,
        "max_iter": max_iter,
        "run_inspections": run_inspections,
    }
    final = app.invoke(_state, {"recursion_limit": recursion_limit})
    return final.get("code")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run agent on docstring and buggy code specified in config."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Путь к конфигу агента (default: config.yaml)",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # we do not parse dir python3 -m eval.main
    args = parser.parse_args(sys.argv[4:])
    args_from_config = parse_config(args.config)

    print(
        run_agent(args_from_config["buggy_code"], args_from_config["docstring"], int(args_from_config["max_iter"]), int(
            args_from_config["recursion_limit"]), bool(args_from_config["run_inspections"])))

from typing import TypedDict, Annotated, Optional, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class RunResult(TypedDict):
    success: bool
    stdout: str
    stderr: str
    return_code: int
    tests_passed: bool


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    code: str
    docstring: Optional[str]
    tests: Optional[str]
    run_result: Optional[RunResult]
    error_summary: Optional[str]
    phase: Literal["analyze_code", "run_code", "analyze_error", "fix_error"]
    iter: int
    max_iter: int
    run_inspections: bool


class FileFragment(TypedDict):
    line_number: int
    code_fragment: str


class StackTrace(TypedDict):
    exact_error: str
    file_fragments: list[FileFragment]

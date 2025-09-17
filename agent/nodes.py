import json
from json import JSONDecodeError

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, ToolMessage, BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from utils.utils import parse_config, parse_json_content
from agent.model import AgentState
from agent.prompts import ANALYZE_CODE_SYSTEM_PROMPT, ANALYZE_ERROR_SYSTEM_PROMPT, FIX_ERROR_SYSTEM_PROMPT, \
    CREATE_TESTS_SYSTEM_PROMPT, UPDATE_TESTS_CODE_PROMPT, \
    POSTPROCESS_CODE_SYSTEM_PROMPT
from agent.tools import run_code_in_sandbox, parse_stack_trace, create_python_file_and_lookup_inspections

load_dotenv()

model = ChatOpenAI(
    model=parse_config("config.yaml")["model_name"],
    temperature=0,
    max_retries=2,
    max_tokens=None,
)


def call_llm(messages: list[BaseMessage]):
    return model.invoke(messages)


def call_llm_with_tools(messages: list[BaseMessage], _tools):
    _model = model.bind_tools(_tools)
    return _model.invoke(messages)


def analyze_code(state: AgentState) -> dict:
    human_message_content = f"Initial buggy code: {state['code']}"
    if state["docstring"] is not None:
        human_message_content += f"\nDocstring for the function: {state['docstring']}"
    if state["tests"] is not None:
        human_message_content += f"\nTests for the function: {state['tests']}"

    messages = [ANALYZE_CODE_SYSTEM_PROMPT] + state["messages"] + [HumanMessage(content=human_message_content)]

    out = call_llm(messages)
    messages.append(out)
    messages.pop(0)
    return {"messages": messages, "phase": "analyze_code"}


def run_code(state: AgentState) -> dict:
    run_result = run_code_in_sandbox.invoke({"code": state["code"], "tests": state["tests"]})
    human_msg = HumanMessage(
        content=f"[run_code_in_sandbox] result:\n{json.dumps(run_result, ensure_ascii=False, indent=2)}",
        name="run_code_in_sandbox",
    )
    return {"messages": state["messages"] + [human_msg], "phase": "run_code", "run_result": run_result}


def create_tests(state: AgentState) -> dict:
    messages = [CREATE_TESTS_SYSTEM_PROMPT] + [HumanMessage(content=f"code: {state['code']}"
                                                                    f"docstring: {state['docstring']}")]
    out = call_llm(messages)
    messages = state["messages"] + [out]
    try:
        return {"messages": messages, "tests": parse_json_content(out.content)}
    except (JSONDecodeError, KeyError, AttributeError, TypeError, ValueError):
        return {"messages": messages}


def analyze_error(state: AgentState) -> dict:
    stdout = state["run_result"]["stdout"]
    stderr = state["run_result"]["stderr"]

    human_message = HumanMessage(content=
                                 f"Here are stdout and stderr to fix: {stdout} and {stderr}")
    messages = [ANALYZE_ERROR_SYSTEM_PROMPT] + state["messages"] + [human_message]

    _tools = [
        parse_stack_trace]

    if state["run_inspections"]:
        _tools.append(create_python_file_and_lookup_inspections)

    _tool_map = {t.name: t for t in _tools}
    out = call_llm_with_tools(messages, _tools)

    messages.append(out)
    messages.pop(0)

    _error_summary = None

    if hasattr(out, "tool_calls"):
        for tool_call in out.tool_calls:
            name = tool_call["name"]
            args = tool_call.get("args", {}) or {}
            try:
                res = _tool_map[name].invoke(args)
            except ValidationError:
                res = {}
            if tool_call["name"] == "parse_stack_trace":
                _error_summary = res["exact_error"]
            messages.append(
                ToolMessage(
                    content=json.dumps(res, ensure_ascii=False),
                    name=name,
                    tool_call_id=tool_call["id"],
                )
            )

    return {"messages": messages, "phase": "analyze_error", "error_summary": _error_summary}


def fix_code(state: AgentState) -> dict:
    # update tests code if there was a logical error in them...
    tests_messages = [UPDATE_TESTS_CODE_PROMPT] + state["messages"] + [
        HumanMessage(content=f"Tests code: {state['tests']}")]
    tests_message = call_llm(tests_messages)

    # update current code
    code_messages = [FIX_ERROR_SYSTEM_PROMPT] + state["messages"] + [tests_message]
    code_message = call_llm(code_messages)

    try:
        new_tests = parse_json_content(tests_message.content)
    except (JSONDecodeError, KeyError, AttributeError, TypeError, ValueError):
        new_tests = state["tests"]

    try:
        new_code = parse_json_content(code_message.content)
    except (JSONDecodeError, KeyError, AttributeError, TypeError, ValueError):
        new_code = state["code"]

    return {"messages": state["messages"] + [tests_message, code_message], "phase": "fix_error", "tests": new_tests,
            "code": new_code}


def postprocess_code(state: AgentState) -> dict:
    messages = [POSTPROCESS_CODE_SYSTEM_PROMPT] + state["messages"]
    out = call_llm(messages)
    try:
        new_code = parse_json_content(out.content)
    except (JSONDecodeError, KeyError, AttributeError, TypeError, ValueError):
        new_code = state["code"]
    return {"code": new_code}


def add_iter(state: AgentState):
    return {"iter": state["iter"] + 1}

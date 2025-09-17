import json
import os
import re
import subprocess
import tempfile
from json import JSONDecodeError
from pathlib import Path

from langchain_core.tools import tool

from agent.model import RunResult, StackTrace

FILENAME = "buggy_code.py"
TESTSNAME = "tests.py"
ROOT = Path.cwd()
AGENT_DIR = Path(".agent")
RESOURCES_DIR = Path("resources")
PATH_TO_INSPECTIONS_SCRIPT = Path("scripts", "inspect.sh")
DESCRIPTIONS_FILENAME = ".descriptions.json"


@tool
def run_code_in_sandbox(code: str, tests: str = None, timeout_time: int = 60) -> RunResult:
    """
    A tool to run code in an isolated sandbox. For now, it is a simple temporary directory.
    Further, can potentially be changed to a docker container
    :param tests: Python tests for the code
    :param code: Python code to run
    :param timeout_time: Timeout for running attempt in seconds. Set to 60 by default.
    :return: A dictionary with success or not (boolean), stdout (str), stderr (str).
    """

    # TODO(add docker support)
    with tempfile.TemporaryDirectory() as tempdir:
        code_path = os.path.join(tempdir, FILENAME)

        if not tests:
            with open(code_path, "w") as code_file:
                code_file.write(code)
        else:
            with open(code_path, "w") as tests_file:
                tests_file.write(code + "\n\n" + tests)

        commands = ["python", code_path]

        try:
            process = subprocess.run(
                commands, cwd=tempdir, capture_output=True, text=True, timeout=timeout_time
            )
            stdout = process.stdout
            if tests:
                tests_passed = (process.returncode == 0)
                success = tests_passed
                stdout = _simplify_stdout(process.stdout)
            else:
                tests_passed = (process.returncode == 0)
                success = (process.returncode == 0)
            return RunResult(
                success=success,
                stdout=stdout,
                stderr=process.stderr,
                return_code=process.returncode,
                tests_passed=tests_passed,
            )

        except subprocess.TimeoutExpired as e:
            return RunResult(
                success=False,
                stdout="" or str(e.stdout),
                stderr=str(subprocess.TimeoutExpired),
                return_code=-1,
                tests_passed=False,
            )


@tool
def parse_stack_trace(trace: str) -> StackTrace:
    """
    A tool that parses a stack trace statically. Please call this tool only you have stderr after running.
    :param trace: stack trace to parse
    :return: StackTrace object. Contains the exact error inside and all appearances of the buggy file in stacktrace
    """
    frame_pattern = re.compile(
        r'^\s*File\s+"(?P<file>.+?)",\s+line\s+(?P<line>\d+)'
        r'(?:,\s+in\s+(?P<func>[^\n]+))?'
        r'(?:\n(?!\s*File\s+")(?![ \t]*\^)[ \t]+(?P<code>[^\n]*))?',
        re.MULTILINE
    )
    files = list(frame_pattern.finditer(trace))

    if not files:
        return {"exact_error": trace.strip(), "file_fragments": []}

    _file_fragments = []

    for file in files:
        frame_dict = file.groupdict()
        if FILENAME in frame_dict["file"]:
            if frame_dict["line"] and frame_dict["code"]:
                _file_fragments.append({"line_number": int(frame_dict["line"]), "code_fragment": frame_dict["code"]})

    last_end = files[-1].end()
    exact_error = trace[last_end:].strip()
    return {"exact_error": exact_error, "file_fragments": _file_fragments}


@tool
def create_python_file_and_lookup_inspections(code: str) -> dict:
    """
    This tool statically checks a lot of inspections on the given code.
    For example: unused references, unresolved references, incorrect type, etc.
    :param code: code to be analyzed
    :return: a dict with all inspections.
    """
    AGENT_DIR.mkdir(parents=True, exist_ok=True)

    with open(AGENT_DIR / FILENAME, "w") as file_path:
        file_path.write(code)

    inspections_xml_path = str(ROOT / RESOURCES_DIR / "profiles_settings.xml")
    result_path = str(ROOT / AGENT_DIR / "inspections")
    search_directory = str(ROOT / AGENT_DIR)

    for file in Path(result_path).iterdir():
        if file.is_file() or file.is_symlink():
            file.unlink()

    commands = [str(PATH_TO_INSPECTIONS_SCRIPT), str(ROOT), inspections_xml_path, result_path, "-v2",
                "-d", search_directory,
                "-format", "json"]
    proc = subprocess.run(commands, cwd=str(ROOT))

    if proc.returncode != 0:
        return {}

    output = {}

    for file in Path(result_path).iterdir():
        if file.name != DESCRIPTIONS_FILENAME:
            try:
                with open(file, "r", encoding="utf-8") as json_file:
                    output[file.name] = json.load(json_file)
            except (JSONDecodeError, KeyError, AttributeError, TypeError, ValueError):
                continue
    return output


def _simplify_stdout(stdout: str) -> list[str]:
    # dummy implementation
    failures = []
    lines_list = stdout.splitlines()
    for index, line in enumerate(lines_list):
        if index == len(lines_list) - 1 or line.strip() == "":
            continue
        if line[0] == ">" or line[0] == "E" or "assert" in line:
            failures.append(line)
            failures.append(lines_list[index + 1])
    return failures

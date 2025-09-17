import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from datasets import load_dataset
from tqdm import tqdm

from agent.main import run_agent
from agent.tools import run_code_in_sandbox
from utils.utils import parse_config


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def get_example_id(example: Dict[str, Any], idx: int) -> str:
    if "task_id" in example and isinstance(example["task_id"], str):
        return example["task_id"]
    return f"item_{idx:04d}"


def normalize_code(s: Optional[str]) -> str:
    return (s or "").strip()


def run_single_example(
    example: Dict[str, Any],
    idx: int,
    agent_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    example_id = get_example_id(example, idx)

    declaration = example.get("declaration", "")
    buggy_solution = example.get("buggy_solution", "")
    code_input = f"{declaration}\n{buggy_solution}"
    docstring = example.get("docstring", "")
    tests = example.get("test", "")
    canonical = example.get("canonical_solution", "")

    t0 = time.perf_counter()
    agent_error = None

    try:
        output_code = run_agent(
            buggy_code=code_input,
            docstring=docstring,
            max_iter=int(agent_cfg.get("max_iter", 5)),
            recursion_limit=int(agent_cfg.get("recursion_limit", 1000)),
        )
        output_code = str(output_code)
    except Exception as e:
        agent_error = f"{type(e).__name__}: {e}"
        output_code = ""

    t1 = time.perf_counter()
    gen_seconds = round(t1 - t0, 4)

    sandbox_error = None
    t2 = time.perf_counter()
    try:
        test_result = run_code_in_sandbox.invoke(
            {"code": output_code, "tests": tests}
        )
    except Exception as e:
        sandbox_error = f"{type(e).__name__}: {e}"
        test_result = {"success": False, "error": sandbox_error}
    t3 = time.perf_counter()
    exec_seconds = round(t3 - t2, 4)

    passed_tests = bool(test_result.get("success", False))
    same_as_canonical = normalize_code(output_code) == normalize_code(canonical)

    status = "PASS" if (passed_tests or same_as_canonical) else "FAIL"
    if agent_error or sandbox_error:
        if status != "PASS":
            status = "ERROR"

    record: Dict[str, Any] = {
        "idx": idx,
        "example_id": example_id,
        "status": status,
        "passed_tests": passed_tests,
        "same_as_canonical": same_as_canonical,
        "gen_seconds": gen_seconds,
        "exec_seconds": exec_seconds,
        "agent_error": agent_error,
        "sandbox_error": sandbox_error,
        "test_result": {
            "success": test_result.get("success", False),
            "stdout": test_result.get("stdout"),
            "stderr": test_result.get("stderr"),
            "traceback": test_result.get("traceback"),
            "error": test_result.get("error"),
        },
        "output_code": output_code,
    }
    return record


def summarize(records: list) -> Dict[str, Any]:
    total = len(records)
    passed = sum(1 for record in records if record["status"] == "PASS")
    errored = sum(1 for record in records if record["status"] == "ERROR")
    failed = total - passed - errored
    pass_rate = round(passed / total, 4) if total > 0 else 0.0
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errored": errored,
        "pass_rate": pass_rate,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent evaluation on bigcode/humanevalpack (python subset)."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to config (default: config.yaml)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="bigcode/humanevalpack",
        help="HF-dataset (default: bigcode/humanevalpack)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="python",
        help='Argument "name" in dataset (default: python)',
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        help='Dataset split (default: "test")',
    )
    parser.add_argument(
        "--results_dir",
        type=str,
        default="results",
        help='Results directory (default: "results")',
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=164,
        help='Limit number of examples (default: 164)',
    )
    # we do not parse dir python3 -m eval.main
    args = parser.parse_args(sys.argv[4:])

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    results_dir = Path(args.results_dir)
    ensure_dir(results_dir)
    stamp = now_stamp()
    jsonl_path = results_dir / f"eval_{stamp}.jsonl"
    summary_path = results_dir / f"summary_{stamp}.json"

    logging.info("Load config: %s", args.config)
    cfg = parse_config(args.config)
    if not isinstance(cfg, dict):
        logging.warning("Config was parsed incorrectly. It was set as an empty dict.")
        cfg = {}

    logging.info("Loading dataset: %s (name=%s, split=%s)", args.dataset, args.name, args.split)
    dataset = load_dataset(args.dataset, name=args.name, split=args.split)

    indices = list(range(len(dataset)))

    total_items = len(indices)
    records = []
    passed_count = 0

    progress_iter = tqdm(indices, desc="Evaluating", ncols=100)

    with open(jsonl_path, "w", encoding="utf-8") as eval_file:
        for i in progress_iter:
            if i >= args.limit:
                break
            example = dataset[i]
            rec = run_single_example(
                example=example,
                idx=i,
                agent_cfg=cfg,
            )
            records.append(rec)

            eval_file.write(json.dumps(rec, ensure_ascii=False) + "\n")
            eval_file.flush()

            if rec["status"] == "PASS":
                passed_count += 1
                msg = f"PASS {passed_count}/{len(records)} | idx={rec['idx']} id={rec['example_id']}"
                logging.info(msg)
            elif rec["status"] == "ERROR":
                msg = f"ERROR {passed_count}/{len(records)} | idx={rec['idx']} id={rec['example_id']}"
                logging.warning(msg)
            else:
                msg = f"FAIL {passed_count}/{len(records)} | idx={rec['idx']} id={rec['example_id']}"
                logging.info(msg)

    summary = summarize(records)
    with open(summary_path, "w", encoding="utf-8") as fsum:
        json.dump(summary, fsum, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False))

    denom = total_items if total_items > 0 else 1
    pass_rate = summary["passed"] / denom
    print(f"{pass_rate:.6f}")

    logging.info("Evaluation finished. JSONL: %s | SUMMARY: %s", jsonl_path, summary_path)


if __name__ == "__main__":
    main()

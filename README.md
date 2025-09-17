# Python Code Fixing Agent

Implementation of a LangGraph-based agent that automatically fixes buggy Python code.

---

## Description

The agent takes buggy code and its docstring, iteratively attempts to repair it, and validates the fix in a sandboxed
environment.

Key points:
- The agent is designed to fix buggy code with an accompanying docstring.
- It generates and runs tests, then modifies the code (and tests sometimes, as they might be incorrect) until it passes.
- Developed and tested on **Python 3.11** — please use this version.

---

## Installation & Run

Clone the repository:

```bash
git clone https://github.com/Kreativshikkk/Python-Code-Fixing-Agent.git PythonCodeFixingAgent
cd PythonCodeFixingAgent
pip install -r requirements.txt
```

Create a `.env` file in the project root and set your OpenAI key:

```
OPENAI_API_KEY=
```

## Run the agent

This script runs agent in the cloned repository:

```python
python -m agent.main
```

### CLI arguments for running the agent:

| Argument   | Type | Default       | Description         |
|------------|------|---------------|---------------------|
| `--config` | str  | `config.yaml` | Path to config file |

### You can set these arguments in config.yaml

| Argument                | Type | Default                                  | Description                                                                                                                |
|-------------------------|------|------------------------------------------|----------------------------------------------------------------------------------------------------------------------------|
| `run_in_docker`         | bool | `False`                                  | Run LLM generated code in Docker container                                                                                 |
| `pycharm_bin_directory` | str  | `/Applications/PyCharm.app/Contents/bin` | Needed for inspections tool. This value it default for Mac                                                                 |
| `model_name`            | str  | `gpt-4o`                                 | Model used in the agent. Currently only OpenAI models are supported                                                        |
| `max_iter`              | int  | 3                                        | Specifies the number of agent fixing code-running tests cycles                                                             |
| `recursion_limit`       | int  | 18                                       | Recursion limit during agent execution. It is recommended to keep it more than max_iter * 6                                |
| `buggy_code`            | str  | ""                                       | Code to be fixed                                                                                                           |
| `docstring`             | str  | ""                                       | Docstring for the code                                                                                                     |
| `run_inspections`       | bool | False                                    | To run inspections tool or no. Note: it is available only if you have PyCharm installed and is running code outside of it! |

## Agent evaluation

By default, agent is evaluated on [humanevalpack](https://huggingface.co/datasets/bigcode/humanevalpack/viewer/python/test?row=0) dataset on it Python subset. 

Input = `declaration` + `buggy_code` 

The task is considered solved if:
1. The fixed code equals the `canonical_solution` OR
2. The solution passes all tests from the `test` field.

You can find detailed evaluation logs in `results/eval_TIMESTAMP.jsonl` and summary here `results/summary_TIMESTAMP.json`.

This script evaluates the agent in cloned repository:

```python
python -m eval.main
```

### CLI arguments for evaluation:

| Argument        | Type | Default                 | Description                    |
|-----------------|------|-------------------------|--------------------------------|
| `--config`      | str  | `config.yaml`           | Path to config file            |
| `--dataset`     | str  | `bigcode/humanevalpack` | HuggingFace dataset to use     |
| `--name`        | str  | `python`                | Subset name in dataset         |
| `--split`       | str  | `test`                  | Dataset split                  |
| `--results_dir` | str  | `results`               | Directory to save results      |
| `--limit`       | int  | `164`                   | Limit number of examples       |
| `--inspections` | bool | `False`                 | Run PyCharm inspections or not |

# Current evaluation scores (pass@1 metric)
| Model        | Mode (Agent-current implementation, LLM-single LLM call) | Passed | Total | Accuracy |
|--------------|----------------------------------------------------------|--------|-------|----------|
| gpt-4o       | LLM                                                      | 148    | 164   | 0.902    |
| gpt-4o       | Agent                                                    | 150    | 164   | 0.915    |
| gpt-4.1      | LLM                                                      | 149    | 164   | 0.909    |
| gpt-4.1      | Agent                                                    | 152    | 164   | 0.927    |
| gpt-4.1-mini | LLM                                                      | 147    | 164   | 0.896    |
| gpt-4.1-mini | Agent                                                    | 112    | 164   | 0.683    |

Note: a mini model's low score is likely because of context issues (messages history definitely has to be adjusted for them).

For other models there is a slight improvement in the performance.

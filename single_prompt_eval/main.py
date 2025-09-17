from datasets import load_dataset
from dotenv import load_dotenv

from agent.tools import run_code_in_sandbox
from openai import OpenAI

load_dotenv()
client = OpenAI()


def quick_eval_one():
    passed = 0
    dataset = load_dataset("bigcode/humanevalpack", name="python", split="test")
    for example in dataset:

        buggy_code = example["declaration"] + "\n" + example["buggy_solution"]
        docstring = example["docstring"]
        tests = example["test"]

        # 1. Генерация кода через GPT
        fixed_code = run_with_gpt(buggy_code, docstring)
        print(buggy_code, "\n", docstring, "\n", tests, "\n", fixed_code)

        # 2. Прогон в песочнице
        result = run_code_in_sandbox.invoke({"code": fixed_code, "tests": tests})
        print(result)
        if result["success"]:
            passed += 1
        print(passed)


def run_with_gpt(buggy_code: str, docstring: str) -> str:
    """
    Отправляет один промпт в gpt-4.1-mini и возвращает сгенерированный код.
    """
    prompt = f"""
    Ты — опытный Python разработчик.
    Тебе дана функция с багами. Вот её описание:
    
    \"\"\"{docstring}\"\"\"
    
    Вот исходный код с ошибками:
    
    ```python
    {buggy_code}
    ```
    Исправь код так, чтобы он полностью соответствовал описанию.
    Верни ТОЛЬКО готовый Python-код функции, без пояснений и текста. Возвращай всё и без обёртки ```python ```
    """
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "Ты — опытный Python разработчик. Исправляй баги в коде."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=16000,
        temperature=0,
    )

    code = response.choices[0].message.content.strip()
    return code


quick_eval_one()

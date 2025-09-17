import json
import re
import yaml


def parse_config(config_path: str) -> object | dict[str, str]:
    with open(config_path) as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)


def parse_json_content(raw_string: str) -> str:
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, raw_string, re.DOTALL)

    json_content = match.group(1)
    json_output = json.loads(json_content)
    return json_output["content"]

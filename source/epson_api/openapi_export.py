import json
from pathlib import Path

from epson_api.config import Settings
from epson_api.main import create_app

SPEC_PATH = Path(__file__).parents[2] / "openapi.json"


def render() -> str:
    return json.dumps(create_app(Settings(api_key="unused")).openapi(), indent=2) + "\n"


if __name__ == "__main__":
    SPEC_PATH.write_text(render(), encoding="utf-8", newline="\n")

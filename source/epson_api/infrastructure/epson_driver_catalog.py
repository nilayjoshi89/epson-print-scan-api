import gzip
import re
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

from epson_api.domain.errors import UnavailableOptionError, UnknownModelError

DRIVER_ROOT = Path("/opt")
OPTION_LINE = re.compile(r"\*(Ink|MediaType|PageSize|Brightness|Contrast|Saturation) ([^/:\s]+)")


class EpsonDriverCatalog:
    def __init__(self, root: Path = DRIVER_ROOT) -> None:
        self._root = root
        self._choices: dict[str, dict[str, set[str]]] = {}

    def driver_path(self, model: str) -> Path:
        matches = sorted(self._root.glob(f"*/ppds/**/Epson-{model}-*.ppd.gz"))
        if not matches:
            raise UnknownModelError(f"No driver for model {model}")
        return matches[0]

    def validated_options(self, model: str, requested: Mapping[str, str]) -> dict[str, str]:
        choices = self._choices_for(model)
        options = {name: value for name, value in requested.items() if name in choices}
        for name, value in options.items():
            if value not in choices[name]:
                raise UnavailableOptionError(f"{name} {value} is not available for model {model}")
        return options

    def _choices_for(self, model: str) -> dict[str, set[str]]:
        if model not in self._choices:
            self._choices[model] = self._read_choices(self.driver_path(model))
        return self._choices[model]

    @staticmethod
    def _read_choices(path: Path) -> dict[str, set[str]]:
        choices: dict[str, set[str]] = defaultdict(set)
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as driver:
            for line in driver:
                if match := OPTION_LINE.match(line):
                    choices[match.group(1)].add(match.group(2))
        return choices

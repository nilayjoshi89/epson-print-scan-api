import asyncio
import re
import shutil
import tempfile
from collections.abc import Mapping
from ipaddress import IPv4Address

from epson_api.domain.errors import PrintFailedError, QueueSetupError
from epson_api.domain.printing import Document, PrintSettings, queue_name
from epson_api.infrastructure.command_runner import CommandRunner
from epson_api.infrastructure.epson_driver_catalog import EpsonDriverCatalog

ORIENTATION_CODES = {"portrait": 3, "landscape": 4, "reverse_landscape": 5, "reverse_portrait": 6}


class CupsPrintQueue:
    def __init__(self, runner: CommandRunner, catalog: EpsonDriverCatalog) -> None:
        self._runner = runner
        self._catalog = catalog
        self._lock = asyncio.Lock()
        self._configured_models: dict[str, str] = {}

    async def submit(
        self,
        printer_ip: IPv4Address,
        document: Document,
        settings: PrintSettings,
        driver_options: Mapping[str, str],
    ) -> str:
        queue = await self._ensure_queue(printer_ip, settings.model)
        with tempfile.NamedTemporaryFile(prefix="print-") as spool:
            shutil.copyfileobj(document.content, spool)
            spool.flush()
            result = await self._runner.run(
                "lp",
                "-d",
                queue,
                "-n",
                str(settings.copies),
                "-t",
                document.title,
                *self._options(settings, driver_options),
                spool.name,
            )
        if result.exit_code:
            raise PrintFailedError(f"Print failed: {result.stderr.strip()}")
        match = re.search(r"request id is (\S+)", result.stdout)
        return match.group(1) if match else result.stdout.strip()

    async def _ensure_queue(self, printer_ip: IPv4Address, model: str) -> str:
        name = queue_name(printer_ip)
        driver = self._catalog.driver_path(model)
        async with self._lock:
            if self._configured_models.get(name) != model:
                result = await self._runner.run(
                    "lpadmin", "-p", name, "-v", f"socket://{printer_ip}:9100", "-P", str(driver), "-E"
                )
                if result.exit_code:
                    raise QueueSetupError(f"Queue setup failed: {result.stderr.strip()}")
                self._configured_models[name] = model
        return name

    @staticmethod
    def _options(settings: PrintSettings, driver_options: Mapping[str, str]) -> list[str]:
        options = [f"{name}={value}" for name, value in driver_options.items()]
        options.append(f"number-up={settings.number_up}")
        if settings.page_ranges != "all":
            options.append(f"page-ranges={settings.page_ranges}")
        if settings.orientation != "auto":
            options.append(f"orientation-requested={ORIENTATION_CODES[settings.orientation]}")
        if settings.fit_to_page:
            options.append("fit-to-page")
        return [argument for option in options for argument in ("-o", option)]

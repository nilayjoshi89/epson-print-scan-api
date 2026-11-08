import asyncio
import os
import tempfile
from ipaddress import IPv4Address
from pathlib import Path

from epson_api.domain.errors import ScanFailedError
from epson_api.domain.scanning import ScanSettings
from epson_api.infrastructure.command_runner import CommandRunner

SCANNER_PORT = 1865
PROBE_TIMEOUT_SECONDS = 3


class SaneScanner:
    def __init__(self, runner: CommandRunner, timeout_seconds: int) -> None:
        self._runner = runner
        self._timeout_seconds = timeout_seconds

    def device_name(self, printer_ip: IPv4Address) -> str:
        return f"epsonds:net:{printer_ip}"

    async def is_reachable(self, printer_ip: IPv4Address) -> bool:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(str(printer_ip), SCANNER_PORT), PROBE_TIMEOUT_SECONDS
            )
        except OSError:
            return False
        writer.close()
        return True

    async def scan(self, printer_ip: IPv4Address, settings: ScanSettings) -> Path:
        handle, name = tempfile.mkstemp(prefix="scan-", suffix=f".{settings.format}")
        os.close(handle)
        output = Path(name)
        try:
            result = await self._runner.run(*self._command(printer_ip, settings, output), timeout=self._timeout_seconds)
            if result.exit_code:
                raise ScanFailedError(f"Scan failed: {result.stderr.strip()}")
        except BaseException:
            output.unlink(missing_ok=True)
            raise
        return output

    def _command(self, printer_ip: IPv4Address, settings: ScanSettings, output: Path) -> list[str]:
        area = []
        if settings.area:
            area = ["-x", str(settings.area.width_mm), "-y", str(settings.area.height_mm)]
        return [
            "scanimage",
            "-d",
            self.device_name(printer_ip),
            "--format",
            settings.format,
            f"--mode={settings.mode}",
            f"--resolution={settings.resolution}",
            *area,
            "-o",
            str(output),
        ]

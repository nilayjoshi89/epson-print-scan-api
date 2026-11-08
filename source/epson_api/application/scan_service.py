import asyncio
from collections import defaultdict
from ipaddress import IPv4Address
from pathlib import Path

from epson_api.application.ports import Scanner
from epson_api.domain.errors import ScannerBusyError
from epson_api.domain.scanning import ScanSettings


class ScanService:
    def __init__(self, scanner: Scanner) -> None:
        self._scanner = scanner
        self._locks: defaultdict[IPv4Address, asyncio.Lock] = defaultdict(asyncio.Lock)

    def is_busy(self, printer_ip: IPv4Address) -> bool:
        return self._locks[printer_ip].locked()

    async def scan(self, printer_ip: IPv4Address, settings: ScanSettings) -> Path:
        if self.is_busy(printer_ip):
            raise ScannerBusyError("A scan is already in progress")
        async with self._locks[printer_ip]:
            return await self._scanner.scan(printer_ip, settings)

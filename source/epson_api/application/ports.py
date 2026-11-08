from collections.abc import Mapping
from ipaddress import IPv4Address
from pathlib import Path
from typing import BinaryIO, Protocol

from epson_api.domain.printing import Document, PrintSettings
from epson_api.domain.scanning import ScanSettings
from epson_api.domain.status import PrinterStatus, QueueStatus


class Scanner(Protocol):
    def device_name(self, printer_ip: IPv4Address) -> str: ...

    async def is_reachable(self, printer_ip: IPv4Address) -> bool: ...

    async def scan(self, printer_ip: IPv4Address, settings: ScanSettings) -> Path: ...


class DriverCatalog(Protocol):
    def validated_options(self, model: str, requested: Mapping[str, str]) -> dict[str, str]: ...


class DocumentInspector(Protocol):
    def is_supported(self, content: BinaryIO) -> bool: ...


class PrintQueue(Protocol):
    async def submit(
        self,
        printer_ip: IPv4Address,
        document: Document,
        settings: PrintSettings,
        driver_options: Mapping[str, str],
    ) -> str: ...


class PrinterStatusReader(Protocol):
    async def read(self, printer_ip: IPv4Address) -> PrinterStatus: ...


class QueueStatusReader(Protocol):
    async def read(self, name: str) -> QueueStatus: ...

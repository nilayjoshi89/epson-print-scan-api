import asyncio
from ipaddress import IPv4Address

import pytest
from fastapi.testclient import TestClient

from epson_api.api.dependencies import Services
from epson_api.application.print_service import PrintService
from epson_api.application.scan_service import ScanService
from epson_api.application.status_service import StatusService
from epson_api.config import Settings
from epson_api.domain.errors import UnavailableOptionError
from epson_api.domain.status import DeviceState, PrinterStatus, QueueStatus
from epson_api.infrastructure.content_document_inspector import ContentDocumentInspector
from epson_api.main import create_app

API_KEY = "test-key"
PRINTER_IP = IPv4Address("192.168.0.64")
MAX_UPLOAD_BYTES = 1024


class FakeScanner:
    def __init__(self, tmp_path) -> None:
        self.tmp_path = tmp_path
        self.requests = []
        self.reachable = True
        self.error = None
        self.gate = None

    def device_name(self, printer_ip) -> str:
        return f"epsonds:net:{printer_ip}"

    async def is_reachable(self, printer_ip) -> bool:
        return self.reachable

    async def scan(self, printer_ip, settings):
        self.requests.append((printer_ip, settings))
        if self.gate:
            await self.gate.wait()
        if self.error:
            raise self.error
        path = self.tmp_path / f"scan.{settings.format}"
        path.write_bytes(b"scanned")
        return path


class FakeCatalog:
    def validated_options(self, model, requested) -> dict:
        if requested["PageSize"] == "Nope":
            raise UnavailableOptionError(f"PageSize Nope is not available for model {model}")
        return dict(requested)


class FakeQueue:
    def __init__(self) -> None:
        self.submitted = []

    async def submit(self, printer_ip, document, settings, driver_options) -> str:
        self.submitted.append((printer_ip, document.title, settings, driver_options))
        return "epson-192-168-0-64-1"


class FakePrinterReader:
    def __init__(self) -> None:
        self.status = PrinterStatus(True, DeviceState("idle", ["none"], True), {"printer-make-and-model": "L3250"})
        self.reads = 0

    async def read(self, printer_ip) -> PrinterStatus:
        self.reads += 1
        return self.status


class FakeQueueReader:
    async def read(self, name) -> QueueStatus:
        return QueueStatus(name=None)


@pytest.fixture
def scanner(tmp_path) -> FakeScanner:
    return FakeScanner(tmp_path)


@pytest.fixture
def queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
def printer_reader() -> FakePrinterReader:
    return FakePrinterReader()


@pytest.fixture
def scan_service(scanner) -> ScanService:
    return ScanService(scanner)


@pytest.fixture
def print_service(queue) -> PrintService:
    return PrintService(FakeCatalog(), ContentDocumentInspector(), queue, MAX_UPLOAD_BYTES)


@pytest.fixture
def status_service(scan_service, scanner, printer_reader) -> StatusService:
    return StatusService(scan_service, scanner, printer_reader, FakeQueueReader())


@pytest.fixture
def client(scan_service, print_service, status_service) -> TestClient:
    services = Services(scan_service, print_service, status_service)
    app = create_app(Settings(api_key=API_KEY), services)
    return TestClient(app, headers={"X-API-Key": API_KEY})


@pytest.fixture
def run():
    return asyncio.run

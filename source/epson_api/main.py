from fastapi import FastAPI, Security

from epson_api.api.client_filter import AllowedClientsMiddleware
from epson_api.api.dependencies import ApiKeyVerifier, Services
from epson_api.api.error_handlers import register_error_handlers
from epson_api.api.routes import router
from epson_api.application.print_service import PrintService
from epson_api.application.scan_service import ScanService
from epson_api.application.status_service import StatusService
from epson_api.config import Settings
from epson_api.infrastructure.command_runner import CommandRunner
from epson_api.infrastructure.content_document_inspector import ContentDocumentInspector
from epson_api.infrastructure.cups_print_queue import CupsPrintQueue
from epson_api.infrastructure.epson_driver_catalog import EpsonDriverCatalog
from epson_api.infrastructure.ipp_client import IppClient
from epson_api.infrastructure.ipp_status_readers import IppPrinterStatusReader, IppQueueStatusReader
from epson_api.infrastructure.sane_scanner import SaneScanner

API_DESCRIPTION = (
    "Print to and scan from Epson printers on a local network. Each request names the printer by its private IPv4 "
    "address in `printer_ip`, so one server can drive several printers. Send the API key in the `X-API-Key` header "
    "on every request. Check `/status` first to confirm a printer is reachable. `/scan` and `/print` act on real "
    "hardware. This specification is available without an API key at `/openapi.json`."
)


def build_services(settings: Settings) -> Services:
    runner = CommandRunner()
    catalog = EpsonDriverCatalog()
    ipp_client = IppClient()
    scanner = SaneScanner(runner, settings.scan_timeout_seconds)
    scan = ScanService(scanner)
    printing = PrintService(
        catalog, ContentDocumentInspector(), CupsPrintQueue(runner, catalog), settings.max_upload_bytes
    )
    status = StatusService(scan, scanner, IppPrinterStatusReader(ipp_client), IppQueueStatusReader(ipp_client))
    return Services(scan, printing, status)


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="Epson print and scan API",
        version="0.1.0",
        description=API_DESCRIPTION,
        dependencies=[Security(ApiKeyVerifier(settings.api_key))],
    )
    app.add_middleware(AllowedClientsMiddleware, networks=settings.allowed_networks)
    app.state.services = services or build_services(settings)
    app.include_router(router)
    register_error_handlers(app)
    return app

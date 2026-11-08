from ipaddress import IPv4Address

from epson_api.application.ports import DocumentInspector, DriverCatalog, PrintQueue
from epson_api.domain.errors import FileTooLargeError, UnsupportedDocumentError
from epson_api.domain.printing import Document, PrintSettings


class PrintService:
    def __init__(
        self,
        catalog: DriverCatalog,
        inspector: DocumentInspector,
        queue: PrintQueue,
        max_upload_bytes: int,
    ) -> None:
        self._catalog = catalog
        self._inspector = inspector
        self._queue = queue
        self._max_upload_bytes = max_upload_bytes

    async def print_document(self, printer_ip: IPv4Address, document: Document, settings: PrintSettings) -> str:
        options = self._catalog.validated_options(settings.model, settings.driver_options)
        if document.size > self._max_upload_bytes:
            raise FileTooLargeError("File is too large")
        if not self._inspector.is_supported(document.content):
            raise UnsupportedDocumentError(
                "Unsupported file type. Supported types are PDF, PostScript, plain text, "
                "PNG, JPEG, TIFF, GIF, BMP, PNM and SVG"
            )
        return await self._queue.submit(printer_ip, document, settings, options)

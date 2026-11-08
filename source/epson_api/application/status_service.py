from ipaddress import IPv4Address

from epson_api.application.ports import PrinterStatusReader, QueueStatusReader, Scanner
from epson_api.application.scan_service import ScanService
from epson_api.domain.printing import queue_name
from epson_api.domain.status import DeviceStatus, PrinterStatus, ScannerStatus


class StatusService:
    def __init__(
        self,
        scans: ScanService,
        scanner: Scanner,
        printers: PrinterStatusReader,
        queues: QueueStatusReader,
    ) -> None:
        self._scans = scans
        self._scanner = scanner
        self._printers = printers
        self._queues = queues

    async def status(self, printer_ip: IPv4Address) -> DeviceStatus:
        busy = self._scans.is_busy(printer_ip)
        return DeviceStatus(
            printer=PrinterStatus(reachable=None) if busy else await self._printers.read(printer_ip),
            queue=await self._queues.read(queue_name(printer_ip)),
            scanner=ScannerStatus(
                device=self._scanner.device_name(printer_ip),
                busy=busy,
                reachable=None if busy else await self._scanner.is_reachable(printer_ip),
            ),
        )

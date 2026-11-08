import asyncio
from ipaddress import IPv4Address

import pytest
from conftest import PRINTER_IP

from epson_api.domain.errors import ScanFailedError, ScannerBusyError
from epson_api.domain.scanning import ScanSettings

OTHER_IP = IPv4Address("192.168.0.65")


def test_second_scan_on_same_printer_is_busy(scan_service, scanner, run) -> None:
    async def scenario() -> None:
        scanner.gate = asyncio.Event()
        first = asyncio.create_task(scan_service.scan(PRINTER_IP, ScanSettings()))
        await asyncio.sleep(0)
        with pytest.raises(ScannerBusyError):
            await scan_service.scan(PRINTER_IP, ScanSettings())
        scanner.gate.set()
        await first

    run(scenario())


def test_other_printer_can_scan_concurrently(scan_service, scanner, run) -> None:
    async def scenario() -> None:
        scanner.gate = asyncio.Event()
        first = asyncio.create_task(scan_service.scan(PRINTER_IP, ScanSettings()))
        await asyncio.sleep(0)
        second = asyncio.create_task(scan_service.scan(OTHER_IP, ScanSettings()))
        await asyncio.sleep(0)
        assert scan_service.is_busy(OTHER_IP)
        scanner.gate.set()
        await asyncio.gather(first, second)

    run(scenario())


def test_lock_is_released_after_failure(scan_service, scanner, run) -> None:
    scanner.error = ScanFailedError("Scan failed: x")
    with pytest.raises(ScanFailedError):
        run(scan_service.scan(PRINTER_IP, ScanSettings()))
    assert not scan_service.is_busy(PRINTER_IP)


def test_status_skips_device_queries_during_scan(scan_service, status_service, scanner, printer_reader, run) -> None:
    async def scenario():
        scanner.gate = asyncio.Event()
        running = asyncio.create_task(scan_service.scan(PRINTER_IP, ScanSettings()))
        await asyncio.sleep(0)
        status = await status_service.status(PRINTER_IP)
        scanner.gate.set()
        await running
        return status

    status = run(scenario())
    assert status.printer.reachable is None
    assert status.scanner.busy is True
    assert status.scanner.reachable is None
    assert printer_reader.reads == 0

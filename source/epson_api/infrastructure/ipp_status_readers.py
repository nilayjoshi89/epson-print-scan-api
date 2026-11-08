import asyncio
import http.client
import struct
from ipaddress import IPv4Address
from typing import Any

from epson_api.domain.status import DeviceState, JobStatus, PrinterStatus, QueueStatus
from epson_api.infrastructure.ipp_client import STATUS_NOT_FOUND, Attributes, IppClient, IppError

PRINTER_PATH = "/ipp/print"
PRINTER_STATES = {3: "idle", 4: "processing", 5: "stopped"}
JOB_STATES = {3: "pending", 4: "pending-held", 5: "processing", 6: "processing-stopped"}
STATE_ATTRIBUTES = ("printer-state", "printer-state-reasons", "printer-is-accepting-jobs")
OPTIONAL_ATTRIBUTES = (
    "printer-make-and-model",
    "printer-alert-description",
    "marker-names",
    "marker-colors",
    "marker-levels",
)
JOB_ATTRIBUTES = ("job-id", "job-name", "job-state", "job-state-reasons")
UNREACHABLE_ERRORS = (OSError, ValueError, struct.error, http.client.HTTPException)


def first(attributes: Attributes, name: str) -> Any:
    return (attributes.get(name) or [None])[0]


def device_state(attributes: Attributes) -> DeviceState:
    state = first(attributes, "printer-state")
    return DeviceState(
        state=PRINTER_STATES.get(state, state),
        reasons=attributes.get("printer-state-reasons", []),
        accepting_jobs=first(attributes, "printer-is-accepting-jobs"),
    )


class IppPrinterStatusReader:
    def __init__(self, client: IppClient) -> None:
        self._client = client

    async def read(self, printer_ip: IPv4Address) -> PrinterStatus:
        try:
            attributes = await asyncio.to_thread(
                self._client.get_printer_attributes,
                str(printer_ip),
                PRINTER_PATH,
                STATE_ATTRIBUTES + OPTIONAL_ATTRIBUTES,
            )
        except UNREACHABLE_ERRORS:
            return PrinterStatus(reachable=False)
        return PrinterStatus(True, device_state(attributes), self._details(attributes))

    @staticmethod
    def _details(attributes: Attributes) -> dict[str, object]:
        details: dict[str, object] = {}
        for name in OPTIONAL_ATTRIBUTES:
            values = [value for value in attributes.get(name, []) if value is not None]
            if values:
                details[name] = values if name.startswith("marker-") else values[0]
        return details


class IppQueueStatusReader:
    def __init__(self, client: IppClient, host: str = "localhost") -> None:
        self._client = client
        self._host = host

    async def read(self, name: str) -> QueueStatus:
        path = f"/printers/{name}"
        try:
            attributes = await asyncio.to_thread(
                self._client.get_printer_attributes, self._host, path, STATE_ATTRIBUTES
            )
        except IppError as error:
            if error.status != STATUS_NOT_FOUND:
                raise
            return QueueStatus(name=None)

        jobs = await asyncio.to_thread(self._client.get_jobs, self._host, path, JOB_ATTRIBUTES)
        return QueueStatus(name, device_state(attributes), [self._job(job) for job in jobs])

    @staticmethod
    def _job(attributes: Attributes) -> JobStatus:
        state = first(attributes, "job-state")
        return JobStatus(
            id=first(attributes, "job-id"),
            name=first(attributes, "job-name"),
            state=JOB_STATES.get(state, state),
            reasons=attributes.get("job-state-reasons", []),
        )

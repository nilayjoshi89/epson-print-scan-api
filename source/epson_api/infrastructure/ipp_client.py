import struct
import urllib.request
from typing import Any

GET_JOBS = 0x000A
GET_PRINTER_ATTRIBUTES = 0x000B
STATUS_CLIENT_ERROR = 0x0400
STATUS_NOT_FOUND = 0x0406

TAG_OPERATION_GROUP = 0x01
TAG_JOB_GROUP = 0x02
TAG_END = 0x03
TAG_PRINTER_GROUP = 0x04
TAG_LAST_DELIMITER = 0x0F
TAG_INTEGER = 0x21
TAG_BOOLEAN = 0x22
TAG_ENUM = 0x23
TAG_FIRST_TEXT = 0x41
TAG_NAME = 0x42
TAG_KEYWORD = 0x44
TAG_URI = 0x45
TAG_CHARSET = 0x47
TAG_LANGUAGE = 0x48
TAG_LAST_TEXT = 0x49

IPP_PORT = 631
HEADER_BYTES = 8

Attributes = dict[str, list[Any]]


class IppError(ValueError):
    def __init__(self, status: int) -> None:
        super().__init__(f"IPP error status 0x{status:04x}")
        self.status = status


class IppResponseParser:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._position = HEADER_BYTES

    def groups(self) -> list[tuple[int, Attributes]]:
        status = struct.unpack(">H", self._data[2:4])[0]
        if status >= STATUS_CLIENT_ERROR:
            raise IppError(status)

        groups: list[tuple[int, Attributes]] = []
        current = ""
        while self._position < len(self._data):
            tag = self._data[self._position]
            self._position += 1
            if tag == TAG_END:
                break
            if tag <= TAG_LAST_DELIMITER:
                groups.append((tag, {}))
                current = ""
                continue
            current = self._read_field().decode(errors="replace") or current
            value = self._read_field()
            if groups and current:
                groups[-1][1].setdefault(current, []).append(self._decode(tag, value))
        return groups

    def _read_field(self) -> bytes:
        length = struct.unpack(">H", self._data[self._position : self._position + 2])[0]
        self._position += 2 + length
        return self._data[self._position - length : self._position]

    @staticmethod
    def _decode(tag: int, value: bytes) -> object:
        if tag in (TAG_INTEGER, TAG_ENUM):
            return int.from_bytes(value, signed=True)
        if tag == TAG_BOOLEAN:
            return value != b"\x00"
        return value.decode(errors="replace") if TAG_FIRST_TEXT <= tag <= TAG_LAST_TEXT else None


class IppClient:
    def __init__(self, timeout_seconds: float = 3) -> None:
        self._timeout_seconds = timeout_seconds

    def get_printer_attributes(self, host: str, path: str, requested: tuple[str, ...]) -> Attributes:
        groups = self._send(GET_PRINTER_ATTRIBUTES, host, path, requested)
        return next((attributes for tag, attributes in groups if tag == TAG_PRINTER_GROUP), {})

    def get_jobs(self, host: str, path: str, requested: tuple[str, ...]) -> list[Attributes]:
        groups = self._send(GET_JOBS, host, path, requested)
        return [attributes for tag, attributes in groups if tag == TAG_JOB_GROUP]

    def _send(self, operation: int, host: str, path: str, requested: tuple[str, ...]) -> list[tuple[int, Attributes]]:
        request = urllib.request.Request(
            f"http://{host}:{IPP_PORT}{path}",
            self._build_request(operation, host, path, requested),
            {"Content-Type": "application/ipp"},
        )
        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
            return IppResponseParser(response.read()).groups()

    @classmethod
    def _build_request(cls, operation: int, host: str, path: str, requested: tuple[str, ...]) -> bytes:
        body = struct.pack(">BBHI", 2, 0, operation, 1) + bytes([TAG_OPERATION_GROUP])
        body += cls._attribute(TAG_CHARSET, "attributes-charset", "utf-8")
        body += cls._attribute(TAG_LANGUAGE, "attributes-natural-language", "en")
        body += cls._attribute(TAG_URI, "printer-uri", f"ipp://{host}:{IPP_PORT}{path}")
        body += cls._attribute(TAG_NAME, "requesting-user-name", "root")
        for index, name in enumerate(requested):
            body += cls._attribute(TAG_KEYWORD, "" if index else "requested-attributes", name)
        return body + bytes([TAG_END])

    @staticmethod
    def _attribute(tag: int, name: str, value: str) -> bytes:
        return struct.pack(">BH", tag, len(name)) + name.encode() + struct.pack(">H", len(value)) + value.encode()

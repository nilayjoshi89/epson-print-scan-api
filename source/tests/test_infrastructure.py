import gzip
import io
import struct
from ipaddress import IPv4Address
from pathlib import Path

import pytest

from epson_api.domain.errors import ScanFailedError, UnavailableOptionError, UnknownModelError
from epson_api.domain.printing import Document, PrintSettings
from epson_api.domain.scanning import ScanArea, ScanSettings
from epson_api.infrastructure.command_runner import CommandResult
from epson_api.infrastructure.content_document_inspector import ContentDocumentInspector
from epson_api.infrastructure.cups_print_queue import CupsPrintQueue
from epson_api.infrastructure.epson_driver_catalog import EpsonDriverCatalog
from epson_api.infrastructure.ipp_client import STATUS_NOT_FOUND, IppError, IppResponseParser
from epson_api.infrastructure.sane_scanner import SaneScanner

IP = IPv4Address("192.168.0.64")


SUBMITTED = CommandResult(0, "request id is q-1 (1 file(s))", "")


class RecordingRunner:
    def __init__(self, result: CommandResult = SUBMITTED) -> None:
        self.result = result
        self.commands: list[tuple[str, ...]] = []

    async def run(self, *command: str, timeout: int = 30) -> CommandResult:
        self.commands.append(command)
        return self.result


@pytest.mark.parametrize(
    "content",
    [
        b"%PDF-1.7",
        b"\r\n%PDF-1.7",
        b"%!PS-Adobe",
        b"\x89PNG\r\n\x1a\n",
        b"\xff\xd8\xff\xe0",
        b"GIF89a",
        b"II*\x00",
        b"MM\x00*",
        b"BM\x00\x00",
        b"P6\n1 1\n255\n",
        b"plain text\n",
        "café, 1, 2\n".encode(),
        b"<svg></svg>",
    ],
)
def test_inspector_accepts_supported_content(content) -> None:
    assert ContentDocumentInspector().is_supported(io.BytesIO(content))


@pytest.mark.parametrize(
    "content",
    [b"", b"<!DOCTYPE html><html>", b"<html>", b"{\\rtf1 x}", b"PK\x03\x04\x00\x00", b"\xff\xfe\x00\x01"],
)
def test_inspector_rejects_unsupported_content(content) -> None:
    assert not ContentDocumentInspector().is_supported(io.BytesIO(content))


def test_inspector_rewinds_content() -> None:
    content = io.BytesIO(b"%PDF-1.7")
    ContentDocumentInspector().is_supported(content)
    assert content.tell() == 0


@pytest.fixture
def catalog(tmp_path) -> EpsonDriverCatalog:
    for package, name in (
        ("epson-inkjet-printer-escpr", "Epson-L3250_Series-epson-inkjet-printer-escpr.ppd.gz"),
        ("epson-inkjet-printer-escpr2", "Epson-WF-C5790_Series-epson-inkjet-printer-escpr2.ppd.gz"),
    ):
        directory = tmp_path / package / "ppds" / "Epson"
        directory.mkdir(parents=True)
        with gzip.open(directory / name, "wt") as driver:
            driver.write('*DefaultInk: COLOR\n*Ink COLOR/Off: ""\n*Ink MONO/On: ""\n*PageSize A4/A4: ""\n')
    return EpsonDriverCatalog(tmp_path)


def test_catalog_finds_models_across_installed_drivers(catalog) -> None:
    assert catalog.driver_path("L3250_Series").parts[-4] == "epson-inkjet-printer-escpr"
    assert catalog.driver_path("WF-C5790_Series").parts[-4] == "epson-inkjet-printer-escpr2"


def test_catalog_requires_exact_model_name(catalog) -> None:
    with pytest.raises(UnknownModelError):
        catalog.driver_path("L3250")


def test_catalog_returns_only_options_the_driver_defines(catalog) -> None:
    requested = {"Ink": "MONO", "PageSize": "A4", "Brightness": "0"}
    assert catalog.validated_options("L3250_Series", requested) == {"Ink": "MONO", "PageSize": "A4"}


def test_catalog_rejects_unavailable_value(catalog) -> None:
    with pytest.raises(UnavailableOptionError, match="Ink PURPLE is not available for model L3250_Series"):
        catalog.validated_options("L3250_Series", {"Ink": "PURPLE"})


def test_catalog_rejects_unknown_model(catalog) -> None:
    with pytest.raises(UnknownModelError, match="No driver for model Nope"):
        catalog.validated_options("Nope", {})


def test_scanner_builds_scanimage_command(run) -> None:
    runner = RecordingRunner()
    settings = ScanSettings(600, "Gray", "pdf", ScanArea(210, 297))
    output = run(SaneScanner(runner, 600).scan(IP, settings))
    output.unlink()
    assert runner.commands[0] == (
        "scanimage",
        "-d",
        "epsonds:net:192.168.0.64",
        "--format",
        "pdf",
        "--mode=Gray",
        "--resolution=600",
        "-x",
        "210",
        "-y",
        "297",
        "-o",
        str(output),
    )


def test_scanner_removes_output_after_failure(run) -> None:
    runner = RecordingRunner(CommandResult(1, "", "device error\n"))
    with pytest.raises(ScanFailedError, match="Scan failed: device error"):
        run(SaneScanner(runner, 600).scan(IP, ScanSettings()))
    assert not Path(runner.commands[0][-1]).exists()


def test_queue_is_created_once_then_reused(catalog, run) -> None:
    runner = RecordingRunner()
    queue = CupsPrintQueue(runner, catalog)

    async def submit_twice() -> None:
        for _ in range(2):
            document = Document(io.BytesIO(b"%PDF-"), 5, "a.pdf")
            job = await queue.submit(IP, document, PrintSettings(), {"Ink": "COLOR"})
            assert job == "q-1"

    run(submit_twice())
    assert [command[0] for command in runner.commands] == ["lpadmin", "lp", "lp"]
    lpadmin = runner.commands[0]
    assert lpadmin[1:5] == ("-p", "epson-192-168-0-64", "-v", "socket://192.168.0.64:9100")


def test_queue_translates_layout_options(catalog, run) -> None:
    runner = RecordingRunner()
    settings = PrintSettings(copies=2, page_ranges="1-3", orientation="landscape", number_up=2, fit_to_page=True)

    async def submit() -> None:
        document = Document(io.BytesIO(b"%PDF-"), 5, "a.pdf")
        await CupsPrintQueue(runner, catalog).submit(IP, document, settings, {"Ink": "MONO"})

    run(submit())
    command = runner.commands[1]
    assert command[:7] == ("lp", "-d", "epson-192-168-0-64", "-n", "2", "-t", "a.pdf")
    options = [command[index + 1] for index, part in enumerate(command) if part == "-o"]
    assert options == ["Ink=MONO", "number-up=2", "page-ranges=1-3", "orientation-requested=4", "fit-to-page"]


def attribute(tag: int, name: bytes, value: bytes) -> bytes:
    return struct.pack(">BH", tag, len(name)) + name + struct.pack(">H", len(value)) + value


def ipp_response(status: int, body: bytes) -> bytes:
    return struct.pack(">BBHI", 2, 0, status, 1) + body + b"\x03"


def test_parser_reads_typed_and_repeated_values() -> None:
    body = b"\x04"
    body += attribute(0x23, b"printer-state", struct.pack(">i", 3))
    body += attribute(0x22, b"printer-is-accepting-jobs", b"\x01")
    body += attribute(0x44, b"printer-state-reasons", b"media-empty-error")
    body += attribute(0x44, b"", b"cover-open-report")
    assert IppResponseParser(ipp_response(0, body)).groups() == [
        (
            0x04,
            {
                "printer-state": [3],
                "printer-is-accepting-jobs": [True],
                "printer-state-reasons": ["media-empty-error", "cover-open-report"],
            },
        )
    ]


def test_parser_raises_with_status() -> None:
    with pytest.raises(IppError) as error:
        IppResponseParser(ipp_response(STATUS_NOT_FOUND, b"")).groups()
    assert error.value.status == STATUS_NOT_FOUND


def test_parser_rejects_truncated_data() -> None:
    with pytest.raises(struct.error):
        IppResponseParser(b"\x02").groups()

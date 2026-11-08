import pytest
from conftest import PRINTER_IP

from epson_api.domain.errors import CommandTimeoutError, ScanFailedError

IP = str(PRINTER_IP)
PDF = ("a.pdf", b"%PDF-1.7", "application/pdf")


def test_missing_key_is_rejected(client) -> None:
    response = client.get("/status", params={"printer_ip": IP}, headers={"X-API-Key": ""})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


@pytest.mark.parametrize("address", ["8.8.8.8", "127.0.0.1", "169.254.1.1", "printer.local"])
def test_invalid_printer_ip_is_rejected(client, address) -> None:
    assert client.get("/status", params={"printer_ip": address}).status_code == 422


def test_scan_returns_file(client, scanner) -> None:
    response = client.post("/scan", json={"printer_ip": IP, "format": "pdf", "paper_size": "A4"})
    assert response.status_code == 200
    assert response.content == b"scanned"
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="scan.pdf"' in response.headers["content-disposition"]
    settings = scanner.requests[0][1]
    assert (settings.area.width_mm, settings.area.height_mm) == (210, 297)


def test_scan_full_uses_no_area(client, scanner) -> None:
    client.post("/scan", json={"printer_ip": IP})
    assert scanner.requests[0][1].area is None


def test_scan_custom_area(client, scanner) -> None:
    client.post("/scan", json={"printer_ip": IP, "paper_size": "custom", "width_mm": 100, "height_mm": 150.5})
    area = scanner.requests[0][1].area
    assert (area.width_mm, area.height_mm) == (100, 150.5)


@pytest.mark.parametrize(
    "fields",
    [
        {"paper_size": "Legal"},
        {"paper_size": "custom"},
        {"paper_size": "custom", "width_mm": 100},
        {"paper_size": "A4", "width_mm": 100},
        {"paper_size": "custom", "width_mm": 300, "height_mm": 100},
        {"paper_size": "custom", "width_mm": 100, "height_mm": 400},
        {"paper_size": "custom", "width_mm": 0, "height_mm": 100},
        {"resolution": 999},
        {"format": "bmp"},
    ],
)
def test_invalid_scan_request_is_rejected(client, fields) -> None:
    assert client.post("/scan", json={"printer_ip": IP, **fields}).status_code == 422


@pytest.mark.parametrize(
    ("error", "status"),
    [(ScanFailedError("Scan failed: x"), 502), (CommandTimeoutError("scanimage timed out"), 504)],
)
def test_scan_errors_are_mapped(client, scanner, error, status) -> None:
    scanner.error = error
    response = client.post("/scan", json={"printer_ip": IP})
    assert response.status_code == status
    assert response.json() == {"detail": str(error)}


def test_print_uses_defaults(client, queue) -> None:
    response = client.post("/print", files={"file": PDF}, data={"printer_ip": IP})
    assert response.status_code == 200
    assert response.json() == {"job_id": "epson-192-168-0-64-1"}
    _, title, settings, options = queue.submitted[0]
    assert title == "a.pdf"
    assert settings.copies == 1
    assert options == {
        "Ink": "COLOR",
        "PageSize": "A4",
        "MediaType": "PLAIN_NORMAL",
        "Brightness": "0",
        "Contrast": "0",
        "Saturation": "0",
    }


def test_print_combines_paper_and_quality(client, queue) -> None:
    data = {"printer_ip": IP, "paper_type": "PMPHOTO", "quality": "DRAFT"}
    client.post("/print", files={"file": PDF}, data=data)
    assert queue.submitted[0][3]["MediaType"] == "PMPHOTO_DRAFT"


@pytest.mark.parametrize(
    "field",
    [
        {"ink": "PURPLE"},
        {"quality": "ULTRA"},
        {"brightness": "26"},
        {"contrast": "-26"},
        {"page_ranges": "1-2;x"},
        {"orientation": "sideways"},
        {"number_up": "3"},
        {"copies": "0"},
        {"page_size": "A4;rm"},
        {"page_size": "Nope"},
    ],
)
def test_invalid_print_option_is_rejected(client, queue, field) -> None:
    assert client.post("/print", files={"file": PDF}, data={"printer_ip": IP, **field}).status_code == 422
    assert not queue.submitted


def test_print_rejects_large_file(client, queue) -> None:
    response = client.post("/print", files={"file": ("a.pdf", b"%PDF-" + bytes(2048))}, data={"printer_ip": IP})
    assert response.status_code == 413
    assert not queue.submitted


def test_print_rejects_unsupported_file(client, queue) -> None:
    response = client.post("/print", files={"file": ("a.bin", b"\x00\x01\x02")}, data={"printer_ip": IP})
    assert response.status_code == 415
    assert not queue.submitted


def test_status_uses_ipp_field_names(client) -> None:
    assert client.get("/status", params={"printer_ip": IP}).json() == {
        "printer": {
            "reachable": True,
            "printer-state": "idle",
            "printer-state-reasons": ["none"],
            "printer-is-accepting-jobs": True,
            "printer-make-and-model": "L3250",
        },
        "queue": {
            "name": None,
            "printer-state": None,
            "printer-state-reasons": [],
            "printer-is-accepting-jobs": None,
            "jobs": [],
        },
        "scanner": {"device": f"epsonds:net:{IP}", "busy": False, "reachable": True},
    }

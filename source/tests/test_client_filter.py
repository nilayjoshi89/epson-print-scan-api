import pytest
from conftest import API_KEY, PRINTER_IP
from fastapi.testclient import TestClient

from epson_api.api.dependencies import Services
from epson_api.config import Settings, parse_networks
from epson_api.main import create_app


@pytest.fixture
def client_from(scan_service, print_service, status_service):
    def build(address: str, allowed: str) -> TestClient:
        settings = Settings(api_key=API_KEY, allowed_networks=parse_networks(allowed))
        app = create_app(settings, Services(scan_service, print_service, status_service))
        return TestClient(app, headers={"X-API-Key": API_KEY}, client=(address, 50000))

    return build


def status_code(client: TestClient) -> int:
    return client.get("/status", params={"printer_ip": str(PRINTER_IP)}).status_code


@pytest.mark.parametrize(
    ("address", "allowed"),
    [
        ("203.0.113.9", "*"),
        ("203.0.113.9", "10.0.0.1, *"),
        ("192.168.0.10", "192.168.0.10"),
        ("192.168.0.10", "10.0.0.1, 192.168.0.0/24"),
        ("192.168.0.10", "192.168.0.99/24"),
    ],
)
def test_allowed_client_reaches_the_api(client_from, address, allowed) -> None:
    assert status_code(client_from(address, allowed)) == 200


@pytest.mark.parametrize(
    ("address", "allowed"),
    [
        ("192.168.0.11", "192.168.0.10"),
        ("192.168.1.10", "192.168.0.0/24"),
        ("not-an-ip", "192.168.0.0/24"),
    ],
)
def test_other_client_is_rejected(client_from, address, allowed) -> None:
    response = client_from(address, allowed).get("/status", params={"printer_ip": str(PRINTER_IP)})
    assert response.status_code == 403
    assert response.json() == {"detail": "Client IP is not allowed"}


def test_filter_runs_before_the_api_key_check(client_from) -> None:
    client = client_from("192.168.1.10", "192.168.0.0/24")
    assert client.get("/status", headers={"X-API-Key": "wrong"}).status_code == 403


def test_filter_also_protects_the_spec(client_from) -> None:
    assert client_from("192.168.1.10", "192.168.0.0/24").get("/openapi.json").status_code == 403


@pytest.mark.parametrize("env", [{}, {"ALLOWED_IPS": ""}, {"ALLOWED_IPS": "*"}])
def test_all_clients_are_allowed_by_default(env) -> None:
    assert Settings.from_env({"API_KEY": API_KEY, **env}).allowed_networks == ()


def test_env_accepts_ips_and_cidr_ranges() -> None:
    settings = Settings.from_env({"API_KEY": API_KEY, "ALLOWED_IPS": "192.168.0.10, 172.18.0.0/16"})
    assert settings.allowed_networks == parse_networks("192.168.0.10/32,172.18.0.0/16")


def test_invalid_entry_stops_startup() -> None:
    with pytest.raises(ValueError, match="does not appear to be"):
        parse_networks("192.168.0.300")

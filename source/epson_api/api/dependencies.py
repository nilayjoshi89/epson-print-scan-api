import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from epson_api.application.print_service import PrintService
from epson_api.application.scan_service import ScanService
from epson_api.application.status_service import StatusService


@dataclass(frozen=True)
class Services:
    scan: ScanService
    printing: PrintService
    status: StatusService


API_KEY_HEADER = APIKeyHeader(
    name="X-API-Key",
    scheme_name="ApiKey",
    description="The value of `API_KEY` configured on the server.",
    auto_error=False,
)


class ApiKeyVerifier:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key.encode()

    def __call__(self, key: Annotated[str | None, Security(API_KEY_HEADER)]) -> None:
        if key is None or not hmac.compare_digest(key.encode(), self._api_key):
            raise HTTPException(401, "Invalid or missing API key")


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDependency = Annotated[Services, Depends(get_services)]

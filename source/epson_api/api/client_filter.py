from ipaddress import ip_address

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from epson_api.config import IpNetwork


class AllowedClientsMiddleware:
    def __init__(self, app: ASGIApp, networks: tuple[IpNetwork, ...]) -> None:
        self._app = app
        self._networks = networks

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not self._is_allowed(scope.get("client")):
            await JSONResponse({"detail": "Client IP is not allowed"}, 403)(scope, receive, send)
            return
        await self._app(scope, receive, send)

    def _is_allowed(self, client: tuple[str, int] | None) -> bool:
        if not self._networks:
            return True
        if client is None:
            return False
        try:
            address = ip_address(client[0])
        except ValueError:
            return False
        return any(address in network for network in self._networks)

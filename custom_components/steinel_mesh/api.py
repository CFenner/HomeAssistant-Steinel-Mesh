"""Client for the gateway's local HTTP API.

Deliberately free of Home Assistant imports so it can be tested on its own.
The gateway protects its web server with HTTP Digest authentication.
"""

from __future__ import annotations

from typing import Any

import httpx


class GatewayError(Exception):
    """The gateway could not be reached or returned an error."""


class GatewayAuthError(GatewayError):
    """The gateway rejected the credentials."""


class GatewayClient:
    """Reads node state from and sends commands to the gateway."""

    def __init__(
        self, client: httpx.AsyncClient, host: str, username: str, password: str
    ) -> None:
        self._client = client
        self._base = f"http://{host}"
        self._auth = httpx.DigestAuth(username, password)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(
                method, self._base + path, auth=self._auth, timeout=10.0, **kwargs
            )
        except httpx.HTTPError as err:
            raise GatewayError(f"Cannot reach the gateway: {err}") from err
        if response.status_code == 401:
            raise GatewayAuthError("Invalid username or password")
        if response.status_code >= 400:
            try:
                message = response.json().get("message", response.text)
            except ValueError:
                message = response.text
            raise GatewayError(f"Gateway returned {response.status_code}: {message}")
        try:
            return response.json()
        except ValueError as err:
            raise GatewayError("Gateway returned invalid JSON") from err

    async def get_nodes(self) -> dict[str, Any]:
        """Return the node list including live state."""
        return await self._request("GET", "/api/nodes")

    async def send_command(
        self,
        address: str,
        *,
        on: bool | None = None,
        brightness: int | None = None,
        auto: bool | None = None,
        threshold: int | None = None,
        run_on: int | None = None,
    ) -> None:
        """Queue a command.

        brightness is 0-100 percent, threshold 1-1500 lx, run_on 1-3600 seconds.
        """
        params: dict[str, str] = {}
        if on is not None:
            params["on"] = "1" if on else "0"
        if brightness is not None:
            params["brightness"] = str(max(0, min(100, brightness)))
        if auto is not None:
            params["auto"] = "1" if auto else "0"
        if threshold is not None:
            params["threshold"] = str(max(1, min(1500, threshold)))
        if run_on is not None:
            params["run_on"] = str(max(1, min(3600, run_on)))
        # The gateway requires a Content-Length header on POST, so send an
        # explicit empty form body; the values travel in the query string.
        await self._request(
            "POST", f"/api/nodes/{address}", params=params, data={}
        )

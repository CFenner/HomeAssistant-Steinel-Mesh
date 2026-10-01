"""Polls the gateway and shares the result with all entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GatewayAuthError, GatewayClient, GatewayError
from .const import DOMAIN, REFRESH_AFTER_COMMAND, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class GatewayCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Data is a mapping of node address (e.g. "0x0008") to the node dict."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: GatewayClient
    ) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            payload = await self.client.get_nodes()
        except GatewayAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GatewayError as err:
            raise UpdateFailed(str(err)) from err
        return {node["address"]: node for node in payload.get("nodes", [])}

    async def async_command(self, address: str, **kwargs: Any) -> None:
        """Send a command, then re-read state once the mesh has acted on it."""
        try:
            await self.client.send_command(address, **kwargs)
        except GatewayError as err:
            raise UpdateFailed(str(err)) from err

        async def _refresh(_now: Any) -> None:
            await self.async_request_refresh()

        async_call_later(self.hass, REFRESH_AFTER_COMMAND, _refresh)

"""Polls the gateway and shares the result with all entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GatewayAuthError, GatewayClient, GatewayError
from .const import DOMAIN, REFRESH_AFTER_COMMAND, UPDATE_INTERVAL
from .device_link import apply_revisions, link_nodes_to_gateway, revisions_from_node

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
        nodes = {node["address"]: node for node in payload.get("nodes", [])}
        self._link_to_gateway(payload, nodes)
        self._record_revisions(nodes)
        return nodes

    def _record_revisions(self, nodes: dict[str, dict[str, Any]]) -> None:
        """Show a device's reported firmware and hardware revision on its device page."""
        registry = dr.async_get(self.hass)
        entry_id = self.config_entry.entry_id
        for address, node in nodes.items():
            firmware, hardware = revisions_from_node(node)
            if firmware is not None or hardware is not None:
                apply_revisions(
                    registry,
                    (DOMAIN, f"{entry_id}_{address}"),
                    sw_version=firmware,
                    hw_version=hardware,
                )

    def _link_to_gateway(self, payload: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> None:
        """Show the mesh devices as connected via the gateway's ESPHome device.

        The gateway reports its Wi-Fi MAC, which is how Home Assistant registers
        the ESPHome device. Older gateway firmware does not report it; then no
        link is made. The devices are created by the entities after the first
        refresh, so this runs on every update until they all exist.
        """
        mac = (payload.get("gateway") or {}).get("mac")
        if not mac:
            return
        entry_id = self.config_entry.entry_id
        link_nodes_to_gateway(
            dr.async_get(self.hass),
            gateway_connection=(dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac)),
            node_identifiers=[(DOMAIN, f"{entry_id}_{address}") for address in nodes],
        )

    async def async_command(self, address: str, **kwargs: Any) -> None:
        """Send a command, then re-read state once the mesh has acted on it."""
        try:
            await self.client.send_command(address, **kwargs)
        except GatewayError as err:
            raise UpdateFailed(str(err)) from err

        async def _refresh(_now: Any) -> None:
            await self.async_request_refresh()

        async_call_later(self.hass, REFRESH_AFTER_COMMAND, _refresh)

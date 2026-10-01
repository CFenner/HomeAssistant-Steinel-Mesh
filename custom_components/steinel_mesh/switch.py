"""Automatic (sensor controlled) mode of a lamp."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import GatewayNodeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SteinelAutoMode(coordinator, address)
        for address, node in coordinator.data.items()
        if "light_control" in node.get("roles", [])
    )


class SteinelAutoMode(GatewayNodeEntity, SwitchEntity):
    """On: the lamp follows its own sensors. Off: manual control."""

    _attr_translation_key = "auto_mode"
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator, address: str) -> None:
        super().__init__(coordinator, address, "auto_mode")

    @property
    def is_on(self) -> bool | None:
        return self.node_state.get("auto")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self._address, auto=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self._address, auto=False)

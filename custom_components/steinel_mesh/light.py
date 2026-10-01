"""Lamps: on/off and brightness."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
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
        SteinelLight(coordinator, address)
        for address, node in coordinator.data.items()
        if "light" in node.get("roles", [])
    )


class SteinelLight(GatewayNodeEntity, LightEntity):
    _attr_name = None
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, coordinator, address: str) -> None:
        super().__init__(coordinator, address, "light")

    @property
    def is_on(self) -> bool | None:
        return self.node_state.get("on")

    @property
    def brightness(self) -> int | None:
        percent = self.node_state.get("brightness")
        return None if percent is None else round(percent * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            await self.coordinator.async_command(
                self._address, brightness=round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            )
        else:
            await self.coordinator.async_command(self._address, on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self._address, on=False)

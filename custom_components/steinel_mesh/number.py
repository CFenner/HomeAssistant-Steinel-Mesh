"""Twilight threshold and on-time after motion of a lamp."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import GatewayNodeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SteinelTwilightThreshold(coordinator, address)
        for address, node in coordinator.data.items()
        if {"sensor", "light_control"} <= set(node.get("roles", []))
    )

    # A lamp reports its on-time only once the gateway has read it, which can
    # take several passes, so the entities are created as the values appear.
    known: set[str] = set()

    def _discover() -> None:
        new = [
            SteinelRunOnTime(coordinator, address)
            for address, node in coordinator.data.items()
            if address not in known and node.get("state", {}).get("run_on") is not None
        ]
        known.update(entity._address for entity in new)
        if new:
            async_add_entities(new)

    _discover()
    entry.async_on_unload(coordinator.async_add_listener(_discover))


class SteinelTwilightThreshold(GatewayNodeEntity, NumberEntity):
    """Ambient light level below which the lamp's automatic mode switches on."""

    _attr_translation_key = "twilight_threshold"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.ILLUMINANCE
    _attr_native_unit_of_measurement = LIGHT_LUX
    _attr_native_min_value = 1
    _attr_native_max_value = 1500
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, address: str) -> None:
        super().__init__(coordinator, address, "twilight_threshold")

    @property
    def native_value(self) -> float | None:
        return self.node_state.get("threshold")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_command(self._address, threshold=int(value))


class SteinelRunOnTime(GatewayNodeEntity, NumberEntity):
    """How long the lamp stays on after the last motion."""

    _attr_translation_key = "run_on_time"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_native_min_value = 1
    _attr_native_max_value = 3600
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, address: str) -> None:
        super().__init__(coordinator, address, "run_on_time")

    @property
    def native_value(self) -> float | None:
        return self.node_state.get("run_on")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_command(self._address, run_on=int(value))

"""Node reachability and presence/motion readings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PROPERTY_MOTION, PROPERTY_PRESENCE
from .entity import GatewayNodeEntity, add_sensor_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SteinelReachable(coordinator, address) for address in coordinator.data)

    def factory(address: str, reading: dict[str, Any]):
        if reading["property"] == PROPERTY_PRESENCE:
            return SteinelDetection(coordinator, address, reading, "presence")
        if reading["property"] == PROPERTY_MOTION:
            return SteinelDetection(coordinator, address, reading, "motion")
        return None

    add_sensor_entities(entry, coordinator, async_add_entities, factory)


class SteinelReachable(GatewayNodeEntity, BinarySensorEntity):
    """Whether the gateway currently gets answers from the node."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "reachable"

    def __init__(self, coordinator, address: str) -> None:
        super().__init__(coordinator, address, "reachable")

    @property
    def available(self) -> bool:
        # Stay available while unreachable, otherwise the state could never
        # show "disconnected".
        return self.coordinator.last_update_success and self._address in self.coordinator.data

    @property
    def is_on(self) -> bool:
        return bool(self.node_state.get("reachable"))


class SteinelDetection(GatewayNodeEntity, BinarySensorEntity):
    def __init__(self, coordinator, address: str, reading: dict[str, Any], kind: str) -> None:
        self._element = reading["element"]
        self._property = reading["property"]
        self._kind = kind
        super().__init__(coordinator, address, f"{kind}_{self._element}")
        self._attr_device_class = (
            BinarySensorDeviceClass.OCCUPANCY
            if kind == "presence"
            else BinarySensorDeviceClass.MOTION
        )
        self._attr_translation_key = kind

    @property
    def is_on(self) -> bool | None:
        for reading in self.node_state.get("sensors", []):
            if reading["element"] == self._element and reading["property"] == self._property:
                return reading.get(self._kind)
        return None

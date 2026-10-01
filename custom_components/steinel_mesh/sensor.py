"""Illuminance, device identity and revisions, plus raw values for properties we cannot decode."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PROPERTY_FIRMWARE, PROPERTY_HARDWARE, PROPERTY_MOTION, PROPERTY_PRESENCE
from .entity import GatewayNodeEntity, add_sensor_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        entity
        for address in coordinator.data
        for entity in (SteinelCompanyId(coordinator, address), SteinelProductId(coordinator, address))
    )

    def factory(address: str, reading: dict[str, Any]):
        if "lux" in reading:
            return SteinelLux(coordinator, address, reading)
        if reading["property"] == PROPERTY_FIRMWARE:
            # An empty answer means the device has no firmware revision to report.
            return SteinelRevision(coordinator, address, reading, "firmware") if "firmware_revision" in reading else None
        if reading["property"] == PROPERTY_HARDWARE:
            return SteinelRevision(coordinator, address, reading, "hardware") if "hardware_revision" in reading else None
        if reading["property"] in (PROPERTY_PRESENCE, PROPERTY_MOTION):
            return None  # shown as a binary sensor
        return SteinelRawReading(coordinator, address, reading)

    add_sensor_entities(entry, coordinator, async_add_entities, factory)


class _Reading(GatewayNodeEntity):
    def __init__(self, coordinator, address: str, reading: dict[str, Any], kind: str) -> None:
        self._element = reading["element"]
        self._property = reading["property"]
        super().__init__(coordinator, address, f"{kind}_{self._element}_{self._property}")

    @property
    def reading(self) -> dict[str, Any] | None:
        for reading in self.node_state.get("sensors", []):
            if reading["element"] == self._element and reading["property"] == self._property:
                return reading
        return None


class SteinelLux(_Reading, SensorEntity):
    _attr_translation_key = "illuminance"
    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX

    def __init__(self, coordinator, address: str, reading: dict[str, Any]) -> None:
        super().__init__(coordinator, address, reading, "lux")
        self._attr_translation_placeholders = {"element": str(self._element)}

    @property
    def native_value(self) -> float | None:
        reading = self.reading
        return None if reading is None else reading.get("lux")


class SteinelRawReading(_Reading, SensorEntity):
    """Undecoded sensor property; hidden by default, useful to see what a device offers."""

    _attr_translation_key = "raw_reading"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, address: str, reading: dict[str, Any]) -> None:
        super().__init__(coordinator, address, reading, "raw")
        self._attr_translation_placeholders = {
            "property": str(self._property),
            "element": str(self._element),
        }

    @property
    def native_value(self) -> str | None:
        reading = self.reading
        return None if reading is None else reading.get("raw")


class _NodeInfo(GatewayNodeEntity, SensorEntity):
    """Identity that comes from the imported network and does not change."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    @property
    def available(self) -> bool:
        # Known from the backup, so it does not depend on the device answering.
        return self.coordinator.last_update_success and self._address in self.coordinator.data


class SteinelCompanyId(_NodeInfo):
    _attr_translation_key = "company_id"

    def __init__(self, coordinator, address: str) -> None:
        super().__init__(coordinator, address, "company_id")

    @property
    def native_value(self) -> str | None:
        company = self.node.get("company_id")
        manufacturer = self.node.get("manufacturer")
        return f"{company} ({manufacturer})" if company and manufacturer else company


class SteinelProductId(_NodeInfo):
    _attr_translation_key = "product_id"

    def __init__(self, coordinator, address: str) -> None:
        super().__init__(coordinator, address, "product_id")

    @property
    def native_value(self) -> str | None:
        return self.node.get("product_id")


class SteinelRevision(_Reading, SensorEntity):
    """Firmware or hardware revision, shown only for devices that report one."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, address: str, reading: dict[str, Any], kind: str) -> None:
        self._kind = kind
        super().__init__(coordinator, address, reading, kind)
        self._attr_translation_key = f"{kind}_revision"

    @property
    def native_value(self) -> int | None:
        reading = self.reading
        return None if reading is None else reading.get(f"{self._kind}_revision")

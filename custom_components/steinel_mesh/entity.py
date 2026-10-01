"""Shared base entity."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GatewayCoordinator


class GatewayNodeEntity(CoordinatorEntity[GatewayCoordinator]):
    """An entity that belongs to one mesh node."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GatewayCoordinator, address: str, key: str) -> None:
        super().__init__(coordinator)
        self._address = address
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{address}_{key}"
        node = coordinator.data[address]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{address}")},
            name=node["name"],
            manufacturer=node.get("manufacturer") or "Steinel",
            model=node.get("product") or f"Product {node.get('product_id', '?')}",
        )

    @property
    def node(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._address, {})

    @property
    def node_state(self) -> dict[str, Any]:
        return self.node.get("state", {})

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._address in self.coordinator.data
            and bool(self.node_state.get("reachable"))
        )


def add_sensor_entities(entry, coordinator, async_add_entities, factory) -> None:
    """Create entities for sensor readings as they first appear.

    A node only reports which sensor properties it has after the gateway has
    polled it, so these entities cannot all be created at setup time.
    `factory(address, reading)` returns an entity, or None to skip a reading.
    """
    known: set[tuple[str, int, str]] = set()

    def _discover() -> None:
        new = []
        for address, node in coordinator.data.items():
            for reading in node.get("state", {}).get("sensors", []):
                identity = (address, reading["element"], reading["property"])
                if identity in known:
                    continue
                entity = factory(address, reading)
                known.add(identity)
                if entity is not None:
                    new.append(entity)
        if new:
            async_add_entities(new)

    _discover()
    entry.async_on_unload(coordinator.async_add_listener(_discover))

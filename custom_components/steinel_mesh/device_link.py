"""Keep the mesh devices' registry entries in step with what the gateway reports.

Links the devices to the gateway's ESPHome device and records their firmware
and hardware revision.

Home Assistant's `via_device` in DeviceInfo takes an identifier, but an ESPHome
device is registered with a MAC connection only, so it cannot be named there.
The link is instead set in the device registry once both devices exist.

This module has no Home Assistant imports so the logic can be tested alone.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def link_nodes_to_gateway(
    registry: Any,
    *,
    gateway_connection: tuple[str, str],
    node_identifiers: Iterable[tuple[str, str]],
) -> int:
    """Point each node's device at the gateway device; return how many changed.

    Does nothing while the gateway's device is unknown (for example before the
    ESPHome integration has registered it), so it is safe to call on every
    update. Nodes whose device does not exist yet are skipped and linked on a
    later call.
    """
    gateway = registry.async_get_device(connections={gateway_connection})
    if gateway is None:
        return 0
    changed = 0
    for identifier in node_identifiers:
        device = registry.async_get_device(identifiers={identifier})
        if device is not None and device.via_device_id != gateway.id:
            registry.async_update_device(device.id, via_device_id=gateway.id)
            changed += 1
    return changed


def revisions_from_node(node: dict[str, Any]) -> tuple[str | None, str | None]:
    """Firmware and hardware revision a node reported, if it reported any.

    The gateway probes each device for the standard firmware and hardware
    revision properties. A device that does not have them answers without a
    value, so no revision is reported.
    """
    firmware = hardware = None
    for reading in node.get("state", {}).get("sensors", []):
        if "firmware_revision" in reading:
            firmware = str(reading["firmware_revision"])
        if "hardware_revision" in reading:
            hardware = str(reading["hardware_revision"])
    return firmware, hardware


def apply_revisions(
    registry: Any,
    identifier: tuple[str, str],
    *,
    sw_version: str | None,
    hw_version: str | None,
) -> bool:
    """Record a device's revisions in the registry; return whether anything changed."""
    device = registry.async_get_device(identifiers={identifier})
    if device is None:
        return False
    changes: dict[str, str] = {}
    if sw_version is not None and device.sw_version != sw_version:
        changes["sw_version"] = sw_version
    if hw_version is not None and device.hw_version != hw_version:
        changes["hw_version"] = hw_version
    if not changes:
        return False
    registry.async_update_device(device.id, **changes)
    return True

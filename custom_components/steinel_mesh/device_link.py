"""Link the mesh devices to the gateway's ESPHome device.

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

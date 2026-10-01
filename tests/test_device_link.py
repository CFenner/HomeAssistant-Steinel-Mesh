"""Tests for linking mesh devices to the gateway device (no Home Assistant needed)."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "device_link",
    Path(__file__).parent.parent / "custom_components" / "steinel_mesh" / "device_link.py",
)
device_link = importlib.util.module_from_spec(spec)
spec.loader.exec_module(device_link)

GATEWAY = ("mac", "a0:76:4e:19:68:04")


class FakeRegistry:
    """Just enough of the device registry for the linking logic."""

    def __init__(self, devices):
        self.devices = devices  # id -> SimpleNamespace(id, identifiers, connections, via_device_id)
        self.updates = []

    def async_get_device(self, identifiers=None, connections=None):
        for device in self.devices.values():
            if identifiers and identifiers & device.identifiers:
                return device
            if connections and connections & device.connections:
                return device
        return None

    def async_update_device(self, device_id, **changes):
        self.updates.append((device_id, changes))
        for key, value in changes.items():
            setattr(self.devices[device_id], key, value)


def device(device_id, identifiers=(), connections=(), via=None):
    return SimpleNamespace(
        id=device_id,
        identifiers=set(identifiers),
        connections=set(connections),
        via_device_id=via,
    )


NODES = [("steinel_mesh", "entry_0x0008"), ("steinel_mesh", "entry_0x000C")]


def test_links_nodes_to_the_gateway_device():
    registry = FakeRegistry(
        {
            "gw": device("gw", connections=[GATEWAY]),
            "a": device("a", identifiers=[NODES[0]]),
            "b": device("b", identifiers=[NODES[1]]),
        }
    )
    changed = device_link.link_nodes_to_gateway(
        registry, gateway_connection=GATEWAY, node_identifiers=NODES
    )
    assert changed == 2
    assert registry.devices["a"].via_device_id == "gw"
    assert registry.devices["b"].via_device_id == "gw"


def test_does_nothing_until_the_gateway_device_exists():
    registry = FakeRegistry({"a": device("a", identifiers=[NODES[0]])})
    assert device_link.link_nodes_to_gateway(
        registry, gateway_connection=GATEWAY, node_identifiers=NODES
    ) == 0
    assert registry.updates == []


def test_skips_nodes_without_a_device_yet_and_links_them_later():
    registry = FakeRegistry(
        {"gw": device("gw", connections=[GATEWAY]), "a": device("a", identifiers=[NODES[0]])}
    )
    assert device_link.link_nodes_to_gateway(
        registry, gateway_connection=GATEWAY, node_identifiers=NODES
    ) == 1
    registry.devices["b"] = device("b", identifiers=[NODES[1]])
    assert device_link.link_nodes_to_gateway(
        registry, gateway_connection=GATEWAY, node_identifiers=NODES
    ) == 1
    assert registry.devices["b"].via_device_id == "gw"


def test_is_idempotent_and_does_not_rewrite_existing_links():
    registry = FakeRegistry(
        {
            "gw": device("gw", connections=[GATEWAY]),
            "a": device("a", identifiers=[NODES[0]], via="gw"),
        }
    )
    assert device_link.link_nodes_to_gateway(
        registry, gateway_connection=GATEWAY, node_identifiers=NODES
    ) == 0
    assert registry.updates == []

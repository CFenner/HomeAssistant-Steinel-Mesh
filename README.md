# HomeAssistant-Steinel-Mesh

[![Discord](https://img.shields.io/discord/1180135968662102136)](https://discord.gg/QGEGytnyY5)

Home Assistant integration for Steinel Bluetooth Mesh luminaires and sensors (for example L 810 SC, L 810 C and IS 180).

Home Assistant cannot talk to a Bluetooth Mesh network directly. This integration therefore talks to an **ESP32-C3 gateway** running the firmware from
[steinel-mesh-esphome-gateway](https://github.com/CFenner/steinel-mesh-esphome-gateway), which joins your Steinel network and exposes every device over a small local HTTP API. The integration is the Home Assistant side of that gateway.

> **Status: experimental.** Verified on a real network (IS 180, two L 810 SC and one L 810 C): setup, reading state, switching lamps, automatic mode and illuminance work. A motion detection (non-zero motion value) has not been observed yet, so the motion decoding is unconfirmed.

## Requirements

- An ESP32-C3 gateway running the firmware above, with your Steinel network imported (see the firmware's README).
- The gateway's address and its web login (username `admin` and the administrator password).

## Tested devices

| Device | Type | Status |
|---|---|---|
| Steinel L 810 SC | Luminaire | Tested: switching, brightness, automatic mode, illuminance |
| Steinel L 810 C | Luminaire | Tested: switching, brightness, automatic mode, illuminance |
| Steinel IS 180 | Sensor | Tested: state and illuminance; motion detection not yet observed |

Have you used the integration with another Steinel Bluetooth Mesh device? Please open an issue or pull request to add it to this list.

## Installation

**HACS:** add this repository as a custom repository (category *Integration*), install **Steinel Mesh**, and restart Home Assistant.

**Manual:** copy `custom_components/steinel_mesh` into `<config>/custom_components/` and restart Home Assistant.

Then add the integration under *Settings → Devices & services → Add integration → Steinel Mesh* and enter the gateway's host, username and password.

## Entities

Each device of the network appears as a Home Assistant device. When the gateway reports its MAC address (firmware with the `/api/nodes` `gateway` field) and Home Assistant already knows the gateway's ESPHome device, the devices are shown as *connected via* that ESPHome device. The device page shows the manufacturer and the product ID as model ID. Each device has:

| Entity | For devices with | Notes |
|---|---|---|
| Light | a light output | on/off and brightness |
| Automatic mode (switch) | Light Control | on: the lamp follows its own sensors; off: manual. A manual on/off or brightness command switches automatic mode off first. |
| Twilight threshold (number, configuration) | a sensor and Light Control | ambient light level in lx below which automatic mode switches the lamp on; 1–1500 lx |
| Illuminance | an illuminance sensor | in lx |
| Company ID | every device | diagnostic; known from the imported network, shown even while the device does not answer |
| Firmware revision, Hardware revision | devices that report them | diagnostic; the gateway asks each device once after it starts, and the values also appear as the device's software and hardware version. Devices that do not provide them show nothing |
| Motion / Presence | a motion or presence property | decoding of these properties is unverified until seen on real devices |
| Mesh connection | every device | diagnostic; off when the gateway gets no answers |
| Sensor `0x....` | any other sensor property | diagnostic, disabled by default; shows the raw bytes |

Devices are read about every 20 seconds by the gateway and fetched by Home Assistant every 10 seconds, so state can lag a command by a few seconds.

## Gateway API

The integration uses the gateway's HTTP API with Digest authentication:

- `GET /api/nodes` returns the devices with their models and live state.
- `POST /api/nodes/<address>?on=1&brightness=40&auto=0&threshold=25` queues a command. `on` and `auto` accept `0`/`1`; `brightness` is 0–100; `threshold` is the twilight threshold in lx (1–1500). Automatic mode (`auto=1`) cannot be combined with `on` or `brightness`.

## Development

```
python3 -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```

The tests cover the API client against a mock gateway that enforces the same Digest login as the real device. They do not need Home Assistant.

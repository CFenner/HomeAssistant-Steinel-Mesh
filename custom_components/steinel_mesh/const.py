"""Constants for the Steinel Mesh integration."""

from datetime import timedelta

DOMAIN = "steinel_mesh"
PLATFORMS = ["light", "switch", "number", "sensor", "binary_sensor"]

UPDATE_INTERVAL = timedelta(seconds=10)
# A command is queued on the gateway and sent over Bluetooth Mesh a moment
# later, so the confirming state read has to wait a little.
REFRESH_AFTER_COMMAND = 3

# Standard Bluetooth Mesh device properties the gateway decodes for us.
PROPERTY_LUX = "0x004E"
PROPERTY_PRESENCE = "0x004D"
PROPERTY_MOTION = "0x0042"
PROPERTY_FIRMWARE = "0x000E"
PROPERTY_HARDWARE = "0x0010"

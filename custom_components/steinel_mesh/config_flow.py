"""Config flow: host and web credentials of the gateway."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import GatewayAuthError, GatewayClient, GatewayError
from .const import DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

ESPHOME_SERVICE = "._esphomelib._tcp.local."


class SteinelMeshGatewayConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    _discovered_host: str

    async def _async_check_gateway(self, host: str, user_input: dict[str, Any]) -> str | None:
        """Return an error key if the gateway cannot be read with these credentials."""
        client = GatewayClient(
            get_async_client(self.hass),
            host,
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
        )
        try:
            await client.get_nodes()
        except GatewayAuthError:
            return "invalid_auth"
        except GatewayError:
            return "cannot_connect"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST].lower())
            self._abort_if_unique_id_configured()
            error = await self._async_check_gateway(user_input[CONF_HOST], user_input)
            if error is None:
                return self.async_create_entry(
                    title=f"Steinel Mesh ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """A gateway announced itself as an ESPHome device."""
        host = str(discovery_info.ip_address)
        name = discovery_info.name.removesuffix(ESPHOME_SERVICE)
        # The announced name contains the MAC, so it survives an IP change.
        await self.async_set_unique_id(name.lower())
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        # A gateway that was added by hand is identified by its host.
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST, "").lower() in (host, discovery_info.hostname.lower().rstrip(".")):
                return self.async_abort(reason="already_configured")
        self._discovered_host = host
        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the web login of a discovered gateway."""
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._async_check_gateway(self._discovered_host, user_input)
            if error is None:
                return self.async_create_entry(
                    title=f"Steinel Mesh ({self._discovered_host})",
                    data={CONF_HOST: self._discovered_host, **user_input},
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=STEP_CREDENTIALS_SCHEMA,
            description_placeholders={"host": self._discovered_host},
            errors=errors,
        )

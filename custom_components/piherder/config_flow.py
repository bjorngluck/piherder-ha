"""Config flow: base URL + token + TLS verify + poll interval."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import PiHerderApiError, fetch_health, normalize_base_url
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

STEP_USER = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
        ),
    }
)


async def _validate(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    origin = normalize_base_url(data[CONF_URL])
    token = (data[CONF_TOKEN] or "").strip()
    if not token.startswith("ph_"):
        raise PiHerderApiError(400, "Token must start with ph_")
    verify = bool(data.get(CONF_VERIFY_SSL, True))
    session = async_get_clientsession(hass, verify_ssl=verify)
    health = await fetch_health(session, origin, token, verify_ssl=verify)
    scopes = health.get("scopes") or []
    if "read" not in scopes:
        raise PiHerderApiError(403, "Token is missing scope read")
    return {**data, CONF_URL: origin, CONF_TOKEN: token}


class PiHerderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = await _validate(self.hass, user_input)
            except PiHerderApiError as exc:
                if exc.status in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(data[CONF_URL])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="PiHerder", data=data)

        return self.async_show_form(step_id="user", data_schema=STEP_USER, errors=errors)

"""Home Assistant services. Cards call these. The token stays on the config entry."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import JOB_TYPES, PiHerderApiError, set_features, trigger_job
from .const import CONF_VERIFY_SSL, DOMAIN
from .coordinator import PiHerderCoordinator

_REGISTERED = f"{DOMAIN}_services"


def _coordinator(hass: HomeAssistant) -> PiHerderCoordinator:
    store = hass.data.get(DOMAIN) or {}
    for key, val in store.items():
        if str(key).startswith("_"):
            continue
        if isinstance(val, PiHerderCoordinator):
            return val
    raise HomeAssistantError("PiHerder is not set up")


def async_register_services(hass: HomeAssistant) -> None:
    if hass.data.get(_REGISTERED):
        return
    hass.data[_REGISTERED] = True

    async def _trigger(call: ServiceCall) -> None:
        coord = _coordinator(hass)
        verify = bool(coord.entry.data.get(CONF_VERIFY_SSL, True))
        session = async_get_clientsession(hass, verify_ssl=verify)
        try:
            result = await trigger_job(
                session,
                coord.origin,
                coord.entry.data["token"],
                int(call.data["server_id"]),
                str(call.data["job_type"]),
                verify_ssl=verify,
            )
        except PiHerderApiError as exc:
            raise HomeAssistantError(exc.message) from exc
        if result.get("already_active"):
            job = result.get("job") or {}
            kind = job.get("job_type") or call.data["job_type"]
            raise HomeAssistantError(f"{kind} already active")
        await coord.async_request_refresh()

    async def _features(call: ServiceCall) -> None:
        coord = _coordinator(hass)
        verify = bool(coord.entry.data.get(CONF_VERIFY_SSL, True))
        session = async_get_clientsession(hass, verify_ssl=verify)
        body = {
            key: bool(call.data[key])
            for key in ("backup", "os_patch", "docker")
            if key in call.data
        }
        try:
            await set_features(
                session,
                coord.origin,
                coord.entry.data["token"],
                int(call.data["server_id"]),
                body,
                verify_ssl=verify,
            )
        except PiHerderApiError as exc:
            raise HomeAssistantError(exc.message) from exc
        await coord.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        "trigger_job",
        _trigger,
        schema=vol.Schema(
            {
                vol.Required("server_id"): vol.Coerce(int),
                vol.Required("job_type"): vol.In(JOB_TYPES),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "set_features",
        _features,
        schema=vol.Schema(
            {
                vol.Required("server_id"): vol.Coerce(int),
                vol.Optional("backup"): bool,
                vol.Optional("os_patch"): bool,
                vol.Optional("docker"): bool,
            }
        ),
    )

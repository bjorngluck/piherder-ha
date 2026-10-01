"""Home Assistant services. Cards call these. The token stays on the config entry."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import (
    JOB_TYPES,
    PiHerderApiError,
    delete_file,
    list_files,
    mkdir_file,
    read_file,
    rename_file,
    set_features,
    start_move,
    trigger_job,
    write_file,
)
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
        kind = str(call.data["job_type"])
        if kind == "docker_stack_stop" and call.data.get("confirm") is not True:
            raise HomeAssistantError("Confirm project stop")
        try:
            result = await trigger_job(
                session,
                coord.origin,
                coord.entry.data["token"],
                int(call.data["server_id"]),
                kind,
                source_filter=call.data.get("source_filter"),
                service=call.data.get("service"),
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

    async def _move(call: ServiceCall) -> dict:
        if call.data.get("confirm") is not True:
            raise HomeAssistantError("Confirm Move")
        coord = _coordinator(hass)
        verify = bool(coord.entry.data.get(CONF_VERIFY_SSL, True))
        session = async_get_clientsession(hass, verify_ssl=verify)
        try:
            result = await start_move(
                session,
                coord.origin,
                coord.entry.data["token"],
                int(call.data["server_id"]),
                int(call.data["dest_server_id"]),
                str(call.data["project"]),
                confirm=True,
                verify_ssl=verify,
            )
        except PiHerderApiError as exc:
            raise HomeAssistantError(exc.message) from exc
        if result.get("already_active"):
            raise HomeAssistantError("Move already active")
        await coord.async_request_refresh()
        return result

    async def _files(call: ServiceCall) -> dict:
        coord = _coordinator(hass)
        verify = bool(coord.entry.data.get(CONF_VERIFY_SSL, True))
        session = async_get_clientsession(hass, verify_ssl=verify)
        action = call.service
        token = coord.entry.data["token"]
        server_id = int(call.data["server_id"])
        path = call.data.get("path") or ""
        try:
            if action == "list_files":
                result = await list_files(
                    session, coord.origin, token, server_id, path, verify_ssl=verify
                )
            elif action == "read_file":
                result = await read_file(
                    session, coord.origin, token, server_id, str(path), verify_ssl=verify
                )
            elif action == "write_file":
                result = await write_file(
                    session,
                    coord.origin,
                    token,
                    server_id,
                    path,
                    str(call.data["name"]),
                    str(call.data.get("text") or ""),
                    verify_ssl=verify,
                )
            elif action == "mkdir":
                result = await mkdir_file(
                    session,
                    coord.origin,
                    token,
                    server_id,
                    path,
                    str(call.data["name"]),
                    verify_ssl=verify,
                )
            elif action == "rename_file":
                result = await rename_file(
                    session,
                    coord.origin,
                    token,
                    server_id,
                    path,
                    str(call.data["src"]),
                    str(call.data["dest"]),
                    verify_ssl=verify,
                )
            elif action == "delete_file":
                if call.data.get("confirm") is not True:
                    raise HomeAssistantError("Confirm delete")
                result = await delete_file(
                    session,
                    coord.origin,
                    token,
                    server_id,
                    str(path),
                    confirm=True,
                    verify_ssl=verify,
                )
            else:
                raise HomeAssistantError("Unknown files action")
        except PiHerderApiError as exc:
            raise HomeAssistantError(exc.message) from exc
        return result

    hass.services.async_register(
        DOMAIN,
        "trigger_job",
        _trigger,
        schema=vol.Schema(
            {
                vol.Required("server_id"): vol.Coerce(int),
                vol.Required("job_type"): vol.In(JOB_TYPES),
                vol.Optional("source_filter"): str,
                vol.Optional("service"): str,
                vol.Optional("confirm"): bool,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "start_move",
        _move,
        schema=vol.Schema(
            {
                vol.Required("server_id"): vol.Coerce(int),
                vol.Required("dest_server_id"): vol.Coerce(int),
                vol.Required("project"): str,
                vol.Required("confirm"): bool,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    file_path = {
        vol.Required("server_id"): vol.Coerce(int),
        vol.Optional("path"): str,
    }
    for name, extra in (
        ("list_files", {}),
        ("read_file", {}),
        ("write_file", {vol.Required("name"): str, vol.Optional("text"): str}),
        ("mkdir", {vol.Required("name"): str}),
        ("rename_file", {vol.Required("src"): str, vol.Required("dest"): str}),
        ("delete_file", {vol.Required("confirm"): bool}),
    ):
        hass.services.async_register(
            DOMAIN,
            name,
            _files,
            schema=vol.Schema({**file_path, **extra}),
            supports_response=SupportsResponse.OPTIONAL,
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

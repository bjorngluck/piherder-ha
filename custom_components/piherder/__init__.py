"""PiHerder Home Assistant integration — Slice 1 read-only fleet remote."""
from __future__ import annotations

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components import frontend, websocket_api
import voluptuous as vol

from .const import DOMAIN
from .coordinator import PiHerderCoordinator

PLATFORMS = [Platform.SENSOR]
_WWW_FLAG = f"{DOMAIN}_www"


@websocket_api.websocket_command({vol.Required("type"): "piherder/snapshot"})
@websocket_api.async_response
async def ws_snapshot(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    store = hass.data.get(DOMAIN) or {}
    origin = None
    data = None
    for key, val in store.items():
        if key.startswith("_") or not hasattr(val, "data"):
            continue
        data = val.data
        origin = getattr(val, "origin", None)
        break
    connection.send_result(msg["id"], {"origin": origin, "data": data or {}})


async def _async_register_frontend(hass: HomeAssistant) -> None:
    if hass.data.get(_WWW_FLAG):
        return
    hass.data[_WWW_FLAG] = True
    www = Path(__file__).parent / "www"
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig("/piherder-card", str(www), False)]
        )
    except Exception:
        hass.http.register_static_path("/piherder-card", str(www), False)
    frontend.add_extra_js_url(hass, "/piherder-card/piherder-dashboard-card.js?v=0.2.0")
    websocket_api.async_register_command(hass, ws_snapshot)


def _purge_fake_link_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Drop leftover press-here entities and nested shortcut devices."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    ereg = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(ereg, entry.entry_id):
        uid = ent.unique_id or ""
        if uid.endswith("_open") or uid.endswith("_url") or uid.endswith("_audit") or uid.endswith("_docker"):
            ereg.async_remove(ent.entity_id)

    dreg = dr.async_get(hass)
    suffixes = ("_docker", "_alerts", "_audit", "_backup")
    for device in list(dr.async_entries_for_config_entry(dreg, entry.entry_id)):
        for domain, ident in device.identifiers:
            if domain == DOMAIN and ident.endswith(suffixes):
                dreg.async_remove_device(device.id)
                break


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await _async_register_frontend(hass)
    _purge_fake_link_entities(hass, entry)
    coord = PiHerderCoordinator(hass, entry)
    await coord.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coord
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload

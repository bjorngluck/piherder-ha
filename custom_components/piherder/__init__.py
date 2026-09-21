"""PiHerder Home Assistant integration — Slice 1 read-only fleet remote."""
from __future__ import annotations

from pathlib import Path

from aiohttp import web
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components import frontend, http, websocket_api
import voluptuous as vol

from .const import DOMAIN
from .coordinator import PiHerderCoordinator

PLATFORMS = [Platform.SENSOR]
_WWW_FLAG = f"{DOMAIN}_www"
_CARD_URL = "/local/piherder-dashboard-card.js?v=0.2.3"


class PiHerderCardView(http.HomeAssistantView):
    """Serve the Lovelace module without auth (same origin as extra_js)."""

    url = "/api/piherder/piherder-dashboard-card.js"
    name = "api:piherder:card"
    requires_auth = False

    async def get(self, request):
        path = Path(__file__).parent / "www" / "piherder-dashboard-card.js"
        return web.FileResponse(
            path,
            headers={
                "Content-Type": "application/javascript; charset=utf-8",
                "Cache-Control": "no-cache",
            },
        )


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


async def _async_register_lovelace_resource(hass: HomeAssistant, url: str) -> None:
    try:
        ll = hass.data.get("lovelace")
        resources = getattr(ll, "resources", None) if ll is not None else None
        if resources is None:
            return
        if getattr(resources, "loaded", True) is False:
            await resources.async_load()
        items = resources.async_items() if hasattr(resources, "async_items") else []
        stem = url.split("?")[0]
        for item in items:
            if str(item.get("url") or "").split("?")[0] == stem:
                return
        try:
            await resources.async_create_item({"resource_type": "module", "url": url})
        except Exception:
            await resources.async_create_item({"res_type": "module", "url": url})
    except Exception:
        return


async def _async_register_frontend(hass: HomeAssistant) -> None:
    if hass.data.get(_WWW_FLAG):
        return
    hass.data[_WWW_FLAG] = True
    hass.http.register_view(PiHerderCardView)
    src = Path(__file__).parent / "www" / "piherder-dashboard-card.js"
    dest_dir = Path(hass.config.path("www"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "piherder-dashboard-card.js"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    hass.data.setdefault("frontend_extra_module_url", set()).add(_CARD_URL)
    try:
        frontend.add_extra_js_url(hass, _CARD_URL)
    except Exception:
        pass
    websocket_api.async_register_command(hass, ws_snapshot)
    await _async_register_lovelace_resource(hass, _CARD_URL)


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

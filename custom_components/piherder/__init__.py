"""PiHerder Home Assistant integration — Slice 1 read-only fleet remote."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PiHerderCoordinator

PLATFORMS = [Platform.SENSOR]


def _purge_fake_link_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Drop leftover Jobs/Audit/Open-* entities from 0.1.2–0.1.4."""
    from homeassistant.helpers import entity_registry as er

    reg = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(reg, entry.entry_id):
        uid = ent.unique_id or ""
        if uid.endswith("_open") or uid.endswith("_url"):
            reg.async_remove(ent.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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

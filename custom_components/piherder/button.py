"""Open-in-PiHerder buttons — not sensors, so HAOS does not show a history trend."""
from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INTEGRATION_VERSION
from .coordinator import PiHerderCoordinator
from .helpers import device_model, fleet_urls, hardware_label, host_urls, os_display

HOST_LINKS = (
    ("open", "Open host", "mdi:server", "open_url", None),
    ("features", "Open features", "mdi:toggle-switch", "features_url", None),
    ("docker", "Open Docker", "mdi:docker", "docker_url", "docker"),
    ("backup", "Open backups", "mdi:backup-restore", "backup_url", "backup"),
    ("services", "Open services", "mdi:heart-pulse", "services_url", None),
    ("jobs", "Open jobs", "mdi:clipboard-text-clock", "jobs_url", None),
    ("audit", "Open audit", "mdi:shield-search", "audit_url", None),
    ("alerts", "Open alerts", "mdi:alert", "alerts_url", None),
)

FLEET_LINKS = (
    ("jobs", "Open jobs", "mdi:clipboard-text-clock", "jobs_url"),
    ("audit", "Open audit", "mdi:shield-search", "audit_url"),
    ("alerts", "Open alerts", "mdi:alert", "alerts_url"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coord: PiHerderCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[int] = set()
    fleet = [
        PiHerderUrlButton(coord, entry, kind, name, icon, key)
        for kind, name, icon, key in FLEET_LINKS
    ]
    async_add_entities(fleet)

    def _discover() -> None:
        rows = (coord.data or {}).get("servers") or []
        fresh = {int(s["id"]) for s in rows if s.get("id") is not None}
        new_ids = fresh - known
        if not new_ids:
            return
        ents: list[ButtonEntity] = []
        for sid in sorted(new_ids):
            known.add(sid)
            for kind, name, icon, key, feat in HOST_LINKS:
                ents.append(
                    PiHerderHostUrlButton(coord, entry, sid, kind, name, icon, key, feat)
                )
        async_add_entities(ents)

    _discover()
    entry.async_on_unload(coord.async_add_listener(_discover))


class PiHerderUrlButton(CoordinatorEntity[PiHerderCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, kind, name, icon, key) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{kind}_open"

    @property
    def device_info(self) -> DeviceInfo:
        summary = (self.coordinator.data or {}).get("summary") or {}
        version = summary.get("version")
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_fleet")},
            name="PiHerder fleet",
            manufacturer="PiHerder",
            model="Fleet",
            sw_version=str(version) if version else None,
            hw_version=f"plugin {INTEGRATION_VERSION}",
            configuration_url=self.coordinator.origin,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        urls = fleet_urls(self.coordinator.origin)
        return {"url": urls[self._key]}

    async def async_press(self) -> None:
        url = (self.extra_state_attributes or {}).get("url")
        if url:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": self.name,
                    "message": f"[Open in PiHerder]({url})",
                    "notification_id": self.unique_id,
                },
                blocking=False,
            )


class PiHerderHostUrlButton(CoordinatorEntity[PiHerderCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, server_id, kind, name, icon, key, feat) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._server_id = server_id
        self._key = key
        self._feat = feat
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_{kind}_open"

    def _row(self) -> dict[str, Any]:
        for row in self.coordinator.data.get("servers") or []:
            if int(row.get("id") or 0) == self._server_id:
                return row
        return {}

    @property
    def available(self) -> bool:
        if not self._feat:
            return True
        flags = (self._row().get("features") or {})
        return bool(flags.get(self._feat))

    @property
    def device_info(self) -> DeviceInfo:
        row = self._row()
        urls = host_urls(self.coordinator.origin, self._server_id)
        hw = hardware_label(row)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_host_{self._server_id}")},
            name=row.get("name") or f"Host {self._server_id}",
            manufacturer="PiHerder",
            model=device_model(row),
            hw_version=hw,
            configuration_url=urls["open_url"],
            via_device=(DOMAIN, f"{self._entry.entry_id}_fleet"),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        urls = host_urls(self.coordinator.origin, self._server_id)
        return {"url": urls[self._key]}

    async def async_press(self) -> None:
        url = (self.extra_state_attributes or {}).get("url")
        if url:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": self.name,
                    "message": f"[Open in PiHerder]({url})",
                    "notification_id": self.unique_id,
                },
                blocking=False,
            )

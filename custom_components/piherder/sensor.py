"""Fleet and per-host sensors (Slice 1)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PiHerderCoordinator

FLEET_SENSORS = (
    ("hosts", "Hosts", "mdi:server-network"),
    ("os_updates", "OS updates", "mdi:package-up"),
    ("container_updates", "Container updates", "mdi:docker"),
    ("reboot_pending", "Reboot pending", "mdi:restart-alert"),
    ("jobs_running", "Jobs running", "mdi:progress-clock"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coord: PiHerderCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        PiHerderFleetSensor(coord, entry, key, name, icon) for key, name, icon in FLEET_SENSORS
    ]
    entities.append(PiHerderMoveSensor(coord, entry))
    entities.append(PiHerderHerderUpSensor(coord, entry))
    seen = {int(s["id"]) for s in coord.data.get("servers") or [] if s.get("id") is not None}
    for sid in seen:
        entities.extend(
            [
                PiHerderHostOsSensor(coord, entry, sid),
                PiHerderHostLastSeenSensor(coord, entry, sid),
                PiHerderHostRebootSensor(coord, entry, sid),
                PiHerderHostBackupSensor(coord, entry, sid),
            ]
        )
    async_add_entities(entities)


def _host(coord: PiHerderCoordinator, server_id: int) -> dict[str, Any] | None:
    for row in coord.data.get("servers") or []:
        if int(row.get("id") or 0) == server_id:
            return row
    return None


class _FleetBase(CoordinatorEntity[PiHerderCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PiHerderCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_fleet")},
            name="PiHerder fleet",
            manufacturer="PiHerder",
            configuration_url=coordinator.origin,
        )


class PiHerderFleetSensor(_FleetBase):
    def __init__(self, coordinator, entry, key: str, name: str, icon: str) -> None:
        super().__init__(coordinator, entry)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        summary = (self.coordinator.data or {}).get("summary") or {}
        return summary.get(self._key)


class PiHerderMoveSensor(_FleetBase):
    _attr_name = "Move in progress"
    _attr_icon = "mdi:swap-horizontal"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_move_running"

    @property
    def native_value(self):
        summary = (self.coordinator.data or {}).get("summary") or {}
        return "on" if summary.get("move_running") else "off"


class PiHerderHerderUpSensor(_FleetBase):
    _attr_name = "Herder"
    _attr_icon = "mdi:heart-pulse"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_herder_up"

    @property
    def native_value(self):
        health = (self.coordinator.data or {}).get("health") or {}
        return "up" if health.get("ok") else "down"


class _HostBase(CoordinatorEntity[PiHerderCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PiHerderCoordinator, entry: ConfigEntry, server_id: int) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._server_id = server_id
        row = _host(coordinator, server_id) or {}
        name = row.get("name") or f"Host {server_id}"
        origin = coordinator.origin
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_host_{server_id}")},
            name=name,
            manufacturer="PiHerder",
            model=str(row.get("os_type") or "host"),
            configuration_url=f"{origin}/servers/{server_id}",
            via_device=(DOMAIN, f"{entry.entry_id}_fleet"),
        )

    def _row(self) -> dict[str, Any]:
        return _host(self.coordinator, self._server_id) or {}


class PiHerderHostOsSensor(_HostBase):
    _attr_name = "OS type"
    _attr_icon = "mdi:linux"

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_os"

    @property
    def native_value(self):
        return self._row().get("os_type")


class PiHerderHostLastSeenSensor(_HostBase):
    _attr_name = "Last seen"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_last_seen"

    @property
    def native_value(self):
        raw = self._row().get("last_seen")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None


class PiHerderHostRebootSensor(_HostBase):
    _attr_name = "Reboot pending"
    _attr_icon = "mdi:restart-alert"

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_reboot"

    @property
    def native_value(self):
        return "yes" if self._row().get("reboot_pending") else "no"


class PiHerderHostBackupSensor(_HostBase):
    _attr_name = "Last backup"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:backup-restore"

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_backup"

    @property
    def native_value(self):
        raw = self._row().get("last_backup_at")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None

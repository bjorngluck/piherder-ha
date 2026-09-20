"""Fleet and per-host sensors (Slice 1)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INTEGRATION_VERSION
from .coordinator import PiHerderCoordinator
from .helpers import (
    alert_state,
    backup_state,
    device_model,
    feature_flags,
    features_label,
    hardware_label,
    host_urls,
    os_display,
    parse_utc,
)

FLEET_SENSORS = (
    ("hosts", "Hosts", "mdi:server-network"),
    ("os_updates", "OS updates", "mdi:package-up"),
    ("container_updates", "Container updates", "mdi:docker"),
    ("reboot_pending", "Reboot pending", "mdi:restart-alert"),
    ("jobs_running", "Jobs running", "mdi:progress-clock"),
    ("alerts_open", "Alerts", "mdi:alert"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coord: PiHerderCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[int] = set()

    fleet: list[SensorEntity] = [
        PiHerderFleetSensor(coord, entry, key, name, icon) for key, name, icon in FLEET_SENSORS
    ]
    fleet.extend(
        [
            PiHerderMoveSensor(coord, entry),
            PiHerderHerderUpSensor(coord, entry),
            PiHerderVersionSensor(coord, entry),
            PiHerderPluginSensor(coord, entry),
        ]
    )
    async_add_entities(fleet)

    known_sc: set[tuple[int, str]] = set()

    def _host_bundle(sid: int) -> list[SensorEntity]:
        return [
            PiHerderHostOsSensor(coord, entry, sid),
            PiHerderHostFeaturesSensor(coord, entry, sid),
            PiHerderHostLastSeenSensor(coord, entry, sid),
            PiHerderHostRebootSensor(coord, entry, sid),
        ]

    def _shortcut_bundle(sid: int, row: dict) -> list[SensorEntity]:
        flags = feature_flags(row)
        out: list[SensorEntity] = [
            PiHerderHostAlertSensor(coord, entry, sid),
            PiHerderHostAuditSensor(coord, entry, sid),
        ]
        if flags.get("docker"):
            out.append(PiHerderHostDockerSensor(coord, entry, sid))
        if flags.get("backup"):
            out.append(PiHerderHostBackupSensor(coord, entry, sid))
        return out

    def _discover() -> None:
        rows = (coord.data or {}).get("servers") or []
        entities: list[SensorEntity] = []
        for row in rows:
            if row.get("id") is None:
                continue
            sid = int(row["id"])
            if sid not in known:
                known.add(sid)
                entities.extend(_host_bundle(sid))
            for ent in _shortcut_bundle(sid, row):
                kind = getattr(ent, "_shortcut", "")
                key = (sid, kind)
                if key in known_sc:
                    continue
                known_sc.add(key)
                entities.append(ent)
        if entities:
            async_add_entities(entities)

    _discover()
    entry.async_on_unload(coord.async_add_listener(_discover))


def _host(coord: PiHerderCoordinator, server_id: int) -> dict[str, Any] | None:
    for row in coord.data.get("servers") or []:
        if int(row.get("id") or 0) == server_id:
            return row
    return None


class _FleetBase(CoordinatorEntity[PiHerderCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:server-network"

    def __init__(self, coordinator: PiHerderCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

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


class PiHerderVersionSensor(_FleetBase):
    _attr_name = "Version"
    _attr_icon = "mdi:tag-outline"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_version"

    @property
    def native_value(self):
        summary = (self.coordinator.data or {}).get("summary") or {}
        return summary.get("version")


class PiHerderPluginSensor(_FleetBase):
    """HACS/custom component version — confirms the files HA actually loaded."""

    _attr_name = "Plugin"
    _attr_icon = "mdi:puzzle-outline"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_plugin"

    @property
    def native_value(self):
        return INTEGRATION_VERSION


class _HostBase(CoordinatorEntity[PiHerderCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:server"

    def __init__(self, coordinator: PiHerderCoordinator, entry: ConfigEntry, server_id: int) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._server_id = server_id

    _shortcut: str = ""

    def _row(self) -> dict[str, Any]:
        return _host(self.coordinator, self._server_id) or {}

    def _shortcut_device(self, kind: str, label: str, url_key: str) -> DeviceInfo:
        row = self._row()
        urls = host_urls(self.coordinator.origin, self._server_id)
        host_name = row.get("name") or f"Host {self._server_id}"
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_host_{self._server_id}_{kind}")},
            name=f"{host_name} · {label}",
            manufacturer="PiHerder",
            model=label,
            configuration_url=urls[url_key],
            via_device=(DOMAIN, f"{self._entry.entry_id}_host_{self._server_id}"),
        )

    @property
    def device_info(self) -> DeviceInfo:
        row = self._row()
        name = row.get("name") or f"Host {self._server_id}"
        urls = host_urls(self.coordinator.origin, self._server_id)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_host_{self._server_id}")},
            name=name,
            manufacturer="PiHerder",
            model=device_model(row),
            hw_version=hardware_label(row),
            configuration_url=urls["open_url"],
            via_device=(DOMAIN, f"{self._entry.entry_id}_fleet"),
        )


class PiHerderHostOsSensor(_HostBase):
    _attr_name = "OS type"
    _attr_icon = "mdi:linux"

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_os"

    @property
    def native_value(self):
        return os_display(self._row())


class PiHerderHostFeaturesSensor(_HostBase):
    _attr_name = "Features"
    _attr_icon = "mdi:toggle-switch"

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_features"

    @property
    def native_value(self):
        return features_label(self._row())

    @property
    def extra_state_attributes(self):
        flags = feature_flags(self._row())
        urls = host_urls(self.coordinator.origin, self._server_id)
        return {**flags, "piherder": urls["open_url"]}


class PiHerderHostLastSeenSensor(_HostBase):
    _attr_name = "Last seen"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_last_seen"

    @property
    def native_value(self):
        raw = self._row().get("last_seen")
        if not raw:
            return None
        return parse_utc(raw)


class PiHerderHostAlertSensor(_HostBase):
    _shortcut = "alerts"
    _attr_name = "Alert"
    _attr_icon = "mdi:alert"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self) -> DeviceInfo:
        return self._shortcut_device("alerts", "Alerts", "alerts_url")

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_alert"

    @property
    def native_value(self):
        return alert_state(self._row())

    @property
    def extra_state_attributes(self):
        row = self._row()
        urls = host_urls(self.coordinator.origin, self._server_id)
        return {
            "alerts_open": int(row.get("alerts_open") or 0),
            "severity": row.get("alert_severity"),
            "alerts": row.get("alerts") or [],
        }

    @property
    def icon(self):
        return "mdi:alert" if int(self._row().get("alerts_open") or 0) else "mdi:alert-outline"


class PiHerderHostRebootSensor(_HostBase):
    _attr_name = "Reboot pending"
    _attr_icon = "mdi:restart-alert"

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_reboot"

    @property
    def native_value(self):
        return "yes" if self._row().get("reboot_pending") else "no"


class PiHerderHostDockerSensor(_HostBase):
    _shortcut = "docker"
    _attr_name = "Updates"
    _attr_icon = "mdi:docker"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_docker"

    @property
    def device_info(self) -> DeviceInfo:
        return self._shortcut_device("docker", "Docker", "docker_url")

    @property
    def native_value(self):
        return int(self._row().get("container_updates_count") or 0)


class PiHerderHostAuditSensor(_HostBase):
    _shortcut = "audit"
    _attr_name = "Log"
    _attr_icon = "mdi:shield-search"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_visible_default = False

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_audit"

    @property
    def device_info(self) -> DeviceInfo:
        return self._shortcut_device("audit", "Audit", "audit_url")

    @property
    def native_value(self):
        return None


class PiHerderHostBackupSensor(_HostBase):
    _shortcut = "backup"
    _attr_name = "Last backup"
    _attr_icon = "mdi:backup-restore"

    @property
    def device_info(self) -> DeviceInfo:
        return self._shortcut_device("backup", "Backups", "backup_url")

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_backup"

    @property
    def device_class(self):
        if parse_utc(self._row().get("last_backup_at")):
            return SensorDeviceClass.TIMESTAMP
        return None

    @property
    def native_value(self):
        return backup_state(self._row())




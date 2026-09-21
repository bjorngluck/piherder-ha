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
    container_slug,
    disk_used_percent,
    host_urls,
    os_display,
    parse_utc,
    shortcut_link_attrs,
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
    known_containers: set[str] = set()
    known_services: set[int] = set()

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

    def _host_bundle(sid: int) -> list[SensorEntity]:
        return [
            PiHerderHostOsSensor(coord, entry, sid),
            PiHerderHostFeaturesSensor(coord, entry, sid),
            PiHerderHostAlertSensor(coord, entry, sid),
            PiHerderHostLastSeenSensor(coord, entry, sid),
            PiHerderHostRebootSensor(coord, entry, sid),
            PiHerderHostBackupSensor(coord, entry, sid),
            PiHerderHostDiskSensor(coord, entry, sid),
        ]

    def _discover() -> None:
        rows = (coord.data or {}).get("servers") or []
        fresh = {int(s["id"]) for s in rows if s.get("id") is not None}
        new_ids = fresh - known
        if not new_ids:
            return
        entities: list[SensorEntity] = []
        for sid in sorted(new_ids):
            known.add(sid)
            entities.extend(_host_bundle(sid))
        async_add_entities(entities)

    def _discover_snapshots() -> None:
        entities: list[SensorEntity] = []
        for host in (coord.data or {}).get("inventory") or []:
            sid = int(host.get("server_id") or 0)
            if sid <= 0:
                continue
            for container in host.get("containers") or []:
                name = (container.get("name") or "").strip()
                if not name:
                    continue
                key = f"{sid}:{name}"
                if key in known_containers:
                    continue
                known_containers.add(key)
                entities.append(PiHerderContainerSensor(coord, entry, sid, name))
        for svc in (coord.data or {}).get("services") or []:
            try:
                bid = int(svc.get("id") or 0)
            except (TypeError, ValueError):
                bid = 0
            if bid <= 0 or bid in known_services:
                continue
            known_services.add(bid)
            sid = int(svc.get("server_id") or 0)
            entities.append(PiHerderServiceSensor(coord, entry, sid, bid))
        if entities:
            async_add_entities(entities)

    def _on_update() -> None:
        _discover()
        _discover_snapshots()

    _on_update()
    entry.async_on_unload(coord.async_add_listener(_on_update))


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

    def _row(self) -> dict[str, Any]:
        return _host(self.coordinator, self._server_id) or {}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return shortcut_link_attrs(
            self.coordinator.origin, self._server_id, self._row()
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
        return {**flags, **super().extra_state_attributes}


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
    _attr_name = "Alert"
    _attr_icon = "mdi:alert"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_alert"

    @property
    def native_value(self):
        return alert_state(self._row())

    @property
    def extra_state_attributes(self):
        row = self._row()
        return {
            **super().extra_state_attributes,
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


class PiHerderHostBackupSensor(_HostBase):
    _attr_name = "Last backup"
    _attr_icon = "mdi:backup-restore"

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


class PiHerderHostDiskSensor(_HostBase):
    """Disk used percent from the stored host-facts snapshot."""

    _attr_name = "Disk"
    _attr_icon = "mdi:harddisk"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, server_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_disk"

    @property
    def native_value(self):
        return disk_used_percent(self._row())

    @property
    def extra_state_attributes(self):
        row = self._row()
        return {
            **super().extra_state_attributes,
            "disk_used_bytes": row.get("disk_used_bytes"),
            "disk_total_bytes": row.get("disk_total_bytes"),
            "os_pretty": row.get("os_pretty"),
            "hardware": row.get("hardware"),
        }


def _inventory_host(coord: PiHerderCoordinator, server_id: int) -> dict[str, Any]:
    for host in (coord.data or {}).get("inventory") or []:
        if int(host.get("server_id") or 0) == server_id:
            return host
    return {}


def _container_row(coord: PiHerderCoordinator, server_id: int, name: str) -> dict[str, Any] | None:
    for container in _inventory_host(coord, server_id).get("containers") or []:
        if (container.get("name") or "") == name:
            return container
    return None


class PiHerderContainerSensor(_HostBase):
    """One container from the last Docker inventory. Status only — no start/stop."""

    def __init__(self, coordinator, entry, server_id: int, name: str) -> None:
        super().__init__(coordinator, entry, server_id)
        self._name = name
        self._attr_name = name
        self._attr_icon = "mdi:docker"
        self._attr_unique_id = f"{entry.entry_id}_host_{server_id}_ctr_{container_slug(name)}"

    def _container(self) -> dict[str, Any] | None:
        return _container_row(self.coordinator, self._server_id, self._name)

    @property
    def available(self) -> bool:
        return super().available and self._container() is not None

    @property
    def native_value(self):
        row = self._container() or {}
        if row.get("running"):
            return "running"
        return row.get("state") or "exited"

    @property
    def extra_state_attributes(self):
        row = self._container() or {}
        return {
            **super().extra_state_attributes,
            "image": row.get("image") or "",
            "uptime": row.get("status") or "",
            "project": row.get("project") or "",
            "service": row.get("service") or "",
        }


def _service_row(coord: PiHerderCoordinator, binding_id: int) -> dict[str, Any] | None:
    for svc in (coord.data or {}).get("services") or []:
        if int(svc.get("id") or 0) == binding_id:
            return svc
    return None


class PiHerderServiceSensor(_HostBase):
    """Monitored service up/down from the stored chip. Not a live probe."""

    def __init__(self, coordinator, entry, server_id: int, binding_id: int) -> None:
        super().__init__(coordinator, entry, server_id)
        self._binding_id = binding_id
        label = (_service_row(coordinator, binding_id) or {}).get("label") or f"Service {binding_id}"
        self._attr_name = label
        self._attr_icon = "mdi:lan-connect"
        self._attr_unique_id = f"{entry.entry_id}_svc_{binding_id}"

    def _svc(self) -> dict[str, Any] | None:
        return _service_row(self.coordinator, self._binding_id)

    @property
    def available(self) -> bool:
        return super().available and self._svc() is not None

    @property
    def native_value(self):
        return (self._svc() or {}).get("state") or "unknown"

    @property
    def extra_state_attributes(self):
        row = self._svc() or {}
        base = super().extra_state_attributes if self._server_id else {}
        return {
            **base,
            "message": row.get("message") or "",
            "scope": row.get("scope") or "",
            "docker_project": row.get("docker_project") or "",
        }

    @property
    def device_info(self) -> DeviceInfo:
        if self._server_id:
            return super().device_info
        summary = (self.coordinator.data or {}).get("summary") or {}
        version = summary.get("version")
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_fleet")},
            name="PiHerder fleet",
            manufacturer="PiHerder",
            model="Fleet",
            sw_version=str(version) if version else None,
            configuration_url=self.coordinator.origin,
        )




"""Pure helpers for HA entities (no Home Assistant imports)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

FEATURE_LABELS = (
    ("backup", "backup"),
    ("os_patch", "OS patch"),
    ("docker", "Docker"),
)

OS_LABELS = {
    "haos": "HAOS",
    "ubuntu": "Ubuntu",
    "debian": "Debian",
    "raspbian": "Raspberry Pi OS",
    "raspberrypi": "Raspberry Pi OS",
}


def feature_flags(row: dict[str, Any] | None) -> dict[str, bool]:
    feat = (row or {}).get("features") or {}
    if not isinstance(feat, dict):
        feat = {}
    return {
        "backup": bool(feat.get("backup")),
        "os_patch": bool(feat.get("os_patch")),
        "docker": bool(feat.get("docker")),
    }


def features_label(row: dict[str, Any] | None) -> str:
    flags = feature_flags(row)
    on = [label for key, label in FEATURE_LABELS if flags.get(key)]
    return ", ".join(on) if on else "none"


def os_display(row: dict[str, Any] | None) -> str:
    raw = row or {}
    if raw.get("os_pretty"):
        return str(raw["os_pretty"])
    if raw.get("os_display"):
        return str(raw["os_display"])
    ot = str(raw.get("os_id") or raw.get("os_type") or "").strip().lower()
    return OS_LABELS.get(ot, ot or "Linux")


def hardware_label(row: dict[str, Any] | None) -> str | None:
    raw = row or {}
    hw = (raw.get("hardware") or "").strip()
    if hw:
        return hw
    arch = (raw.get("arch") or "").strip()
    return arch or None


def device_model(row: dict[str, Any] | None) -> str:
    """HA model = real OS pretty name (Ubuntu / HAOS), not debian hardware."""
    return os_display(row)


def shortcut_link_attrs(origin: str, server_id: int, row: dict[str, Any] | None) -> dict[str, str]:
    """http(s) attrs HA more-info renders as real links (same tab behaviour as Visit)."""
    urls = host_urls(origin, server_id)
    flags = feature_flags(row)
    out = {
        "Alerts": urls["alerts_url"],
        "Audit": urls["audit_url"],
    }
    if flags.get("docker"):
        out["Docker"] = urls["docker_url"]
    if flags.get("backup"):
        out["Backups"] = urls["backup_url"]
    return out


def host_urls(origin: str, server_id: int) -> dict[str, str]:
    base = (origin or "").rstrip("/")
    sid = int(server_id)
    return {
        "open_url": f"{base}/servers/{sid}",
        "features_url": f"{base}/servers/{sid}#host-features",
        "docker_url": f"{base}/servers/{sid}/docker",
        "backup_url": f"{base}/servers/{sid}/backups",
        "services_url": f"{base}/servers/{sid}/services",
        "jobs_url": f"{base}/jobs?server_id={sid}",
        "audit_url": f"{base}/audit?server_id={sid}",
        "alerts_url": f"{base}/notifications?server_id={sid}",
    }


def parse_utc(raw: Any) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def backup_state(row: dict[str, Any] | None) -> datetime | str:
    dt = parse_utc((row or {}).get("last_backup_at"))
    return dt if dt is not None else "never"


def alert_state(row: dict[str, Any] | None) -> str:
    raw = row or {}
    n = int(raw.get("alerts_open") or 0)
    title = (raw.get("alert_title") or "").strip()
    if n <= 0:
        return "none"
    if title and n == 1:
        return title
    if title:
        return f"{title} (+{n - 1})"
    return str(n)


def memory_used_percent(row: dict[str, Any] | None) -> float | None:
    raw = row or {}
    try:
        total = int(raw.get("memory_total_bytes") or 0)
        used = int(raw.get("memory_used_bytes") or 0)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return round(100.0 * used / total, 1)


def cpu_load_value(row: dict[str, Any] | None) -> float | None:
    raw = (row or {}).get("cpu_load")
    if raw is None or raw == "":
        return None
    try:
        return round(float(raw), 2)
    except (TypeError, ValueError):
        return None


# job_type, label, feature key, confirm before call
CARD_JOBS = (
    ("backup", "Backup", "backup", True),
    ("retention", "Retention", "backup", True),
    ("os_update_check", "Check OS", "os", False),
    ("container_update_check", "Check containers", "docker", False),
    ("os_patch", "Patch OS", "os", True),
    ("container_patch", "Patch containers", "docker", True),
    ("host_reboot", "Restart host", "os", True),
)

_FEATURE_FLAG = {"backup": "backup", "os": "os_patch", "docker": "docker"}


def scopes_allow_feature(scopes: list | None, feature: str) -> bool:
    """No feature:* scopes means every feature. Any feature:* limits to those."""
    found = {str(s) for s in (scopes or [])}
    limited = any(s.startswith("feature:") for s in found)
    if not limited:
        return True
    return f"feature:{feature}" in found


def card_actions(scopes: list | None, features: dict | None) -> list[dict[str, Any]]:
    """Confirm buttons a token may show. A read token gets none."""
    found = {str(s) for s in (scopes or [])}
    if "jobs" not in found:
        return []
    flags = feature_flags({"features": features or {}})
    out: list[dict[str, Any]] = []
    for job_type, label, feature, confirm in CARD_JOBS:
        if not scopes_allow_feature(found, feature):
            continue
        flag_key = _FEATURE_FLAG[feature]
        if not flags.get(flag_key):
            continue
        out.append(
            {
                "job_type": job_type,
                "label": label,
                "feature": feature,
                "confirm": confirm,
            }
        )
    return out


def card_toggles(scopes: list | None) -> list[dict[str, str]]:
    """Feature toggles. Shown even when the flag is off, so it can be turned on."""
    found = {str(s) for s in (scopes or [])}
    if "edit" not in found:
        return []
    labels = (("backup", "Backup"), ("os", "OS patch"), ("docker", "Docker"))
    return [
        {"feature": key, "flag": _FEATURE_FLAG[key], "label": label}
        for key, label in labels
        if scopes_allow_feature(found, key)
    ]


_DEVICE_MARKS = (
    (re.compile(r"compute module\s*5|\bcm\s*5\b"), "CM5"),
    (re.compile(r"compute module\s*4|\bcm\s*4\b"), "CM4"),
    (re.compile(r"\b(?:raspberry\s*)?pi\s*500\b"), "500"),
    (re.compile(r"\b(?:raspberry\s*)?pi\s*400\b"), "400"),
    (re.compile(r"\bzero\s*2\b"), "Zero 2"),
    (re.compile(r"\b(?:pi\s*)?zero(?:\s*w)?\b|\brpi\s*zero\b"), "Zero"),
    (re.compile(r"\b(?:raspberry\s*)?pi\s*5\b|\brpi\s*5\b"), "5"),
    (re.compile(r"\b(?:raspberry\s*)?pi\s*4\b|\brpi\s*4\b"), "4"),
    (re.compile(r"\b(?:raspberry\s*)?pi\s*3\b|\brpi\s*3\b"), "3"),
    (re.compile(r"\b(?:raspberry\s*)?pi\s*2\b|\brpi\s*2\b"), "2"),
    (re.compile(r"\b(?:raspberry\s*)?pi\s*1\b|\brpi\s*1\b"), "1"),
)


def device_mark(row: dict[str, Any] | None) -> str | None:
    """Short Raspberry Pi model parsed from the stored hardware string."""
    hw = str((row or {}).get("hardware") or "").lower()
    if not hw:
        return None
    for pattern, mark in _DEVICE_MARKS:
        if pattern.search(hw):
            return mark
    if "raspberry" in hw or re.search(r"\brpi\b", hw):
        return "Pi"
    return None


def device_icon(row: dict[str, Any] | None) -> str:
    if device_mark(row):
        return "mdi:raspberry-pi"
    return "mdi:server"


def os_icon(row: dict[str, Any] | None) -> str:
    raw = row or {}
    blob = " ".join(
        str(raw.get(key) or "") for key in ("os_id", "os_type", "os_pretty", "os_display")
    ).lower()
    if "haos" in blob or "home assistant" in blob:
        return "mdi:home-assistant"
    if "ubuntu" in blob:
        return "mdi:ubuntu"
    if any(token in blob for token in ("raspbian", "raspberry pi os", "debian", "raspberrypi")):
        return "mdi:debian"
    return "mdi:linux"


def annotate_server(row: dict[str, Any]) -> dict[str, Any]:
    """Icon fields the Lovelace card reads. No new herder column."""
    row["device_icon"] = device_icon(row)
    row["device_mark"] = device_mark(row) or ""
    row["os_icon"] = os_icon(row)
    return row


def history_points(rows: Any, entity_id: str) -> list[float]:
    """Numeric series from a history websocket payload.

    Home Assistant returns a map keyed by entity id. A list is the older shape,
    one series in request order, so the first entry is the fallback.
    """
    series: Any = None
    if isinstance(rows, dict):
        series = rows.get(entity_id)
    elif isinstance(rows, list) and rows:
        series = rows[0]
    if not isinstance(series, list):
        return []
    out: list[float] = []
    for item in series:
        raw = item.get("s", item.get("state")) if isinstance(item, dict) else item
        try:
            out.append(float(raw))
        except (TypeError, ValueError):
            continue
    return out


def jobs_left_active(previous: list | None, current: list | None) -> list[dict[str, Any]]:
    """Jobs present in the previous active set and absent from the current one."""
    prev: dict[Any, dict[str, Any]] = {}
    for job in previous or []:
        if isinstance(job, dict) and job.get("id") is not None:
            prev[job["id"]] = job
    current_ids = {
        job.get("id")
        for job in (current or [])
        if isinstance(job, dict) and job.get("id") is not None
    }
    return [prev[job_id] for job_id in prev if job_id not in current_ids]


def finished_job_events(previous: dict | None, jobs: list | None) -> list[dict[str, Any]]:
    """Empty on the first poll. After that, ids that left the active set."""
    if not isinstance(previous, dict):
        return []
    return jobs_left_active(previous.get("jobs"), jobs)


def disk_used_percent(row: dict[str, Any] | None) -> float | None:
    raw = row or {}
    try:
        total = int(raw.get("disk_total_bytes") or 0)
        used = int(raw.get("disk_used_bytes") or 0)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return round(100.0 * used / total, 1)


def container_slug(name: str) -> str:
    text = "".join(ch if ch.isalnum() else "_" for ch in (name or "").strip().lower())
    return text.strip("_") or "container"


def fleet_urls(origin: str) -> dict[str, str]:
    base = (origin or "").rstrip("/")
    return {
        "jobs_url": f"{base}/jobs",
        "audit_url": f"{base}/audit",
        "alerts_url": f"{base}/notifications",
        "open_url": base,
    }

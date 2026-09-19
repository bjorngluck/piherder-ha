"""Pure helpers for HA entities (no Home Assistant imports)."""
from __future__ import annotations

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
    if raw.get("os_display"):
        return str(raw["os_display"])
    ot = str(raw.get("os_type") or "").strip().lower()
    return OS_LABELS.get(ot, ot or "Linux")


def device_model(row: dict[str, Any] | None) -> str:
    """Device model line: OS display + enabled features (not raw debian hardware)."""
    os_name = os_display(row)
    feats = features_label(row)
    if feats == "none":
        return os_name
    return f"{os_name} · {feats}"


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


def fleet_urls(origin: str) -> dict[str, str]:
    base = (origin or "").rstrip("/")
    return {
        "jobs_url": f"{base}/jobs",
        "audit_url": f"{base}/audit",
        "alerts_url": f"{base}/notifications",
        "open_url": base,
    }


def host_urls(origin: str, server_id: int) -> dict[str, str]:
    base = (origin or "").rstrip("/")
    sid = int(server_id)
    return {
        "open_url": f"{base}/servers/{sid}",
        "jobs_url": f"{base}/jobs?server_id={sid}",
        "audit_url": f"{base}/audit?server_id={sid}",
        "alerts_url": f"{base}/notifications?server_id={sid}",
    }

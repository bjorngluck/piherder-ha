"""Pure helpers for HA entities (no Home Assistant imports)."""
from __future__ import annotations

from typing import Any

FEATURE_LABELS = (
    ("backup", "backup"),
    ("os_patch", "OS patch"),
    ("docker", "Docker"),
)


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


def device_model(row: dict[str, Any] | None) -> str:
    os_type = str((row or {}).get("os_type") or "host")
    feats = features_label(row)
    if feats == "none":
        return os_type
    return f"{os_type} · {feats}"


def fleet_urls(origin: str) -> dict[str, str]:
    base = (origin or "").rstrip("/")
    return {
        "jobs_url": f"{base}/jobs",
        "audit_url": f"{base}/audit",
        "open_url": base,
    }


def host_urls(origin: str, server_id: int) -> dict[str, str]:
    base = (origin or "").rstrip("/")
    sid = int(server_id)
    return {
        "open_url": f"{base}/servers/{sid}",
        "jobs_url": f"{base}/jobs?server_id={sid}",
        "audit_url": f"{base}/audit?server_id={sid}",
    }

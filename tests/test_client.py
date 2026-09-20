"""Pure tests for the PiHerder API client helpers (no Home Assistant)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_CLIENT = Path(__file__).resolve().parents[1] / "custom_components" / "piherder" / "client.py"
_spec = importlib.util.spec_from_file_location("piherder_client", _CLIENT)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
derive_summary = _mod.derive_summary
normalize_base_url = _mod.normalize_base_url


def test_normalize_base_url():
    assert normalize_base_url("https://ph.example/") == "https://ph.example"
    with pytest.raises(ValueError):
        normalize_base_url("  ")


def test_derive_summary_matches_herder_counts():
    servers = [
        {"id": 1, "os_updates_count": 4, "container_updates_count": 0, "reboot_pending": True, "last_backup_at": "2026-09-10T02:00:00"},
        {"id": 2, "os_updates_count": 0, "container_updates_count": 2, "reboot_pending": False, "last_backup_at": "2026-09-01T02:00:00"},
    ]
    jobs = [
        {"status": "running", "job_type": "backup"},
        {"status": "pending", "job_type": "service_migrate"},
        {"status": "success", "job_type": "service_migrate"},
    ]
    out = derive_summary(servers, jobs, version="1.5.0")
    assert out["hosts"] == 2
    assert out["os_updates"] == 1
    assert out["container_updates"] == 1
    assert out["reboot_pending"] == 1
    assert out["jobs_running"] == 2
    assert out["move_running"] is True
    assert out["last_backup_oldest_at"] == "2026-09-01T02:00:00"


def test_features_and_urls():
    from pathlib import Path
    import importlib.util

    hp = Path(__file__).resolve().parents[1] / "custom_components" / "piherder" / "helpers.py"
    spec = importlib.util.spec_from_file_location("piherder_helpers", hp)
    h = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(h)
    row = {"os_type": "debian", "features": {"backup": True, "os_patch": False, "docker": True}}
    assert h.features_label(row) == "backup, Docker"
    assert h.device_model(row) == "Debian"
    assert h.feature_flags(row)["backup"] is True
    assert h.feature_flags(row)["os_patch"] is False
    urls = h.host_urls("https://ph.example", 12)
    assert urls["jobs_url"] == "https://ph.example/jobs?server_id=12"
    assert urls["audit_url"] == "https://ph.example/audit?server_id=12"
    assert urls["open_url"] == "https://ph.example/servers/12"
    assert urls["docker_url"].endswith("/docker")
    assert urls["backup_url"].endswith("/backups")
    assert urls["services_url"].endswith("/services")
    assert h.features_label({"features": {}}) == "none"
    assert h.os_display({"os_type": "haos"}) == "HAOS"
    assert h.os_display({"os_display": "Ubuntu", "os_type": "debian"}) == "Ubuntu"
    assert h.device_model({"os_display": "Ubuntu", "features": {"backup": True, "os_patch": False, "docker": False}}) == "Ubuntu"
    assert h.hardware_label({"hardware": "Raspberry Pi 5 Model B Rev 1.0"}) == "Raspberry Pi 5 Model B Rev 1.0"
    assert h.backup_state({}) == "never"
    dt = h.parse_utc("2026-09-10T02:00:00")
    assert dt is not None and dt.tzinfo is not None
    assert h.alert_state({"alerts_open": 0}) == "none"
    assert "kernel" in h.alert_state({"alerts_open": 1, "alert_title": "kernel update"}) or h.alert_state({"alerts_open": 1, "alert_title": "kernel update"}) == "kernel update"

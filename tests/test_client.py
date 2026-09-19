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

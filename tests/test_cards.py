"""HA-cards: job posts and which buttons a token may see. No Home Assistant, no SSH."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "piherder"


def _load(name: str):
    path = _ROOT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"piherder_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


helpers = _load("helpers")
client = _load("client")


class _Resp:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self._payload = payload

    async def text(self):
        return json.dumps(self._payload)

    async def json(self, content_type=None):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


class _Session:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self.payload = payload
        self.calls: list[tuple] = []

    def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs.get("json")))
        return _Resp(self.status, self.payload)

    def patch(self, url, **kwargs):
        self.calls.append(("patch", url, kwargs.get("json")))
        return _Resp(self.status, self.payload)


def test_read_token_hides_actions_and_toggles():
    features = {"backup": True, "os_patch": True, "docker": True}
    assert helpers.card_actions(["read"], features) == []
    assert helpers.card_toggles(["read"]) == []


def test_jobs_token_lists_confirms_including_reboot():
    features = {"backup": True, "os_patch": True, "docker": True}
    actions = helpers.card_actions(["read", "jobs"], features)
    kinds = [row["job_type"] for row in actions]
    assert kinds == [
        "backup",
        "retention",
        "os_update_check",
        "container_update_check",
        "os_patch",
        "container_patch",
        "host_reboot",
    ]
    reboot = next(row for row in actions if row["job_type"] == "host_reboot")
    assert reboot["confirm"] is True
    check = next(row for row in actions if row["job_type"] == "os_update_check")
    assert check["confirm"] is False
    assert helpers.card_toggles(["read", "jobs"]) == []


def test_feature_scope_hides_other_jobs_and_off_flag():
    actions = helpers.card_actions(
        ["read", "jobs", "feature:os"],
        {"backup": True, "os_patch": False, "docker": True},
    )
    assert actions == []
    actions = helpers.card_actions(
        ["read", "jobs", "feature:os"],
        {"backup": True, "os_patch": True, "docker": True},
    )
    assert {row["job_type"] for row in actions} == {"os_update_check", "os_patch", "host_reboot"}
    toggles = helpers.card_toggles(["read", "edit", "feature:docker"])
    assert [row["flag"] for row in toggles] == ["docker"]


def test_trigger_job_posts_host_reboot_and_os_patch():
    async def _run():
        session = _Session(202, {"job_id": 9, "job_type": "host_reboot", "status": "pending"})
        out = await client.trigger_job(session, "https://ph.example", "ph_x", 4, "host_reboot")
        assert out["http_status"] == 202
        assert out["already_active"] is False
        assert session.calls == [
            ("post", "https://ph.example/api/v1/servers/4/jobs", {"job_type": "host_reboot"})
        ]
        session = _Session(202, {"job_id": 10, "job_type": "os_patch"})
        await client.trigger_job(session, "https://ph.example/", "ph_x", 4, "os_patch")
        assert session.calls[0][2] == {"job_type": "os_patch"}
        busy = _Session(409, {"already_active": True, "job": {"id": 3, "job_type": "os_patch"}})
        out = await client.trigger_job(busy, "https://ph.example", "ph_x", 4, "host_reboot")
        assert out["already_active"] is True
        assert out["job"]["job_type"] == "os_patch"

    asyncio.run(_run())


def test_set_features_posts_three_flags():
    async def _run():
        session = _Session(200, {"ok": True, "changed": {"backup": True}})
        await client.set_features(
            session,
            "https://ph.example",
            "ph_x",
            4,
            {"backup": True, "os_patch": False, "docker": True, "files": True},
        )
        assert session.calls == [
            (
                "patch",
                "https://ph.example/api/v1/servers/4/features",
                {"backup": True, "os_patch": False, "docker": True},
            )
        ]

    asyncio.run(_run())


def test_memory_and_cpu_from_snapshot():
    row = {
        "memory_total_bytes": 1000,
        "memory_used_bytes": 250,
        "cpu_load": 1.5,
        "disk_total_bytes": 0,
    }
    assert helpers.memory_used_percent(row) == 25.0
    assert helpers.cpu_load_value(row) == 1.5
    assert helpers.disk_used_percent(row) is None


def test_unknown_job_type_rejected():
    async def _run():
        with pytest.raises(client.PiHerderApiError):
            await client.trigger_job(_Session(202, {}), "https://ph.example", "ph_x", 1, "service_migrate")

    asyncio.run(_run())

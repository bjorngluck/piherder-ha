"""HTTP client for PiHerder /api/v1 (no Home Assistant imports)."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

try:
    import aiohttp
except ImportError:  # unit tests of derive_summary without aiohttp
    aiohttp = None  # type: ignore


class PiHerderApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def normalize_base_url(url: str) -> str:
    raw = (url or "").strip().rstrip("/")
    if not raw:
        raise ValueError("Base URL is required")
    return raw


JOB_TYPES = (
    "backup",
    "retention",
    "os_update_check",
    "container_update_check",
    "os_patch",
    "container_patch",
    "host_reboot",
    "container_start",
    "container_stop",
    "container_restart",
    "container_redeploy",
    "docker_stack_stop",
)

# Lovelace shows and writes this much. The herder still enforces the fleet jail and its own upload cap.
CARD_FILE_BYTES = 64 * 1024

FEATURE_FIELDS = ("backup", "os_patch", "docker")


async def _request_json(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    token: str,
    *,
    body: dict | None = None,
    form: Any = None,
    verify_ssl: bool = True,
) -> tuple[int, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    ssl: bool | None = None if verify_ssl else False
    kwargs: dict[str, Any] = {"headers": headers, "ssl": ssl}
    if aiohttp is not None:
        kwargs["timeout"] = aiohttp.ClientTimeout(total=30)
    if form is not None:
        kwargs["data"] = form
    elif body is not None:
        kwargs["json"] = body
        headers["Content-Type"] = "application/json"
    call = getattr(session, method.lower())
    async with call(url, **kwargs) as resp:
        text = await resp.text()
        parsed: Any = None
        if text:
            try:
                parsed = await resp.json(content_type=None)
            except Exception:
                parsed = {"detail": text[:300]}
        return resp.status, parsed if parsed is not None else {}


async def _get_json(
    session: aiohttp.ClientSession,
    url: str,
    token: str,
    *,
    verify_ssl: bool = True,
) -> Any:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    ssl: bool | None = None if verify_ssl else False
    async with session.get(url, headers=headers, ssl=ssl, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        text = await resp.text()
        if resp.status == 401 or resp.status == 403:
            raise PiHerderApiError(resp.status, "Token rejected (need scope read; check allowlist)")
        if resp.status >= 400:
            raise PiHerderApiError(resp.status, text[:300] or resp.reason or "error")
        if not text:
            return {}
        try:
            return await resp.json(content_type=None)
        except Exception as exc:
            raise PiHerderApiError(resp.status, f"Invalid JSON: {exc}") from exc


async def trigger_job(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    server_id: int,
    job_type: str,
    *,
    source_filter: str | None = None,
    service: str | None = None,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """POST a job. 202 accepted. 409 returns the job already running. Never SSH."""
    kind = (job_type or "").strip().lower()
    if kind in ("docker_stack_down", "docker_stack_remove"):
        raise PiHerderApiError(400, "Project stop is docker compose stop, not down or remove")
    if kind not in JOB_TYPES:
        raise PiHerderApiError(400, f"Unsupported job_type {kind}")
    body: dict[str, Any] = {"job_type": kind}
    if kind == "docker_stack_stop":
        path = (source_filter or "").strip()
        if not path:
            raise PiHerderApiError(400, "Project stop needs the compose directory")
        body["source_filter"] = path
    elif kind in ("container_start", "container_stop", "container_restart", "container_redeploy"):
        path = (source_filter or "").strip()
        svc = (service or "").strip()
        if not path or not svc:
            raise PiHerderApiError(
                400, "container start, stop, restart, and update need a compose directory and a service name"
            )
        body["source_filter"] = path
        body["service"] = svc
    elif source_filter:
        body["source_filter"] = source_filter
    origin = normalize_base_url(base)
    status, parsed = await _request_json(
        session,
        "post",
        f"{origin}/api/v1/servers/{int(server_id)}/jobs",
        token,
        body=body,
        verify_ssl=verify_ssl,
    )
    if not isinstance(parsed, dict):
        parsed = {}
    if status in (202, 409):
        out = dict(parsed)
        out["http_status"] = status
        out["already_active"] = status == 409
        return out
    detail = parsed.get("detail") if isinstance(parsed, dict) else ""
    raise PiHerderApiError(status, str(detail or "job failed")[:300])


async def set_features(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    server_id: int,
    features: dict[str, bool],
    *,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """PATCH backup / os_patch / docker. Other keys are dropped."""
    body = {key: bool(features[key]) for key in FEATURE_FIELDS if key in features}
    if not body:
        raise PiHerderApiError(400, "No feature fields")
    origin = normalize_base_url(base)
    status, parsed = await _request_json(
        session,
        "patch",
        f"{origin}/api/v1/servers/{int(server_id)}/features",
        token,
        body=body,
        verify_ssl=verify_ssl,
    )
    if status < 400 and isinstance(parsed, dict):
        return parsed
    detail = parsed.get("detail") if isinstance(parsed, dict) else ""
    raise PiHerderApiError(status, str(detail or "features failed")[:300])


async def start_move(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    server_id: int,
    dest_server_id: int,
    project: str,
    *,
    confirm: bool = False,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """POST a stop-first Move. confirm must be true. No undo. Never SSH."""
    if confirm is not True:
        raise PiHerderApiError(400, "Move requires confirm")
    name = (project or "").strip()
    if not name or "/" in name or name.startswith(".."):
        raise PiHerderApiError(400, "Move needs a compose project name")
    origin = normalize_base_url(base)
    status, parsed = await _request_json(
        session,
        "post",
        f"{origin}/api/v1/servers/{int(server_id)}/moves",
        token,
        body={
            "dest_server_id": int(dest_server_id),
            "project": name,
            "confirm": True,
        },
        verify_ssl=verify_ssl,
    )
    if not isinstance(parsed, dict):
        parsed = {}
    if status in (202, 409):
        out = dict(parsed)
        out["http_status"] = status
        out["already_active"] = status == 409
        return out
    detail = parsed.get("detail") if isinstance(parsed, dict) else ""
    raise PiHerderApiError(status, str(detail or "move failed")[:300])


def _file_rel(path: str | None) -> str:
    try:
        return _helpers_module().fleet_jail_rel(path)
    except ValueError as exc:
        raise PiHerderApiError(400, str(exc)) from exc


def _files_url(origin: str, server_id: int, suffix: str, rel: str) -> str:
    return (
        f"{origin}/api/v1/servers/{int(server_id)}/files{suffix}?p={quote(rel, safe='/')}"
    )


async def list_files(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    server_id: int,
    path: str | None = "",
    *,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """List one fleet-jail directory. The herder refuses paths outside that jail."""
    origin = normalize_base_url(base)
    rel = _file_rel(path)
    data = await _get_json(
        session, _files_url(origin, server_id, "", rel), token, verify_ssl=verify_ssl
    )
    if not isinstance(data, dict):
        raise PiHerderApiError(500, "files: expected object")
    return data


async def read_file(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    server_id: int,
    path: str,
    *,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """Download one fleet-jail file as text, capped for the Lovelace response."""
    origin = normalize_base_url(base)
    rel = _file_rel(path)
    status, raw = await _request_bytes(
        session,
        "get",
        _files_url(origin, server_id, "/download", rel),
        token,
        verify_ssl=verify_ssl,
    )
    if status >= 400:
        raise PiHerderApiError(status, _error_text(raw))
    if len(raw) > CARD_FILE_BYTES:
        raise PiHerderApiError(400, "File is larger than the card can show")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PiHerderApiError(400, "File is not text. Open it in PiHerder.") from exc
    return {"path": rel, "text": text, "bytes": len(raw)}


async def write_file(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    server_id: int,
    path: str | None,
    name: str,
    text: str,
    *,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """Upload one text file into a fleet-jail directory."""
    if aiohttp is None:
        raise PiHerderApiError(500, "aiohttp is required")
    origin = normalize_base_url(base)
    rel = _file_rel(path)
    filename = (name or "").strip().replace("\\", "/").split("/")[-1]
    if not filename or filename in (".", ".."):
        raise PiHerderApiError(400, "File name is required")
    raw = (text or "").encode("utf-8")
    if len(raw) > CARD_FILE_BYTES:
        raise PiHerderApiError(400, "File is larger than the card can write")
    form = aiohttp.FormData()
    form.add_field("p", rel)
    form.add_field("file", raw, filename=filename, content_type="text/plain; charset=utf-8")
    status, parsed = await _request_json(
        session,
        "post",
        f"{origin}/api/v1/servers/{int(server_id)}/files",
        token,
        form=form,
        verify_ssl=verify_ssl,
    )
    if status < 400 and isinstance(parsed, dict):
        return parsed
    detail = parsed.get("detail") if isinstance(parsed, dict) else ""
    raise PiHerderApiError(status, str(detail or "upload failed")[:300])


async def mkdir_file(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    server_id: int,
    path: str | None,
    name: str,
    *,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    origin = normalize_base_url(base)
    status, parsed = await _request_json(
        session,
        "post",
        f"{origin}/api/v1/servers/{int(server_id)}/files/mkdir",
        token,
        body={"p": _file_rel(path), "name": (name or "").strip()},
        verify_ssl=verify_ssl,
    )
    if status < 400 and isinstance(parsed, dict):
        return parsed
    detail = parsed.get("detail") if isinstance(parsed, dict) else ""
    raise PiHerderApiError(status, str(detail or "mkdir failed")[:300])


async def rename_file(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    server_id: int,
    path: str | None,
    src: str,
    dest: str,
    *,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    origin = normalize_base_url(base)
    status, parsed = await _request_json(
        session,
        "post",
        f"{origin}/api/v1/servers/{int(server_id)}/files/rename",
        token,
        body={"p": _file_rel(path), "src": (src or "").strip(), "dest": (dest or "").strip()},
        verify_ssl=verify_ssl,
    )
    if status < 400 and isinstance(parsed, dict):
        return parsed
    detail = parsed.get("detail") if isinstance(parsed, dict) else ""
    raise PiHerderApiError(status, str(detail or "rename failed")[:300])


async def delete_file(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    server_id: int,
    path: str,
    *,
    confirm: bool = False,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """Delete one file or an empty directory inside the fleet jail."""
    if confirm is not True:
        raise PiHerderApiError(400, "Delete requires confirm")
    origin = normalize_base_url(base)
    rel = _file_rel(path)
    status, parsed = await _request_json(
        session,
        "delete",
        _files_url(origin, server_id, "", rel),
        token,
        verify_ssl=verify_ssl,
    )
    if status < 400 and isinstance(parsed, dict):
        return parsed
    detail = parsed.get("detail") if isinstance(parsed, dict) else ""
    raise PiHerderApiError(status, str(detail or "delete failed")[:300])


def _error_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")[:300]
    try:
        import json

        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get("detail"):
            return str(parsed["detail"])[:300]
    except Exception:
        pass
    return text or "error"


async def _request_bytes(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    token: str,
    *,
    verify_ssl: bool = True,
) -> tuple[int, bytes]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "*/*"}
    ssl: bool | None = None if verify_ssl else False
    kwargs: dict[str, Any] = {"headers": headers, "ssl": ssl}
    if aiohttp is not None:
        kwargs["timeout"] = aiohttp.ClientTimeout(total=30)
    call = getattr(session, method.lower())
    async with call(url, **kwargs) as resp:
        return resp.status, await resp.read()


async def fetch_health(session: aiohttp.ClientSession, base: str, token: str, *, verify_ssl: bool = True) -> dict:
    data = await _get_json(session, f"{normalize_base_url(base)}/api/v1/health", token, verify_ssl=verify_ssl)
    if not isinstance(data, dict):
        raise PiHerderApiError(500, "health: expected object")
    return data


async def fetch_snapshot(
    session: aiohttp.ClientSession, base: str, token: str, *, verify_ssl: bool = True
) -> dict[str, Any]:
    """Coordinator payload: summary if present, else derive from servers + jobs."""
    origin = normalize_base_url(base)
    health = await fetch_health(session, origin, token, verify_ssl=verify_ssl)
    servers_raw = await _get_json(
        session, f"{origin}/api/v1/servers?limit=100", token, verify_ssl=verify_ssl
    )
    jobs_raw = await _get_json(
        session,
        f"{origin}/api/v1/jobs?active_only=true&limit=100",
        token,
        verify_ssl=verify_ssl,
    )
    servers = servers_raw.get("servers") if isinstance(servers_raw, dict) else []
    if not isinstance(servers, list):
        servers = []
    servers = [_annotate_server(row) if isinstance(row, dict) else row for row in servers]
    jobs = jobs_raw.get("jobs") if isinstance(jobs_raw, dict) else []
    if not isinstance(jobs, list):
        jobs = []

    summary = None
    try:
        summary = await _get_json(
            session, f"{origin}/api/v1/summary", token, verify_ssl=verify_ssl
        )
        if not isinstance(summary, dict) or "hosts" not in summary:
            summary = None
    except PiHerderApiError as exc:
        if exc.status not in (404, 405):
            # Missing summary is fine on older herders; other errors still fail.
            if exc.status >= 500:
                raise
            summary = None

    if not isinstance(summary, dict):
        summary = derive_summary(servers, jobs, version=None)

    inventory = await _optional_object(
        session, f"{origin}/api/v1/inventory", token, verify_ssl=verify_ssl
    )
    services = await _optional_object(
        session, f"{origin}/api/v1/services", token, verify_ssl=verify_ssl
    )
    hosts = inventory.get("hosts") if isinstance(inventory, dict) else []
    if not isinstance(hosts, list):
        hosts = []
    service_rows = services.get("services") if isinstance(services, dict) else []
    if not isinstance(service_rows, list):
        service_rows = []

    return {
        "origin": origin,
        "health": health,
        "summary": summary,
        "servers": servers,
        "jobs": jobs,
        "inventory": hosts,
        "services": service_rows,
    }


async def _optional_object(
    session: aiohttp.ClientSession,
    url: str,
    token: str,
    *,
    verify_ssl: bool = True,
) -> dict:
    """Slice 1b snapshots. 404 on an older herder is an empty object, not a failure."""
    try:
        data = await _get_json(session, url, token, verify_ssl=verify_ssl)
    except PiHerderApiError as exc:
        if exc.status in (404, 405):
            return {}
        if exc.status >= 500:
            raise
        return {}
    return data if isinstance(data, dict) else {}


def _helpers_module():
    """Load helpers beside this file so unit tests can import client alone."""
    import importlib.util
    import sys
    from pathlib import Path

    key = "_piherder_helpers_annot"
    mod = sys.modules.get(key)
    if mod is None:
        path = Path(__file__).with_name("helpers.py")
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return mod


def _annotate_server(row: dict) -> dict:
    return _helpers_module().annotate_server(row)


def derive_summary(servers: list, jobs: list, *, version: str | None) -> dict[str, Any]:
    os_n = sum(1 for s in servers if int(s.get("os_updates_count") or 0) > 0)
    cont_n = sum(1 for s in servers if int(s.get("container_updates_count") or 0) > 0)
    reboot_n = sum(1 for s in servers if s.get("reboot_pending"))
    backups = [s.get("last_backup_at") for s in servers if s.get("last_backup_at")]
    oldest = min(backups) if backups else None
    active = [j for j in jobs if str(j.get("status") or "").lower() in ("pending", "running")]
    move = any(str(j.get("job_type") or "").lower() == "service_migrate" for j in active)
    return {
        "ok": True,
        "version": version,
        "hosts": len(servers),
        "os_updates": os_n,
        "container_updates": cont_n,
        "reboot_pending": reboot_n,
        "jobs_running": len(active),
        "move_running": bool(move),
        "last_backup_oldest_at": oldest,
        "alerts_open": 0,
    }

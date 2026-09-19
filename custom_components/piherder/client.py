"""HTTP client for PiHerder /api/v1 (no Home Assistant imports)."""
from __future__ import annotations

from typing import Any

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

    return {
        "origin": origin,
        "health": health,
        "summary": summary,
        "servers": servers,
        "jobs": jobs,
    }


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
    }

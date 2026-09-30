"""DataUpdateCoordinator — snapshot reads only, never SSH."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import PiHerderApiError, fetch_snapshot, normalize_base_url
from .const import CONF_SCAN_INTERVAL, CONF_VERIFY_SSL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .helpers import finished_job_events


class PiHerderCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = int(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.entry = entry
        self.origin = normalize_base_url(entry.data[CONF_URL])

    async def _async_update_data(self) -> dict[str, Any]:
        verify = bool(self.entry.data.get(CONF_VERIFY_SSL, True))
        session = async_get_clientsession(self.hass, verify_ssl=verify)
        try:
            data = await fetch_snapshot(
                session,
                self.origin,
                self.entry.data[CONF_TOKEN],
                verify_ssl=verify,
            )
        except PiHerderApiError as exc:
            raise UpdateFailed(exc.message) from exc
        except Exception as exc:
            raise UpdateFailed(str(exc)) from exc
        previous = self.data if isinstance(self.data, dict) else None
        for job in finished_job_events(previous, data.get("jobs")):
            self.hass.bus.async_fire(
                "piherder_job_completed",
                {
                    "job_id": job.get("id"),
                    "server_id": job.get("server_id"),
                    "job_type": job.get("job_type"),
                    "status": job.get("status"),
                },
            )
        return data

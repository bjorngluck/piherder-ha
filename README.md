# PiHerder for Home Assistant

HACS integration: Home Assistant **observes** a [PiHerder](https://github.com/bjorngluck/piherder) fleet over `/api/v1`.

This is **not** PiHerder managing HAOS over SSH. That stays in the PiHerder image ([HAOS hosts](https://piherder-docs.hacknow.info/day-to-day/haos-hosts/)).

**Slice 1 (read-only), plugin 0.1.5:** config flow, fleet sensors, one HA device per host. **Visit** on the device opens that host in PiHerder. Sensors are status (counts, OS, hardware, alerts) — not fake “open” buttons. Token scope **`read`**. Poll is database snapshots — never SSH the fleet.

No start/stop, Move, Files, console, or OS apply from HA.

## Install

1. In PiHerder: Settings → API management → token with **`read` only**. IP allowlist = this HA host.
2. HACS → custom repositories → [bjorngluck/piherder-ha](https://github.com/bjorngluck/piherder-ha) → Integration.
3. Add **PiHerder**: base URL, `ph_…` token, TLS verify, poll interval. Wrong URL/token keeps the form filled.

HACS does **not** auto-refresh custom repos. New release: HACS → PiHerder → **⋮ → Redownload** → pick the tag → **restart Home Assistant**. Confirm fleet **Plugin** is **0.1.5**.

Operator wiki: [Home Assistant → PiHerder](https://piherder-docs.hacknow.info/integrations/home-assistant/) (Pages builds `main`; train copy is on `v1.6.0-dev`).

Do not vendor this tree inside the PiHerder Docker image.

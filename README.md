# PiHerder for Home Assistant

HACS integration: Home Assistant **observes** a [PiHerder](https://github.com/bjorngluck/piherder) fleet over `/api/v1`.

This is **not** PiHerder managing HAOS over SSH. That stays in the PiHerder image ([HAOS hosts](https://piherder-docs.hacknow.info/day-to-day/haos-hosts/)).

**Slice 1 (read-only):** config flow, fleet sensors, one HA device per PiHerder host, Open in PiHerder. Token scope **`read`**. Poll is database snapshots — never SSH the fleet.

No start/stop, Move, Files, console, or OS apply from HA.

## Install

1. In PiHerder: Settings → API management → token with **`read` only**. IP allowlist = this HA host.
2. HACS → custom repositories → this GitHub repo → Integration.
3. Add **PiHerder**: base URL, `ph_…` token, TLS verify, poll interval.

Operator wiki: [Home Assistant → PiHerder](https://piherder-docs.hacknow.info/integrations/home-assistant/) (Pages builds `main`; train copy is on `v1.6.0-dev`).

## GitHub

Lean name: **`bjorngluck/piherder-ha`**. Confirm before the first public create. Do not vendor this tree inside the PiHerder Docker image.

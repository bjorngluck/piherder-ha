# PiHerder for Home Assistant

HACS integration: Home Assistant **observes** a [PiHerder](https://github.com/bjorngluck/piherder) fleet over `/api/v1`.

This is **not** PiHerder managing HAOS over SSH. That stays in the PiHerder image ([HAOS hosts](https://piherder-docs.hacknow.info/day-to-day/haos-hosts/)).

**Plugin 0.2.0:** Lovelace card **PiHerder fleet** (`custom:piherder-dashboard-card`) — fleet CPU/memory/disk/containers, expand a host, chips to Host / Docker / Backups / Alerts / Audit. Device page Visit remains the host. Token **`read`**.

No start/stop, Move, Files, console, or OS apply from HA.

## Install

1. In PiHerder: Settings → API management → token with **`read` only**. IP allowlist = this HA host.
2. HACS → custom repositories → [bjorngluck/piherder-ha](https://github.com/bjorngluck/piherder-ha) → Integration.
3. Add **PiHerder**: base URL, `ph_…` token, TLS verify, poll interval. Wrong URL/token keeps the form filled.

HACS does **not** auto-refresh custom repos. New release: HACS → PiHerder → **⋮ → Redownload** → pick the tag → **restart Home Assistant**. Confirm fleet **Plugin** is **0.2.2**, restart HA, hard-refresh. Add card YAML `type: custom:piherder-dashboard-card`. Resource must be `/local/piherder-dashboard-card.js?v=0.2.2` as **JavaScript module** (delete any old `/api/piherder/…` resource).

Operator wiki: [Home Assistant → PiHerder](https://piherder-docs.hacknow.info/integrations/home-assistant/) (Pages builds `main`; train copy is on `v1.6.0-dev`).

Do not vendor this tree inside the PiHerder Docker image.

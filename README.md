# PiHerder for Home Assistant

HACS integration: Home Assistant **observes** a [PiHerder](https://github.com/bjorngluck/piherder) fleet over `/api/v1`.

This is **not** PiHerder managing HAOS over SSH. That stays in the PiHerder image ([HAOS hosts](https://piherder-docs.hacknow.info/day-to-day/haos-hosts/)).

**Plugin 0.2.2:** Lovelace card **PiHerder fleet** (`custom:piherder-dashboard-card`) — fleet CPU/memory/disk/containers, expand a host, chips to Host / Docker / Backups / Alerts / Audit. The HA **device page** has one **Visit** (the host). Home Assistant does not allow extra Visit links on custom devices; those shortcuts are the card chips. Token **`read`**.

No start/stop, Move, Files, console, or OS apply from HA.

## Install

1. In PiHerder: Settings → API management → token with **`read` only**. IP allowlist = this HA host.
2. HACS → custom repositories → [bjorngluck/piherder-ha](https://github.com/bjorngluck/piherder-ha) → Integration.
3. Add **PiHerder**: base URL, `ph_…` token, TLS verify, poll interval. Wrong URL/token keeps the form filled.
4. Confirm fleet **Plugin** is **0.2.2**.

HACS does **not** auto-refresh custom repos. New GitHub Release: HACS → PiHerder → **⋮ → Redownload** → pick the tag → **restart Home Assistant**. Reload of the config entry does not replace files.

## Fleet card

After restart, the integration copies the card JS to Home Assistant `config/www/`.

1. Dashboard **⋮ → Resources** — delete any `/api/piherder/…` URL. Add **`/local/piherder-dashboard-card.js?v=0.2.2`** as **JavaScript module**.
2. Hard-refresh the browser (Ctrl+Shift+R).
3. Add card → **Manual**:

```yaml
type: custom:piherder-dashboard-card
```

“Custom element doesn’t exist” = stale resource URL, resource type is JavaScript instead of module, or HA was not restarted after Redownload.

CPU/memory/disk numbers come from PiHerder’s stored host-facts snapshot (Alembic **045**). Recreate PiHerder **web**, then System Info refresh (or wait ~15 minutes). Empty bars mean the herder has no snapshot yet.

Operator wiki: [Home Assistant → PiHerder](https://piherder-docs.hacknow.info/integrations/home-assistant/) (Pages builds `main`; train copy is on `v1.6.0-dev`).

Do not vendor this tree inside the PiHerder Docker image.

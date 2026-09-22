# PiHerder for Home Assistant

[![Release](https://img.shields.io/badge/plugin-v0.2.4-green.svg)](https://github.com/bjorngluck/piherder-ha/releases/tag/v0.2.4)
[![PiHerder](https://img.shields.io/badge/PiHerder-v1.6%20train-blue.svg)](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/docs/PLAN_v1.6.0.md)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-41BDF5?logo=home-assistant&logoColor=fff)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-custom%20integration-orange.svg)](https://github.com/bjorngluck/piherder-ha)
[![Install guide](https://img.shields.io/badge/wiki-install%20steps-red.svg)](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/wiki/integrations/home-assistant.md)
[![Sponsor](https://img.shields.io/badge/Sponsor-%231EAEDB?logo=githubsponsors&logoColor=fff&style=flat)](https://github.com/sponsors/bjorngluck)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-ffdd00?logo=buymeacoffee&logoColor=black&style=flat)](https://www.buymeacoffee.com/bjorngluck)

HACS integration: Home Assistant **observes** a [PiHerder](https://github.com/bjorngluck/piherder) fleet over `/api/v1`.

This is **not** PiHerder managing HAOS over SSH. That stays in the PiHerder image ([HAOS hosts](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/wiki/day-to-day/haos-hosts.md)).

**Plugin 0.2.4** (GitHub Release [`v0.2.4`](https://github.com/bjorngluck/piherder-ha/releases/tag/v0.2.4)). Needs a PiHerder on the **v1.6** train for container, service, and disk sensors. An older herder still shows Slice 1 (fleet + host + Visit); a 404 on `/inventory` or `/services` is ignored.

The Lovelace card **PiHerder fleet** (`custom:piherder-dashboard-card`) shows fleet CPU, memory, disk, and containers. Expand a host for chips to Host / Docker / Backups / Alerts / Audit. The HA **device page** has one **Visit** (the host). Slice 1b adds **disk %**, one sensor per container (running / image / uptime text), and one sensor per monitored service (up/down) on that same host device. They are status only. Token **`read`**. Poll reads stored snapshots. It never SSHs the fleet.

No start/stop, Move, Files, console, or OS apply from HA.

## Install

Full steps, with the card resource and what each HA screen means: **[Home Assistant → PiHerder](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/wiki/integrations/home-assistant.md)**.

The public docs site ([piherder-docs.hacknow.info](https://piherder-docs.hacknow.info/)) is built from PiHerder `main` and still shows **v1.5.0**. That site’s Home Assistant page is published when v1.6 merges. Until then, use the wiki file on `v1.6.0-dev` linked above.

1. In PiHerder: Settings → API management → token with **`read` only**. IP allowlist = this HA host. Token page: [API tokens](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/wiki/operations/api-tokens.md).
2. HACS → custom repositories → [bjorngluck/piherder-ha](https://github.com/bjorngluck/piherder-ha) → Integration.
3. Add **PiHerder**: base URL, `ph_…` token, TLS verify, poll interval. Wrong URL/token keeps the form filled.
4. Confirm fleet **Plugin** is **0.2.4**. The fleet **Version** sensor is the PiHerder app (still **1.5.0** until that app is tagged).

HACS does **not** auto-refresh custom repos. New GitHub Release: HACS → PiHerder → **⋮ → Redownload** → pick **`v0.2.4`** → **restart Home Assistant**. Reload of the config entry does not replace files.

## Fleet card

After restart, the integration copies the card JS to Home Assistant `config/www/`.

1. Dashboard **⋮ → Resources** — delete any `/api/piherder/…`, `?v=0.2.2`, or `?v=0.2.3` URL. Add **`/local/piherder-dashboard-card.js?v=0.2.4`** as **JavaScript module**. The card header shows the PiHerder logo from `/local/piherder-logo.png`.
2. Hard-refresh the browser (Ctrl+Shift+R).
3. Add card → **Manual**:

```yaml
type: custom:piherder-dashboard-card
```

“Custom element doesn’t exist” = stale resource URL, resource type is JavaScript instead of module, or HA was not restarted after Redownload.

CPU, memory, and disk numbers come from PiHerder **[System Info](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/wiki/day-to-day/system-info.md)** (a stored host snapshot, not live SSH). v1.6 persists those columns so this integration can poll the database without SSHing the fleet. Recreate PiHerder **web** (Alembic **045**), then the System Info refresh icon (or wait ~15 minutes). Empty bars mean the herder has no snapshot yet.

## Wiki

| Topic | Page |
|-------|------|
| Install, card, Visit, Slice 1b | [Home Assistant → PiHerder](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/wiki/integrations/home-assistant.md) |
| Why CPU/memory/disk are stored | [System Info](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/wiki/day-to-day/system-info.md) |
| `read` token and allowlist | [API tokens](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/wiki/operations/api-tokens.md) |
| Path 1, PiHerder managing HAOS | [HAOS hosts](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/wiki/day-to-day/haos-hosts.md) |
| Adding the host the card will list | [Add a server](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/wiki/day-to-day/add-server.md) |

Do not vendor this tree inside the PiHerder Docker image.

## Support

Optional. Nothing here is required to install the integration.

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-%231EAEDB?logo=githubsponsors&logoColor=fff&style=for-the-badge)](https://github.com/sponsors/bjorngluck)
&nbsp;
[![Buy me a coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=%E2%98%95&slug=bjorngluck&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://www.buymeacoffee.com/bjorngluck)

[github.com/sponsors/bjorngluck](https://github.com/sponsors/bjorngluck) · [buymeacoffee.com/bjorngluck](https://www.buymeacoffee.com/bjorngluck) · [Support the project](https://github.com/bjorngluck/piherder/blob/v1.6.0-dev/wiki/support.md)

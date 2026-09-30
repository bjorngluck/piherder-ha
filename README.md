# PiHerder for Home Assistant

[![Release](https://img.shields.io/badge/plugin-v0.4.2-green.svg)](https://github.com/bjorngluck/piherder-ha/releases)
[![PiHerder](https://img.shields.io/badge/PiHerder-v1.7.0-blue.svg)](https://github.com/bjorngluck/piherder/releases/tag/v1.7.0)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-41BDF5?logo=home-assistant&logoColor=fff)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-custom%20integration-orange.svg)](https://github.com/bjorngluck/piherder-ha)
[![Install guide](https://img.shields.io/badge/wiki-install%20steps-red.svg)](https://piherder-docs.hacknow.info/integrations/home-assistant/)
[![Sponsor](https://img.shields.io/badge/Sponsor-%231EAEDB?logo=githubsponsors&logoColor=fff&style=flat)](https://github.com/sponsors/bjorngluck)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-ffdd00?logo=buymeacoffee&logoColor=black&style=flat)](https://www.buymeacoffee.com/bjorngluck)

HACS integration: Home Assistant **observes** a [PiHerder](https://github.com/bjorngluck/piherder) fleet over `/api/v1`.

This is **not** PiHerder managing HAOS over SSH. That stays in the PiHerder image ([HAOS hosts](https://piherder-docs.hacknow.info/day-to-day/haos-hosts/)). Needs PiHerder **[v1.7.0](https://github.com/bjorngluck/piherder/releases/tag/v1.7.0)** for `host_reboot`. An older herder still shows the read-only fleet card.

**Plugin 0.4.2** is this build. HACS lists it only after the **v0.4.2** GitHub Release. A push to `main` without a `v*` tag leaves the previous release in the list. The card keeps the tab, the selected host, and open sections when it redraws. It targets PiHerder **[v1.7.0](https://github.com/bjorngluck/piherder/blob/v1.7.0/docs/RELEASE_v1.7.0.md)** or newer for the fleet card. Start and stop of one container need the v1.8 herder jobs `container_start` and `container_stop`. A 1.7 herder answers **400** for those two. A 404 on `/inventory` or `/services` from an older herder is ignored.

The Lovelace card is one module with **Fleet**, **Host**, and **Updates** tabs. A host strip picks the machine (a Raspberry Pi mark and an OS icon). Click memory, disk, or CPU load to open that sensor’s Home Assistant history. **Backup** is the face button. The other confirms are an **Actions** menu. **Containers** on the Host tab lists the last inventory. **Start** or **Stop** runs `docker compose` for that one service after a confirm. A container with no compose directory or service name has no button. A `read` token shows no job buttons. The older card names (`piherder-host-card`, `piherder-updates-card`, `piherder-resources-card`) still load. The HA **device page** has one **Visit** (the host). Sensors include disk %, memory %, CPU load, one sensor per container, and one sensor per monitored service. Poll reads stored snapshots. It never SSHs the fleet. When a job the plugin was watching leaves the active set, Home Assistant gets `piherder_job_completed`.

No Move, Files, console, or whole-project stop from HA. An automation can call `piherder.trigger_job` without the card dialog.

## Install

Full steps, with the card resource and what each HA screen means: **[Home Assistant → PiHerder](https://piherder-docs.hacknow.info/integrations/home-assistant/)**. Release: **[PiHerder v1.7.0](https://github.com/bjorngluck/piherder/releases/tag/v1.7.0)**.

1. In PiHerder: Settings → API management → token with **`read`**. Add **`jobs`** and **`edit`** if you want the confirm buttons and feature toggles. IP allowlist = this HA host. Token page: [API tokens](https://piherder-docs.hacknow.info/operations/api-tokens/).
2. HACS → custom repositories → [bjorngluck/piherder-ha](https://github.com/bjorngluck/piherder-ha) → Integration.
3. Add **PiHerder**: base URL, `ph_…` token, TLS verify, poll interval. Wrong URL/token keeps the form filled.
4. Confirm fleet **Plugin** is **0.4.2**. The fleet **Version** sensor is the PiHerder app (**1.7.0** until the herder tags 1.8.0).

HACS does **not** auto-refresh custom repos. Pick **v0.4.2**, then **restart Home Assistant**. Reload of the config entry does not replace the card file.

## Fleet card

After restart, the integration copies the card JS to Home Assistant `config/www/`.

1. Dashboard **⋮ → Resources** — delete any `/api/piherder/…`, `?v=0.2.2`, `?v=0.2.3`, `?v=0.2.4`, `?v=0.3.0`, `?v=0.4.0`, or `?v=0.4.1` URL. Add **`/local/piherder-dashboard-card.js?v=0.4.2`** as **JavaScript module**. The card header shows the PiHerder logo from `/local/piherder-logo.png`.
2. Hard-refresh the browser (Ctrl+Shift+R).
3. Add card → **Manual**:

```yaml
type: custom:piherder-dashboard-card
```

Host, updates, and resources cards use the same resource:

```yaml
type: custom:piherder-host-card
server_id: 1
```

```yaml
type: custom:piherder-updates-card
```

```yaml
type: custom:piherder-resources-card
server_id: 1
```

“Custom element doesn’t exist” = stale resource URL, resource type is JavaScript instead of module, or HA was not restarted after Redownload.

CPU, memory, and disk numbers come from PiHerder **[System Info](https://piherder-docs.hacknow.info/day-to-day/system-info/)** (a stored host snapshot, not live SSH). Recreate PiHerder **web** on **1.7.0**, then the System Info refresh icon (or wait ~15 minutes). Empty bars mean the herder has no snapshot yet. Click a stat to open Home Assistant’s history for that sensor. The thin sparkline uses the same history.

## Wiki

| Topic | Page |
|-------|------|
| PiHerder v1.7.0 | [Release](https://github.com/bjorngluck/piherder/releases/tag/v1.7.0) · [notes](https://github.com/bjorngluck/piherder/blob/v1.7.0/docs/RELEASE_v1.7.0.md) |
| Install, cards, Visit | [Home Assistant → PiHerder](https://piherder-docs.hacknow.info/integrations/home-assistant/) |
| Why CPU/memory/disk are stored | [System Info](https://piherder-docs.hacknow.info/day-to-day/system-info/) |
| `read` token and allowlist | [API tokens](https://piherder-docs.hacknow.info/operations/api-tokens/) |
| Path 1, PiHerder managing HAOS | [HAOS hosts](https://piherder-docs.hacknow.info/day-to-day/haos-hosts/) |
| Adding the host the card will list | [Add a server](https://piherder-docs.hacknow.info/day-to-day/add-server/) |

Do not vendor this tree inside the PiHerder Docker image.

## Support

Optional. Nothing here is required to install the integration.

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-%231EAEDB?logo=githubsponsors&logoColor=fff&style=for-the-badge)](https://github.com/sponsors/bjorngluck)
&nbsp;
[![Buy me a coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=%E2%98%95&slug=bjorngluck&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://www.buymeacoffee.com/bjorngluck)

[github.com/sponsors/bjorngluck](https://github.com/sponsors/bjorngluck) · [buymeacoffee.com/bjorngluck](https://www.buymeacoffee.com/bjorngluck) · [Support the project](https://piherder-docs.hacknow.info/support/)

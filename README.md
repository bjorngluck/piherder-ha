# PiHerder for Home Assistant

[![Release](https://img.shields.io/badge/plugin-v0.5.0-green.svg)](https://github.com/bjorngluck/piherder-ha/releases)
[![PiHerder](https://img.shields.io/badge/PiHerder-v1.9.0-blue.svg)](https://github.com/bjorngluck/piherder/blob/v1.9.0/docs/RELEASE_v1.9.0.md)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-41BDF5?logo=home-assistant&logoColor=fff)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-custom%20integration-orange.svg)](https://github.com/bjorngluck/piherder-ha)
[![Install guide](https://img.shields.io/badge/wiki-install%20steps-red.svg)](https://piherder-docs.hacknow.info/integrations/home-assistant/)
[![Sponsor](https://img.shields.io/badge/Sponsor-%231EAEDB?logo=githubsponsors&logoColor=fff&style=flat)](https://github.com/sponsors/bjorngluck)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-ffdd00?logo=buymeacoffee&logoColor=black&style=flat)](https://www.buymeacoffee.com/bjorngluck)

HACS integration: Home Assistant **observes** a [PiHerder](https://github.com/bjorngluck/piherder) fleet over `/api/v1`.

This is **not** PiHerder managing HAOS over SSH. That stays in the PiHerder image ([HAOS hosts](https://piherder-docs.hacknow.info/day-to-day/haos-hosts/)). Needs PiHerder **[v1.9.0](https://github.com/bjorngluck/piherder/blob/v1.9.0/docs/RELEASE_v1.9.0.md)**. Start, stop, restart, and update of one container have been on the herder since **v1.8.1**. `host_reboot` has been on the herder since **v1.7.0**. An older herder still shows the read-only fleet card.

**Plugin 0.5.0** is this build. HACS lists it only after the **v0.5.0** GitHub Release. A push to `main` without a `v*` tag leaves the previous release in the list. The Updates tab writes **OS updates** and **container updates** in full. A container that needs an image update has a gold name. A running service has **Stop** and **Restart**. A stopped service has **Start**. **Update** pulls and recreates that one service. **Stop project** runs `docker compose stop` for that compose directory. It does not remove containers or volumes. **Move** stops a project on this host, copies it, and starts it on another host. A finished Move has no Undo. **Files** lists, reads, writes, creates, renames, and deletes inside the fleet jail. The card still keeps the tab, the selected host, and open sections when it redraws. It targets PiHerder **[v1.9.0](https://github.com/bjorngluck/piherder/blob/v1.9.0/docs/RELEASE_v1.9.0.md)** for one-service actions, project stop, Files, and Move (`POST /api/v1/servers/{id}/moves`). A 1.7 herder answers **400** for the one-service jobs. A 404 on `/inventory` or `/services` from an older herder is ignored. [piherder-mcp](https://github.com/bjorngluck/piherder-mcp) does not grow a Move tool.

The Lovelace card is one module with **Fleet**, **Host**, and **Updates** tabs. A host strip picks the machine (a Raspberry Pi mark and an OS icon). Click memory, disk, or CPU load to open that sensor’s Home Assistant history. **Backup** is the face button. The other confirms are an **Actions** menu. **Containers** on the Host tab lists the last inventory. **Stop** and **Restart** are on a running service. **Start** is on a stopped one. **Update** is on a service with an image update. Each runs `docker compose` for that one service after a confirm. **Stop project** is one button per compose directory and asks first. **Move** is shown only when health says `service_migrate` is on, the token may run Docker jobs, and another host has Docker on. It asks first. **Files** is shown only when the token has `files`. A container with no compose directory or service name has no one-service button. A `read` token shows no job buttons. There is no console. The older card names (`piherder-host-card`, `piherder-updates-card`, `piherder-resources-card`) still load. The HA **device page** has one **Visit** (the host). Sensors include disk %, memory %, CPU load, one sensor per container, and one sensor per monitored service. Poll reads stored snapshots. It never SSHs the fleet. When a job the plugin was watching leaves the active set, Home Assistant gets `piherder_job_completed`.

## Poll only

There is no herder→HA webhook in this plugin.

PiHerder can POST alerts to a URL the operator set. That call sends a shared secret as `Authorization: Bearer` and `X-PiHerder-Webhook-Secret`. The body has no timestamp, nonce, or signature, so a captured request can be sent again. This plugin does not listen for it. Job completion stays `piherder_job_completed`, fired on the next poll when a watched job leaves the active set.

## Authz

| Action | Token | Confirm | Notes |
|--------|--------|---------|--------|
| One-service start, stop, restart, update | `jobs`, and `feature:docker` when the token is feature-restricted. Docker flag on the host. | Card dialog | `container_*` jobs. Other services stay up. |
| Stop project | Same as one-service | Card dialog and `confirm: true` on `piherder.trigger_job` | `docker_stack_stop`. `docker compose stop` for the compose directory. `docker_stack_down` and `docker_stack_remove` are rejected. |
| Move | `jobs`, and `feature:docker` when restricted. Docker flag on source and destination. Herder Move surface on. | Card dialog and `confirm: true` on `piherder.start_move` and on `POST /moves` | Source is left stopped. No undo. Hidden when health `service_migrate` is not true. |
| Files | `files` | Card dialog and `confirm: true` on delete | Fleet jail only. List, read, write, mkdir, rename, delete of a file or an empty directory. The card moves at most 64 KiB of text. No chmod, zip, or recursive delete. |
| Feature toggles | `edit`, plus `feature:*` when restricted | Card dialog when turning a flag off | |

An automation can call `piherder.trigger_job` without the card dialog. Project stop and Move still require `confirm: true` in the service data. A token without `jobs` cannot queue those jobs. A token without `files` has no Files tools.

## Install

Full steps, with the card resource and what each HA screen means: **[Home Assistant → PiHerder](https://piherder-docs.hacknow.info/integrations/home-assistant/)**. Release: **[PiHerder v1.9.0](https://github.com/bjorngluck/piherder/blob/v1.9.0/docs/RELEASE_v1.9.0.md)**.

1. In PiHerder: Settings → API management → token with **`read`**. Add **`jobs`** for confirms, **`files`** for the fleet jail, and **`edit`** for feature toggles. Add **`feature:docker`** only when this token should be limited to Docker. IP allowlist = this HA host. Token page: [API tokens](https://piherder-docs.hacknow.info/operations/api-tokens/).
2. HACS → custom repositories → [bjorngluck/piherder-ha](https://github.com/bjorngluck/piherder-ha) → Integration.
3. Add **PiHerder**: base URL, `ph_…` token, TLS verify, poll interval. Wrong URL/token keeps the form filled.
4. Confirm fleet **Plugin** is **0.5.0**. The fleet **Version** sensor is the PiHerder app (**1.9.0**).

HACS does **not** auto-refresh custom repos. Pick **v0.5.0**, then **restart Home Assistant**. Reload of the config entry does not replace the card file.

## Fleet card

After restart, the integration copies the card JS to Home Assistant `config/www/`.

1. Dashboard **⋮ → Resources** — delete any `/api/piherder/…`, `?v=0.2.2`, `?v=0.2.3`, `?v=0.2.4`, `?v=0.3.0`, `?v=0.4.0`, `?v=0.4.1`, `?v=0.4.2`, `?v=0.4.3`, or `?v=0.4.4` URL. Add **`/local/piherder-dashboard-card.js?v=0.5.0`** as **JavaScript module**. The card header shows the PiHerder logo from `/local/piherder-logo.png`.
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

CPU, memory, and disk numbers come from PiHerder **[System Info](https://piherder-docs.hacknow.info/day-to-day/system-info/)** (a stored host snapshot, not live SSH). Recreate PiHerder **web** on **1.9.0**, then the System Info refresh icon (or wait ~15 minutes). Empty bars mean the herder has no snapshot yet. Click a stat to open Home Assistant’s history for that sensor. The thin sparkline uses the same history.

## Test plan

1. Token with `read` only: no Start, Stop, Stop project, Move, or Files.
2. Token with `read` and `jobs`: Stop project asks, then posts `docker_stack_stop` with the compose directory and `confirm: true`. The service rejects that job when `confirm` is omitted. `docker_stack_down` is not a job type.
3. Health `service_migrate: true`, two Docker hosts, `jobs`: Move asks, then posts `start_move` with `confirm: true`. Health false or missing hides Move. A finished Move has no Undo button.
4. Token with `files`: Files loads the jail root, opens a directory, reads a text file, saves one, makes a folder, renames, and deletes only after a confirm. A path with `..` is rejected in the plugin before the request.
5. A watched job that disappears from the active set fires `piherder_job_completed`. No webhook endpoint is registered.

## Wiki

| Topic | Page |
|-------|------|
| PiHerder v1.9.0 | [Notes](https://github.com/bjorngluck/piherder/blob/v1.9.0/docs/RELEASE_v1.9.0.md). Tag [v1.9.0](https://github.com/bjorngluck/piherder/releases/tag/v1.9.0). Prior: [v1.8.1](https://github.com/bjorngluck/piherder/releases/tag/v1.8.1) |
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

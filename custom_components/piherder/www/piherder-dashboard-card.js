/* PiHerder Lovelace card. Fleet, host, and updates are tabs of one card.
   History is a thin sparkline; a click opens Home Assistant more-info. */
(function () {
  const JOBS = [
    ["backup", "Backup", "backup", true],
    ["retention", "Retention", "backup", true],
    ["os_update_check", "Check OS", "os", false],
    ["container_update_check", "Check containers", "docker", false],
    ["os_patch", "Patch OS", "os", true],
    ["container_patch", "Patch containers", "docker", true],
    ["host_reboot", "Restart host", "os", true],
  ];
  const FLAG = { backup: "backup", os: "os_patch", docker: "docker" };
  const COLORS = { memory: "#e60012", disk: "#00a651", cpu: "#f5c542", reboot: "#ff6b6b", backup: "#7eb6ff" };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function fmtBytes(n) {
    if (n == null || n === 0) return n === 0 ? "0" : "—";
    const u = ["B", "KiB", "MiB", "GiB", "TiB"];
    let v = Number(n);
    let i = 0;
    while (v >= 1024 && i < u.length - 1) {
      v /= 1024;
      i += 1;
    }
    return (i === 0 ? String(Math.round(v)) : v.toFixed(v >= 10 ? 0 : 1)) + " " + u[i];
  }

  function pct(used, total) {
    if (!total) return 0;
    return Math.max(0, Math.min(100, Math.round((100 * (used || 0)) / total)));
  }

  function tone(p) {
    if (p >= 90) return "hot";
    if (p >= 75) return "warm";
    return "ok";
  }

  function allowFeature(scopes, feature) {
    const found = new Set((scopes || []).map(String));
    const limited = [...found].some((s) => s.startsWith("feature:"));
    if (!limited) return true;
    return found.has("feature:" + feature);
  }

  function containerControl(scopes, features) {
    const found = new Set((scopes || []).map(String));
    if (!found.has("jobs") || !allowFeature(scopes, "docker")) return false;
    return !!(features || {}).docker;
  }

  function containersOf(data, serverId) {
    const hosts = (data && data.inventory) || [];
    const host = hosts.find((h) => String(h.server_id) === String(serverId));
    return ((host && host.containers) || [])
      .slice()
      .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")));
  }

  function actionsFor(scopes, features) {
    const found = new Set((scopes || []).map(String));
    if (!found.has("jobs")) return [];
    const flags = features || {};
    return JOBS.filter((row) => allowFeature(scopes, row[2]) && flags[FLAG[row[2]]]).map((row) => ({
      job_type: row[0],
      label: row[1],
      feature: row[2],
      confirm: row[3],
    }));
  }

  function togglesFor(scopes) {
    const found = new Set((scopes || []).map(String));
    if (!found.has("edit")) return [];
    return [
      ["backup", "Backup"],
      ["os", "OS patch"],
      ["docker", "Docker"],
    ]
      .filter((row) => allowFeature(scopes, row[0]))
      .map((row) => ({ feature: row[0], flag: FLAG[row[0]], label: row[1] }));
  }

  function historyPoints(rows, eid) {
    let list = [];
    if (Array.isArray(rows)) {
      list = rows[0] || [];
    } else if (rows && eid && rows[eid]) {
      list = rows[eid];
    }
    if (!Array.isArray(list)) return [];
    return list
      .map((row) => Number(row && row.s != null ? row.s : row && row.state))
      .filter((n) => !Number.isNaN(n));
  }

  function spark(points, color) {
    const nums = (points || []).map(Number).filter((n) => !Number.isNaN(n));
    if (!nums.length) return `<div class="ph-spark-empty">No history yet</div>`;
    const w = 280;
    const h = 28;
    const max = Math.max(...nums, 1);
    const min = Math.min(...nums, 0);
    const span = max - min || 1;
    const step = nums.length === 1 ? 0 : w / (nums.length - 1);
    const line = nums
      .map((v, i) => {
        const x = (i * step).toFixed(1);
        const y = (h - (h * (v - min)) / span).toFixed(1);
        return (i ? "L" : "M") + x + " " + y;
      })
      .join(" ");
    return `<svg class="ph-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
      <path d="${line}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"></path>
    </svg>`;
  }

  function icon(name) {
    return `<ha-icon icon="${esc(name || "mdi:server")}"></ha-icon>`;
  }

  function osLabel(server) {
    return server.os_pretty || server.os_display || server.os_type || "";
  }

  function metricEntity(hass, serverId, metric) {
    const states = (hass && hass.states) || {};
    for (const eid of Object.keys(states)) {
      const attrs = (states[eid] && states[eid].attributes) || {};
      if (String(attrs.server_id) === String(serverId) && attrs.piherder_metric === metric) return eid;
    }
    return null;
  }

  class PiHerderCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._kind = "fleet";
      this._tab = "fleet";
      this._history = {};
      this._note = "";
      this._menu = "";
      this._selectedId = null;
      this._focusStats = false;
    }

    setConfig(config) {
      this._config = config || {};
    }

    set hass(hass) {
      this._hass = hass;
      if (!this._wired) {
        this._wired = true;
        this._tick();
        this._timer = window.setInterval(() => this._tick(), 20000);
      }
    }

    disconnectedCallback() {
      if (this._timer) window.clearInterval(this._timer);
    }

    getCardSize() {
      if (this._tab === "fleet") return 8;
      if (this._tab === "updates") return 5;
      return 7;
    }

    async _tick() {
      if (!this._hass || !this._hass.connection) return;
      try {
        const res = await this._hass.connection.sendMessagePromise({ type: "piherder/snapshot" });
        this._origin = (res && res.origin) || "";
        this._data = (res && res.data) || {};
        this._error = "";
        await this._loadHistory();
        this._render();
      } catch (err) {
        this._error = String(err.message || err);
        this._render();
      }
    }

    _pinnedId() {
      const want = this._config && this._config.server_id;
      if (want == null || want === "") return null;
      return String(want);
    }

    _servers() {
      const rows = ((this._data && this._data.servers) || []).slice();
      const pin = this._pinnedId();
      const list = pin ? rows.filter((s) => String(s.id) === pin) : rows;
      return list.sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")));
    }

    _selected() {
      const rows = this._servers();
      if (!rows.length) return null;
      const id = this._pinnedId() || this._selectedId;
      return rows.find((s) => String(s.id) === String(id)) || rows[0];
    }

    _scopes() {
      const health = (this._data && this._data.health) || {};
      return health.scopes || [];
    }

    async _loadHistory() {
      if (!this._hass || !this._hass.callWS) return;
      const server = this._selected();
      if (!server) return;
      const end = new Date();
      const start = new Date(end.getTime() - 24 * 3600 * 1000);
      for (const metric of ["memory", "disk", "cpu"]) {
        const eid = metricEntity(this._hass, server.id, metric);
        const key = server.id + ":" + metric;
        if (!eid) {
          this._history[key] = [];
          continue;
        }
        try {
          const rows = await this._hass.callWS({
            type: "history/history_during_period",
            start_time: start.toISOString(),
            end_time: end.toISOString(),
            entity_ids: [eid],
            minimal_response: true,
            no_attributes: true,
          });
          this._history[key] = historyPoints(rows, eid);
        } catch (err) {
          this._history[key] = this._history[key] || [];
        }
      }
    }

    _more(server, metric) {
      const eid = metricEntity(this._hass, server.id, metric);
      if (!eid) return;
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          bubbles: true,
          composed: true,
          detail: { entityId: eid },
        })
      );
    }

    async _act(server, action) {
      const name = server.name || server.hostname || "this host";
      if (action.confirm) {
        const text =
          action.job_type === "host_reboot"
            ? "Restart " +
              name +
              "? This reboots the machine. It will not start if a patch or backup is already running."
            : action.label + " on " + name + "?";
        if (!window.confirm(text)) return;
      }
      try {
        await this._hass.callService("piherder", "trigger_job", {
          server_id: server.id,
          job_type: action.job_type,
        });
        this._note = action.label + " queued";
        this._menu = "";
      } catch (err) {
        this._note = String(err.message || err);
      }
      this._render();
    }

    async _container(server, btn) {
      const act = btn.getAttribute("data-ctr-act") === "stop" ? "stop" : "start";
      const name = btn.getAttribute("data-ctr-name") || "this container";
      const host = server.name || server.hostname || "this host";
      const verb = act === "stop" ? "Stop" : "Start";
      const text =
        verb +
        " " +
        name +
        " on " +
        host +
        "? This runs docker compose " +
        act +
        " for that service. Other containers in the project stay as they are.";
      if (!window.confirm(text)) return;
      try {
        await this._hass.callService("piherder", "trigger_job", {
          server_id: server.id,
          job_type: act === "stop" ? "container_stop" : "container_start",
          source_filter: btn.getAttribute("data-ctr-path"),
          service: btn.getAttribute("data-ctr-svc"),
        });
        this._note = verb + " " + name + " queued";
      } catch (err) {
        this._note = String(err.message || err);
      }
      this._render();
    }

    _containers(server) {
      const rows = containersOf(this._data, server.id);
      if (!rows.length) return "";
      const allow = containerControl(this._scopes(), server.features);
      const body = rows
        .map((c) => {
          const name = c.name || c.service || "container";
          const state = c.running ? "running" : c.state || "exited";
          const path = String(c.path || "").trim();
          const service = String(c.service || "").trim();
          const act = c.running ? "stop" : "start";
          const btn =
            allow && path && service
              ? `<button type="button" data-ctr-act="${act}" data-ctr-path="${esc(path)}" data-ctr-svc="${esc(
                  service
                )}" data-ctr-name="${esc(name)}">${c.running ? "Stop" : "Start"}</button>`
              : "";
          return `<div class="ph-ctr"><span class="ph-ctr-name">${esc(name)}</span><span class="ph-ctr-state">${esc(
            state
          )}</span>${btn}</div>`;
        })
        .join("");
      return `<details class="ph-features"><summary>Containers</summary><div class="ph-ctr-list">${body}</div></details>`;
    }

    async _toggle(server, toggle) {
      const flags = server.features || {};
      const on = !!flags[toggle.flag];
      const next = !on;
      const name = server.name || "this host";
      if (on && !window.confirm("Turn off " + toggle.label + " on " + name + "?")) return;
      try {
        await this._hass.callService("piherder", "set_features", {
          server_id: server.id,
          [toggle.flag]: next,
        });
        this._note = toggle.label + (next ? " on" : " off");
      } catch (err) {
        this._note = String(err.message || err);
      }
      this._render();
    }

    _styles() {
      return `
        :host { display:block; }
        .ph {
          background: var(--ha-card-background, var(--card-background-color, #1c1c1c));
          border-radius: var(--ha-card-border-radius, 12px);
          border: 1px solid var(--divider-color, #333);
          padding: 14px 16px 12px;
          color: var(--primary-text-color, #eee);
          font: 14px/1.4 var(--ha-font-family-body, system-ui, sans-serif);
        }
        .ph-head { display:flex; align-items:center; gap:10px; margin: 0 0 10px; }
        .ph-logo { width: 36px; height: 36px; border-radius: 8px; flex-shrink: 0; background: #fff; }
        .ph-title { font-weight: 650; font-size: 1.05rem; margin: 0; letter-spacing: -0.02em; }
        .ph-sub { font-size: 0.72rem; opacity: 0.65; display:flex; align-items:center; gap:4px; }
        .ph-tabs { display:flex; gap:6px; margin: 0 0 12px; }
        .ph-tab {
          border: 0; border-radius: 999px; padding: 5px 12px; font: inherit; font-size: 0.78rem; font-weight: 650;
          cursor: pointer; color: inherit; background: transparent;
        }
        .ph-tab.on { background: #e60012; color: #fff; }
        .ph-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(92px, 1fr)); gap: 8px; margin-bottom: 12px; }
        .ph-tile { background: color-mix(in srgb, #00a651 14%, transparent); border-radius: 10px; padding: 8px; }
        .ph-tile .n { font-size: 1.2rem; font-weight: 700; }
        .ph-tile .l { font-size: 0.68rem; text-transform: uppercase; opacity: 0.7; }
        .ph-strip { display:flex; gap:8px; overflow-x:auto; padding-bottom: 8px; margin-bottom: 8px; }
        .ph-host, .ph-row {
          display:flex; align-items:center; gap:10px; width:100%;
          background: none; border: 0; border-top: 1px solid var(--divider-color, #333);
          color: inherit; font: inherit; text-align: left; padding: 10px 2px; cursor: pointer;
        }
        .ph-strip .ph-host {
          border: 1px solid var(--divider-color, #333); border-radius: 12px; padding: 8px 10px; width: auto; min-width: 148px;
        }
        .ph-host.on, .ph-row:hover, .ph-host:hover { background: color-mix(in srgb, #00a651 12%, transparent); }
        .ph-dev { position: relative; width: 28px; height: 28px; flex-shrink: 0; }
        .ph-dev ha-icon { --mdc-icon-size: 26px; width: 26px; height: 26px; }
        .ph-mark {
          position: absolute; right: -4px; bottom: -4px; min-width: 14px; padding: 0 3px;
          border-radius: 6px; background: #e60012; color: #fff; font-size: 0.62rem; font-weight: 750; line-height: 1.3; text-align: center;
        }
        .ph-host-name { font-weight: 650; display:block; }
        .ph-host-meta { margin-left: auto; opacity: 0.6; font-size: 0.78rem; white-space: nowrap; }
        .ph-sub ha-icon { --mdc-icon-size: 14px; width: 14px; height: 14px; }
        .ph-metric {
          display:block; width:100%; margin: 8px 0; padding: 4px 2px; text-align:left;
          background: none; border: 0; color: inherit; font: inherit; cursor: pointer; border-radius: 8px;
        }
        .ph-metric:hover { background: color-mix(in srgb, var(--primary-text-color) 6%, transparent); }
        .ph-metric:disabled { cursor: default; }
        .ph-metric-h { display:flex; justify-content:space-between; font-size: 0.8rem; opacity: 0.9; margin-bottom: 4px; }
        .ph-bar { height: 8px; border-radius: 99px; background: color-mix(in srgb, var(--primary-text-color) 12%, transparent); overflow:hidden; }
        .ph-bar-fill { height:100%; border-radius: 99px; }
        .ph-bar-fill.ok { background: #3dd68c; }
        .ph-bar-fill.warm { background: #f5c542; }
        .ph-bar-fill.hot { background: #ff6b6b; }
        .ph-spark { width: 100%; height: 28px; display:block; margin-top: 4px; }
        .ph-spark-empty { font-size: 0.72rem; opacity: 0.55; margin-top: 2px; }
        .ph-actions { display:flex; flex-wrap:wrap; gap: 6px; margin-top: 10px; align-items: center; }
        button.ph-btn, a.ph-btn {
          border: 0; border-radius: 999px; padding: 6px 12px; font: inherit; font-size: 0.78rem; font-weight: 650;
          cursor: pointer; color: #fff; background: #e60012; text-decoration: none;
        }
        button.ph-btn.quiet, a.ph-btn.quiet { background: color-mix(in srgb, #00a651 70%, #111); }
        .ph-menu { display:flex; flex-direction:column; gap: 2px; margin-top: 6px; padding: 6px; border-radius: 10px; background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); }
        .ph-menu button, .ph-menu a {
          background: none; border: 0; color: inherit; font: inherit; text-align: left; padding: 6px 8px; border-radius: 8px;
          cursor: pointer; text-decoration: none;
        }
        .ph-menu button:hover, .ph-menu a:hover { background: color-mix(in srgb, #e60012 22%, transparent); }
        details.ph-features { margin-top: 8px; }
        details.ph-features summary { cursor: pointer; font-size: 0.8rem; opacity: 0.8; }
        .ph-toggles { display:flex; flex-wrap:wrap; gap: 6px; margin-top: 6px; }
        button.ph-tog { background: transparent; color: inherit; border: 1px solid var(--divider-color, #444); border-radius: 999px; padding: 5px 10px; font: inherit; font-size: 0.78rem; cursor: pointer; }
        button.ph-tog.on { border-color: #00a651; color: #00a651; }
        .ph-ctr { display:flex; align-items:center; gap: 8px; padding: 4px 0; }
        .ph-ctr-name { font-weight: 650; }
        .ph-ctr-state { opacity: 0.7; font-size: 0.78rem; margin-right: auto; }
        .ph-ctr button {
          border: 0; border-radius: 999px; padding: 4px 10px; font: inherit; font-size: 0.75rem; font-weight: 650;
          cursor: pointer; color: #fff; background: color-mix(in srgb, #00a651 70%, #111);
        }
        .ph-pill { display:inline-block; margin-left: 8px; padding: 1px 8px; border-radius: 999px; background:#e60012; color:#fff; font-size: 0.7rem; font-weight: 700; }
        .ph-note { margin-top: 8px; font-size: 0.8rem; opacity: 0.85; }
        .ph-empty, .ph-err { opacity: 0.7; }
        .ph-err { color: #ff6b6b; opacity: 1; }
        .ph-count { font-variant-numeric: tabular-nums; }
        .ph-count.warn { color: #f5c542; font-weight: 700; }
      `;
    }

    _hostFace(server, extra) {
      const mark = server.device_mark ? `<span class="ph-mark">${esc(server.device_mark)}</span>` : "";
      return `<span class="ph-dev">${icon(server.device_icon || "mdi:server")}${mark}</span>
        <span>
          <span class="ph-host-name">${esc(server.name || server.hostname || "Host")}</span>
          <span class="ph-sub">${icon(server.os_icon || "mdi:linux")} ${esc(osLabel(server))}</span>
        </span>
        ${extra || ""}`;
    }

    _links(server) {
      const id = server.id;
      const f = server.features || {};
      const base = (this._origin || "").replace(/\/$/, "");
      return [
        ["Host", base + "/servers/" + id],
        f.docker ? ["Docker", base + "/servers/" + id + "/docker"] : null,
        f.backup ? ["Backups", base + "/servers/" + id + "/backups"] : null,
        ["Alerts", base + "/notifications?server_id=" + id],
        ["Audit", base + "/audit?server_id=" + id],
      ].filter(Boolean);
    }

    _metricButton(server, metric, label, used, total, extra) {
      const key = server.id + ":" + metric;
      const eid = metricEntity(this._hass, server.id, metric);
      const p = metric === "cpu" ? (total ? Math.min(100, Math.round((100 * (used || 0)) / total)) : 0) : pct(used, total);
      return `<button type="button" class="ph-metric" data-metric="${metric}" ${eid ? "" : "disabled"}>
        <div class="ph-metric-h"><span>${esc(label)}</span><span>${extra}</span></div>
        <div class="ph-bar"><div class="ph-bar-fill ${tone(p)}" style="width:${p}%"></div></div>
        ${spark(this._history[key], COLORS[metric])}
      </button>`;
    }

    _fleet() {
      const summary = (this._data && this._data.summary) || {};
      const servers = this._servers();
      const memP = pct(summary.memory_used_bytes, summary.memory_total_bytes);
      const diskP = pct(summary.disk_used_bytes, summary.disk_total_bytes);
      const rows = servers
        .map(
          (s) =>
            `<button type="button" class="ph-row" data-host="${s.id}" data-goto="host">${this._hostFace(
              s,
              `<span class="ph-host-meta">${s.container_count != null ? esc(s.container_count) + " ctr" : ""}</span>`
            )}</button>`
        )
        .join("");
      return `<div class="ph-grid">
          <div class="ph-tile"><div class="n">${summary.hosts ?? servers.length}</div><div class="l">Hosts</div></div>
          <div class="ph-tile"><div class="n">${summary.cpu_cores ?? "—"}</div><div class="l">CPU cores</div></div>
          <div class="ph-tile"><div class="n">${summary.containers ?? "—"}</div><div class="l">Containers</div></div>
          <div class="ph-tile"><div class="n">${memP}%</div><div class="l">Memory</div></div>
          <div class="ph-tile"><div class="n">${diskP}%</div><div class="l">Disk</div></div>
        </div>
        <div class="ph-metric" style="cursor:default">
          <div class="ph-metric-h"><span>Memory</span><span>${fmtBytes(summary.memory_used_bytes)} / ${fmtBytes(summary.memory_total_bytes)}</span></div>
          <div class="ph-bar"><div class="ph-bar-fill ${tone(memP)}" style="width:${memP}%"></div></div>
        </div>
        <div class="ph-metric" style="cursor:default">
          <div class="ph-metric-h"><span>Disk</span><span>${fmtBytes(summary.disk_used_bytes)} / ${fmtBytes(summary.disk_total_bytes)}</span></div>
          <div class="ph-bar"><div class="ph-bar-fill ${tone(diskP)}" style="width:${diskP}%"></div></div>
        </div>
        <div class="ph-hosts">${rows || `<div class="ph-empty">No hosts in snapshot</div>`}</div>`;
    }

    _host() {
      const server = this._selected();
      if (!server) return `<div class="ph-empty">No host in this snapshot</div>`;
      const pin = this._pinnedId();
      const strip = pin
        ? ""
        : `<div class="ph-strip">${this._servers()
            .map(
              (s) =>
                `<button type="button" class="ph-host ${String(s.id) === String(server.id) ? "on" : ""}" data-host="${s.id}">${this._hostFace(s)}</button>`
            )
            .join("")}</div>`;
      const load = server.cpu_load != null ? Number(server.cpu_load) : 0;
      const cores = Number(server.cpu_cores || 0);
      const actions = actionsFor(this._scopes(), server.features);
      const backup = actions.find((a) => a.job_type === "backup");
      const menu = actions.filter((a) => a.job_type !== "backup");
      const toggles = togglesFor(this._scopes());
      const links = this._links(server);
      const hostUrl = links.length ? links[0][1] : "#";
      const moreLinks = links.slice(1);
      const flags = server.features || {};
      const menuOpen = this._menu === "actions" && menu.length;
      const linkOpen = this._menu === "links" && moreLinks.length;
      return `${strip}
        <div class="ph-title">${esc(server.name || server.hostname || "Host")}${
          server.reboot_pending ? `<span class="ph-pill">Reboot pending</span>` : ""
        }</div>
        <div class="ph-sub">${icon(server.os_icon || "mdi:linux")} ${esc(osLabel(server))}</div>
        <div class="ph-actions">
          ${
            metricEntity(this._hass, server.id, "reboot")
              ? `<button type="button" class="ph-btn quiet" data-metric="reboot">${server.reboot_pending ? "Reboot pending" : "Reboot"}</button>`
              : ""
          }
          ${
            metricEntity(this._hass, server.id, "backup")
              ? `<button type="button" class="ph-btn quiet" data-metric="backup">Last backup</button>`
              : ""
          }
        </div>
        <div id="ph-stats">
          ${this._metricButton(
            server,
            "memory",
            "Memory",
            server.memory_used_bytes,
            server.memory_total_bytes,
            fmtBytes(server.memory_used_bytes) + " / " + fmtBytes(server.memory_total_bytes)
          )}
          ${this._metricButton(
            server,
            "disk",
            "Disk",
            server.disk_used_bytes,
            server.disk_total_bytes,
            fmtBytes(server.disk_used_bytes) + " / " + fmtBytes(server.disk_total_bytes)
          )}
          ${this._metricButton(
            server,
            "cpu",
            "CPU load",
            load,
            cores || 1,
            cores ? load.toFixed(2) + " / " + cores + " cores" : load ? load.toFixed(2) : "—"
          )}
        </div>
        <div class="ph-actions">
          ${backup ? `<button type="button" class="ph-btn" data-job="backup">Backup</button>` : ""}
          ${
            menu.length
              ? `<button type="button" class="ph-btn quiet" data-menu="actions">Actions</button>`
              : ""
          }
          <a class="ph-btn quiet" href="${esc(hostUrl)}" target="_blank" rel="noopener">Open host</a>
          ${
            moreLinks.length
              ? `<button type="button" class="ph-btn quiet" data-menu="links" aria-label="More links">Also</button>`
              : ""
          }
        </div>
        ${
          menuOpen
            ? `<div class="ph-menu">${menu
                .map((a) => `<button type="button" data-job="${a.job_type}">${esc(a.label)}</button>`)
                .join("")}</div>`
            : ""
        }
        ${
          linkOpen
            ? `<div class="ph-menu">${moreLinks
                .map(([n, href]) => `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(n)}</a>`)
                .join("")}</div>`
            : ""
        }
        ${
          toggles.length
            ? `<details class="ph-features"><summary>Features</summary><div class="ph-toggles">${toggles
                .map(
                  (t) =>
                    `<button type="button" class="ph-tog ${flags[t.flag] ? "on" : ""}" data-flag="${t.flag}">${esc(t.label)}</button>`
                )
                .join("")}</div></details>`
            : ""
        }
        ${this._containers(server)}`;
    }

    _updates() {
      const servers = this._servers();
      if (!servers.length) return `<div class="ph-empty">No host in this snapshot</div>`;
      return servers
        .map((s) => {
          const os = Number(s.os_updates_count || 0);
          const ctr = Number(s.container_updates_count || 0);
          return `<button type="button" class="ph-row" data-host="${s.id}" data-goto="host">${this._hostFace(
            s,
            `<span class="ph-host-meta"><span class="ph-count ${os ? "warn" : ""}">${os} OS</span> · <span class="ph-count ${
              ctr ? "warn" : ""
            }">${ctr} ctr</span>${s.reboot_pending ? " · reboot" : ""}</span>`
          )}</button>`;
        })
        .join("");
    }

    _body() {
      if (this._tab === "updates") return this._updates();
      if (this._tab === "host") return this._host();
      return this._fleet();
    }

    _render() {
      const titles = { fleet: "Fleet", host: "Host", updates: "Updates" };
      const tabs = ["fleet", "host", "updates"]
        .map(
          (tab) =>
            `<button type="button" class="ph-tab ${this._tab === tab ? "on" : ""}" data-tab="${tab}">${titles[tab]}</button>`
        )
        .join("");
      this.shadowRoot.innerHTML = `
        <style>${this._styles()}</style>
        <div class="ph">
          <div class="ph-head">
            <img class="ph-logo" src="/local/piherder-logo.png" alt="" width="36" height="36" />
            <div>
              <div class="ph-title">PiHerder</div>
              <div class="ph-sub">${titles[this._tab] || "Fleet"}</div>
            </div>
          </div>
          <div class="ph-tabs">${tabs}</div>
          ${this._error ? `<div class="ph-err">${esc(this._error)}</div>` : ""}
          ${!this._data && !this._error ? `<div class="ph-empty">Waiting for PiHerder…</div>` : this._body()}
          ${this._note ? `<div class="ph-note">${esc(this._note)}</div>` : ""}
        </div>
      `;
      this.shadowRoot.querySelectorAll("[data-tab]").forEach((btn) => {
        btn.addEventListener("click", () => {
          this._tab = btn.getAttribute("data-tab");
          this._menu = "";
          this._render();
        });
      });
      this.shadowRoot.querySelectorAll("[data-host]").forEach((btn) => {
        btn.addEventListener("click", () => {
          this._selectedId = btn.getAttribute("data-host");
          if (btn.getAttribute("data-goto") === "host") this._tab = "host";
          this._menu = "";
          this._loadHistory().then(() => this._render());
        });
      });
      this.shadowRoot.querySelectorAll("[data-menu]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const name = btn.getAttribute("data-menu");
          this._menu = this._menu === name ? "" : name;
          this._render();
        });
      });
      this.shadowRoot.querySelectorAll("[data-metric]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const server = this._selected();
          if (server) this._more(server, btn.getAttribute("data-metric"));
        });
      });
      this.shadowRoot.querySelectorAll("[data-job]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const server = this._selected();
          const action = actionsFor(this._scopes(), server && server.features).find(
            (a) => a.job_type === btn.getAttribute("data-job")
          );
          if (server && action) this._act(server, action);
        });
      });
      this.shadowRoot.querySelectorAll("[data-ctr-act]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const server = this._selected();
          if (server) this._container(server, btn);
        });
      });
      this.shadowRoot.querySelectorAll("[data-flag]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const server = this._selected();
          const toggle = togglesFor(this._scopes()).find((t) => t.flag === btn.getAttribute("data-flag"));
          if (server && toggle) this._toggle(server, toggle);
        });
      });
      if (this._focusStats && this._data) {
        const stats = this.shadowRoot.getElementById("ph-stats");
        if (stats && this._tab === "host") stats.scrollIntoView({ block: "nearest" });
        this._focusStats = false;
      }
    }
  }

  function define(tag, kind, name, description, stub) {
    class Card extends PiHerderCard {
      constructor() {
        super();
        this._kind = kind;
        this._tab = kind === "updates" ? "updates" : kind === "fleet" ? "fleet" : "host";
        this._focusStats = kind === "resources";
      }
      static getStubConfig() {
        return stub || {};
      }
    }
    if (!customElements.get(tag)) customElements.define(tag, Card);
    window.customCards = window.customCards || [];
    if (!window.customCards.some((c) => c.type === tag)) {
      window.customCards.push({ type: tag, name: name, description: description, preview: true });
    }
  }

  define(
    "piherder-dashboard-card",
    "fleet",
    "PiHerder fleet",
    "Fleet totals. Open a host for bars, history, and actions"
  );
  define(
    "piherder-host-card",
    "host",
    "PiHerder host",
    "One host strip, bars, and a short action menu",
    { server_id: 1 }
  );
  define(
    "piherder-updates-card",
    "updates",
    "PiHerder updates",
    "One row per host for OS and container counts"
  );
  define(
    "piherder-resources-card",
    "resources",
    "PiHerder resources",
    "Host bars. Click a stat for Home Assistant history",
    { server_id: 1 }
  );
})();

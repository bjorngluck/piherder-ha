/* PiHerder fleet Lovelace card — totals, bars, expand host, real http links. */
(function () {
  const CARD = "piherder-dashboard-card";

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

  function bar(label, used, total, extra) {
    const p = pct(used, total);
    return `<div class="ph-metric">
      <div class="ph-metric-h"><span>${label}</span><span>${extra || (total ? fmtBytes(used) + " / " + fmtBytes(total) : "—")}</span></div>
      <div class="ph-bar"><div class="ph-bar-fill ${tone(p)}" style="width:${p}%"></div></div>
    </div>`;
  }

  function links(origin, s) {
    const id = s.id;
    const f = s.features || {};
    const base = (origin || "").replace(/\/$/, "");
    const items = [
      ["Host", `${base}/servers/${id}`],
      f.docker ? ["Docker", `${base}/servers/${id}/docker`] : null,
      f.backup ? ["Backups", `${base}/servers/${id}/backups`] : null,
      ["Alerts", `${base}/notifications?server_id=${id}`],
      ["Audit", `${base}/audit?server_id=${id}`],
    ].filter(Boolean);
    return `<div class="ph-links">${items
      .map(
        ([n, href]) =>
          `<a class="ph-chip" href="${href}" target="_blank" rel="noopener">${n}</a>`
      )
      .join("")}</div>`;
  }

  class PiHerderDashboardCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._open = {};
      this._data = null;
      this._origin = "";
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
      return 8;
    }

    async _tick() {
      if (!this._hass || !this._hass.connection) return;
      try {
        const res = await this._hass.connection.sendMessagePromise({
          type: "piherder/snapshot",
        });
        this._origin = (res && res.origin) || "";
        this._data = (res && res.data) || {};
        this._render();
      } catch (err) {
        this._error = String(err.message || err);
        this._render();
      }
    }

    _toggle(id) {
      this._open[id] = !this._open[id];
      this._render();
    }

    _render() {
      const summary = (this._data && this._data.summary) || {};
      const servers = (this._data && this._data.servers) || [];
      const memP = pct(summary.memory_used_bytes, summary.memory_total_bytes);
      const diskP = pct(summary.disk_used_bytes, summary.disk_total_bytes);
      const hosts = servers
        .slice()
        .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")));

      const hostRows = hosts
        .map((s) => {
          const id = s.id;
          const open = !!this._open[id];
          const load = Number(s.cpu_load || 0);
          const cores = Number(s.cpu_cores || 0);
          const cpuP = cores ? Math.min(100, Math.round((100 * load) / cores)) : 0;
          return `<div class="ph-host ${open ? "open" : ""}">
            <button type="button" class="ph-host-h" data-id="${id}">
              <span class="ph-dot ${s.reboot_pending ? "hot" : s.alerts_open ? "warm" : "ok"}"></span>
              <span class="ph-host-name">${this._esc(s.name || s.hostname || "Host " + id)}</span>
              <span class="ph-host-meta">${s.container_count != null ? s.container_count + " ctr" : ""}</span>
              <span class="ph-chev">${open ? "▾" : "▸"}</span>
            </button>
            ${
              open
                ? `<div class="ph-host-b">
                <div class="ph-muted">${this._esc(s.hardware || "")} · ${this._esc(s.os_pretty || s.os_display || s.os_type || "")}</div>
                ${bar("CPU", load, cores || 1, cores ? load.toFixed(2) + " / " + cores + " cores" : "—")}
                ${bar("Memory", s.memory_used_bytes, s.memory_total_bytes)}
                ${bar("Disk", s.disk_used_bytes, s.disk_total_bytes)}
                ${links(this._origin, s)}
              </div>`
                : ""
            }
          </div>`;
        })
        .join("");

      this.shadowRoot.innerHTML = `
        <style>
          :host { display:block; }
          .ph {
            background: var(--ha-card-background, var(--card-background-color, #1c1c1c));
            border-radius: var(--ha-card-border-radius, 12px);
            border: 1px solid var(--divider-color, #333);
            padding: 14px 16px 10px;
            color: var(--primary-text-color, #eee);
            font: 14px/1.4 var(--ha-font-family-body, system-ui, sans-serif);
          }
          .ph-head { display:flex; align-items:center; gap:10px; margin: 0 0 12px; }
          .ph-logo { width: 36px; height: 36px; border-radius: 8px; flex-shrink: 0; background: #fff; }
          .ph-title { font-weight: 650; font-size: 1.05rem; margin: 0; letter-spacing: -0.02em; }
          .ph-sub { font-size: 0.72rem; opacity: 0.6; letter-spacing: 0.02em; }
          .ph-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(92px, 1fr)); gap: 8px; margin-bottom: 12px; }
          .ph-tile {
            background: color-mix(in srgb, var(--primary-color, #4caf50) 12%, transparent);
            border-radius: 10px; padding: 10px 10px 8px;
          }
          .ph-tile .n { font-size: 1.25rem; font-weight: 700; letter-spacing: -0.03em; }
          .ph-tile .l { font-size: 0.7rem; text-transform: uppercase; opacity: 0.7; letter-spacing: 0.04em; }
          .ph-metric { margin: 8px 0; }
          .ph-metric-h { display:flex; justify-content:space-between; font-size: 0.8rem; opacity: 0.85; margin-bottom: 4px; }
          .ph-bar { height: 8px; border-radius: 99px; background: color-mix(in srgb, var(--primary-text-color) 12%, transparent); overflow:hidden; }
          .ph-bar-fill { height:100%; border-radius: 99px; }
          .ph-bar-fill.ok { background: #3dd68c; }
          .ph-bar-fill.warm { background: #f5c542; }
          .ph-bar-fill.hot { background: #ff6b6b; }
          .ph-host { border-top: 1px solid var(--divider-color, #333); }
          .ph-host-h {
            width:100%; display:flex; align-items:center; gap:8px;
            background:none; border:0; color:inherit; font: inherit; padding: 10px 2px; cursor:pointer; text-align:left;
          }
          .ph-host-name { font-weight: 600; flex: 1; }
          .ph-host-meta { opacity: 0.55; font-size: 0.8rem; }
          .ph-dot { width:8px; height:8px; border-radius:50%; background:#3dd68c; flex-shrink:0; }
          .ph-dot.warm { background:#f5c542; }
          .ph-dot.hot { background:#ff6b6b; }
          .ph-host-b { padding: 0 4px 12px 18px; }
          .ph-muted { font-size: 0.78rem; opacity: 0.65; margin-bottom: 6px; }
          .ph-links { display:flex; flex-wrap:wrap; gap:6px; margin-top: 8px; }
          .ph-chip {
            display:inline-block; padding: 4px 10px; border-radius: 999px;
            background: color-mix(in srgb, var(--primary-color, #4caf50) 22%, transparent);
            color: var(--primary-text-color, #eee); text-decoration:none; font-size: 0.78rem; font-weight: 600;
          }
          .ph-chip:hover { filter: brightness(1.15); }
          .ph-err { color: #ff6b6b; font-size: 0.9rem; }
          .ph-empty { opacity: 0.6; padding: 8px 0; }
        </style>
        <div class="ph">
          <div class="ph-head">
            <img class="ph-logo" src="/local/piherder-logo.png" alt="" width="36" height="36" />
            <div>
              <div class="ph-title">PiHerder</div>
              <div class="ph-sub">Fleet</div>
            </div>
          </div>
          ${
            this._error
              ? `<div class="ph-err">${this._esc(this._error)}</div>`
              : ""
          }
          ${
            !this._data && !this._error
              ? `<div class="ph-empty">Waiting for PiHerder…</div>`
              : `<div class="ph-grid">
                  <div class="ph-tile"><div class="n">${summary.hosts ?? hosts.length}</div><div class="l">Hosts</div></div>
                  <div class="ph-tile"><div class="n">${summary.cpu_cores ?? "—"}</div><div class="l">CPU cores</div></div>
                  <div class="ph-tile"><div class="n">${summary.containers ?? "—"}</div><div class="l">Containers</div></div>
                  <div class="ph-tile"><div class="n">${memP}%</div><div class="l">Memory</div></div>
                  <div class="ph-tile"><div class="n">${diskP}%</div><div class="l">Disk</div></div>
                </div>
                ${bar("Memory", summary.memory_used_bytes, summary.memory_total_bytes)}
                ${bar("Disk", summary.disk_used_bytes, summary.disk_total_bytes)}
                <div class="ph-hosts">${hostRows || `<div class="ph-empty">No hosts in snapshot</div>`}</div>`
          }
        </div>
      `;
      this.shadowRoot.querySelectorAll(".ph-host-h").forEach((btn) => {
        btn.addEventListener("click", () => this._toggle(btn.getAttribute("data-id")));
      });
    }

    _esc(s) {
      return String(s || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/"/g, "&quot;");
    }

    static getStubConfig() {
      return {};
    }
  }

if (!customElements.get(CARD)) {
  customElements.define(CARD, PiHerderDashboardCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === CARD)) {
  window.customCards.push({
    type: CARD,
    name: "PiHerder fleet",
    description: "Fleet totals, expandable hosts, links into PiHerder",
    preview: true,
  });
}
})();

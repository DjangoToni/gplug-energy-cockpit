const GPLUG_CARD_VERSION = "0.3.3";

class GPlugEnergyCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._history = [];
    this._lastPoint = "";
  }

  static getStubConfig() { return {}; }
  static getGridOptions() { return { columns: 12, rows: 8, min_columns: 6, min_rows: 5 }; }
  getCardSize() { return 8; }

  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._capture();
    this._render();
  }

  _metrics() {
    if (!this._hass) return {};
    let anchor = this._config.entity ? this._hass.states[this._config.entity] : null;
    if (!anchor) {
      anchor = Object.values(this._hass.states).find((state) => state.attributes?.metric_key === "meter_status" && state.attributes?.cockpit_group_id);
    }
    if (!anchor) return {};
    const group = anchor.attributes.cockpit_group_id;
    const metrics = { _anchor: anchor };
    Object.values(this._hass.states).forEach((state) => {
      if (state.attributes?.cockpit_group_id === group) metrics[state.attributes.metric_key] = state;
    });
    return metrics;
  }

  _num(state) {
    if (!state || ["unknown", "unavailable"].includes(state.state)) return null;
    const number = Number(state.state);
    return Number.isFinite(number) ? number : null;
  }

  _format(state, digits) {
    const value = this._num(state);
    if (value === null) return "—";
    const unit = state.attributes.unit_of_measurement || "";
    const precision = digits ?? (unit === "kW" && Math.abs(value) < 1 ? 3 : Math.abs(value) < 10 ? 2 : Math.abs(value) < 100 ? 1 : 0);
    return `${value.toLocaleString(undefined, { minimumFractionDigits: precision, maximumFractionDigits: precision })}${unit ? ` ${unit}` : ""}`;
  }

  _capture() {
    const m = this._metrics();
    const net = this._num(m.net_power);
    if (net === null) return;
    const point = `${net}`;
    if (point === this._lastPoint) return;
    this._lastPoint = point;
    this._history.push(net);
    if (this._history.length > 150) this._history.shift();
  }

  _sparkline() {
    if (this._history.length < 2) return `<div class="chart-empty">Live-Verlauf wird aufgebaut …</div>`;
    const maximum = Math.max(100, ...this._history.map(Math.abs));
    const points = this._history.map((value, index) => {
      const x = index / (this._history.length - 1) * 100;
      const y = 40 - ((value / maximum + 1) / 2) * 36;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    return `<svg class="spark" viewBox="0 0 100 44" preserveAspectRatio="none">
      <line x1="0" y1="22" x2="100" y2="22" class="zero"></line>
      <polyline points="${points}"></polyline>
    </svg>`;
  }

  _clickable(state, html, className = "") {
    return `<button class="clickable ${className}" data-entity="${state?.entity_id || ""}">${html}</button>`;
  }

  _phase(m, phase) {
    const voltage = m[`voltage_l${phase}`];
    const current = m[`current_l${phase}`];
    if (!voltage && !current) return "";
    return `<div class="phase"><strong>L${phase}</strong><span>${this._format(voltage, 1)}</span><span>${this._format(current, 2)}</span></div>`;
  }

  _energyRow(label, state, digits = 3) {
    if (!state) return "";
    return this._clickable(state, `<span>${label}</span><strong>${this._format(state, digits)}</strong>`, "row");
  }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const m = this._metrics();
    if (!m._anchor) {
      this.shadowRoot.innerHTML = `<ha-card><div class="empty">Kein gPlug Energy Cockpit gefunden.</div></ha-card>`;
      return;
    }
    const net = this._num(m.net_power) || 0;
    const importing = net >= 0;
    const status = m.meter_status?.state || "unavailable";
    const title = this._config.title || "gPlug Energy Cockpit";
    const hasPhases = [1, 2, 3].some((phase) => m[`voltage_l${phase}`] || m[`current_l${phase}`]);
    const hasTariffs = m.import_energy_t1 || m.import_energy_t2 || m.export_energy_t1 || m.export_energy_t2;
    const hasSolar = Boolean(m.inverter_grid_power);

    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; --blue:#2196f3; --cyan:#00acc1; --amber:#ff9800; --green:#43a047; --red:#e53935; }
        ha-card { overflow:hidden; }
        button { font:inherit; color:inherit; }
        .header { display:flex; justify-content:space-between; align-items:center; padding:14px 20px 8px; }
        .brand { display:flex; align-items:center; gap:11px; min-width:0; }
        .brand-logo { width:46px; height:46px; object-fit:contain; flex:0 0 auto; box-sizing:border-box; padding:4px; border-radius:12px; background:#fff; border:1px solid color-mix(in srgb,#102a43 12%,transparent); }
        .header h2 { margin:0; font-size:20px; font-weight:650; }
        .status { padding:5px 10px; border-radius:99px; font-size:12px; font-weight:700; }
        .status.online { color:var(--green); background:color-mix(in srgb,var(--green) 14%,transparent); }
        .status.stale,.status.unavailable { color:var(--red); background:color-mix(in srgb,var(--red) 14%,transparent); }
        .flow { display:grid; grid-template-columns:1fr 1.2fr 1fr; gap:16px; align-items:center; padding:18px 20px 20px; }
        .node { text-align:center; }
        .node .icon { width:64px; height:64px; margin:auto; border-radius:50%; display:grid; place-items:center; background:var(--secondary-background-color); font-size:30px; }
        .node strong { display:block; margin-top:8px; }
        .flow-center { text-align:center; }
        .flow-value { font-size:clamp(28px,7vw,44px); font-weight:750; white-space:nowrap; }
        .flow-label { color:var(--secondary-text-color); font-size:12px; margin-bottom:4px; }
        .arrow { height:5px; border-radius:99px; margin:12px 0 5px; background:linear-gradient(90deg,var(--blue),var(--cyan)); position:relative; }
        .arrow::after { content:""; position:absolute; right:-1px; top:-5px; border-left:11px solid var(--cyan); border-top:7px solid transparent; border-bottom:7px solid transparent; }
        .arrow.export { transform:rotate(180deg); background:linear-gradient(90deg,var(--amber),var(--cyan)); }
        .kpis { display:grid; grid-template-columns:repeat(4,1fr); border-top:1px solid var(--divider-color); border-bottom:1px solid var(--divider-color); }
        .clickable { appearance:none; border:0; background:transparent; cursor:pointer; }
        .kpi { padding:14px 10px; text-align:center; border-right:1px solid var(--divider-color); }
        .kpi:last-child { border-right:0; }
        .kpi span { display:block; color:var(--secondary-text-color); font-size:11px; margin-bottom:5px; }
        .kpi strong { font-size:16px; }
        .chart { padding:15px 20px 10px; }
        .chart-title { display:flex; justify-content:space-between; color:var(--secondary-text-color); font-size:11px; }
        .spark { display:block; width:100%; height:105px; margin-top:6px; }
        .spark polyline { fill:none; stroke:var(--blue); stroke-width:2.4; vector-effect:non-scaling-stroke; }
        .spark .zero { stroke:var(--divider-color); stroke-width:1; stroke-dasharray:3 3; vector-effect:non-scaling-stroke; }
        .chart-empty { height:70px; display:grid; place-items:center; color:var(--secondary-text-color); font-size:12px; }
        .sections { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; padding:10px 20px 20px; }
        .panel { border:1px solid var(--divider-color); border-radius:14px; padding:13px; min-width:0; }
        .panel h3 { margin:0 0 9px; font-size:13px; }
        .row { width:100%; display:flex; justify-content:space-between; gap:10px; padding:5px 0; }
        .row span { color:var(--secondary-text-color); text-align:left; }
        .row strong { white-space:nowrap; }
        .phases { display:grid; grid-template-columns:repeat(3,1fr); gap:6px; }
        .phase { border-radius:9px; background:var(--secondary-background-color); padding:9px 5px; text-align:center; }
        .phase strong,.phase span { display:block; } .phase span { color:var(--secondary-text-color); font-size:11px; margin-top:3px; }
        .solar { margin:0 20px 20px; padding:14px; border:1px solid color-mix(in srgb,var(--amber) 45%,var(--divider-color)); border-radius:14px; background:color-mix(in srgb,var(--amber) 5%,transparent); }
        .solar h3 { margin:0 0 10px; font-size:14px; }
        .solar-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; text-align:center; }
        .solar-grid span { display:block; color:var(--secondary-text-color); font-size:11px; }
        .solar-grid strong { display:block; margin-top:5px; }
        .empty { padding:24px; }
        @media(max-width:650px) {
          .flow { grid-template-columns:70px 1fr 70px; padding-left:10px; padding-right:10px; }
          .node .icon { width:48px; height:48px; font-size:23px; }
          .flow-value { font-size:26px; }
          .kpis { grid-template-columns:repeat(2,1fr); }
          .kpi:nth-child(2) { border-right:0; } .kpi:nth-child(-n+2) { border-bottom:1px solid var(--divider-color); }
          .sections { grid-template-columns:1fr; padding-left:12px; padding-right:12px; }
          .solar { margin-left:12px; margin-right:12px; }
        }
      </style>
      <ha-card>
        <div class="header"><div class="brand"><img class="brand-logo" src="/gplug_energy/gplug-energy-logo.png?v=${GPLUG_CARD_VERSION}" alt=""><h2>${title}</h2></div><span class="status ${status}">${status === "online" ? "● Online" : "● Daten veraltet"}</span></div>
        <div class="flow">
          <div class="node"><div class="icon">⚡</div><strong>Stromnetz</strong></div>
          <div class="flow-center">
            <div class="flow-label">${importing ? "Netzbezug" : "Einspeisung"}</div>
            <div class="flow-value">${this._format(importing ? m.import_power : m.export_power)}</div>
            <div class="arrow ${importing ? "" : "export"}"></div>
          </div>
          <div class="node"><div class="icon">⌂</div><strong>Haus</strong></div>
        </div>
        <div class="kpis">
          ${this._clickable(m.import_today, `<span>Bezug heute</span><strong>${this._format(m.import_today, 3)}</strong>`, "kpi")}
          ${this._clickable(m.export_today, `<span>Einspeisung heute</span><strong>${this._format(m.export_today, 3)}</strong>`, "kpi")}
          ${this._clickable(m.net_cost_today, `<span>Nettokosten heute</span><strong>${this._format(m.net_cost_today, 2)}</strong>`, "kpi")}
          ${this._clickable(importing ? m.peak_import_today : m.peak_export_today, `<span>Spitze heute</span><strong>${this._format(importing ? m.peak_import_today : m.peak_export_today)}</strong>`, "kpi")}
        </div>
        <div class="chart"><div class="chart-title"><span>Live-Netzleistung</span><span>Bezug + / Einspeisung −</span></div>${this._sparkline()}</div>
        <div class="sections">
          <div class="panel"><h3>Energiezähler</h3>
            ${this._energyRow("Netzbezug gesamt", m.import_energy_total)}
            ${this._energyRow("Einspeisung gesamt", m.export_energy_total)}
            ${!m.import_energy_total && !m.export_energy_total ? `<span class="flow-label">Keine Gesamtzähler zugeordnet</span>` : ""}
          </div>
          ${hasPhases ? `<div class="panel"><h3>Netzphasen</h3><div class="phases">${this._phase(m,1)}${this._phase(m,2)}${this._phase(m,3)}</div>${this._energyRow("Frequenz",m.frequency,2)}${this._energyRow("Spannungsabweichung",m.voltage_imbalance,2)}</div>` : ""}
          ${hasTariffs ? `<div class="panel"><h3>Tarifzähler</h3>${this._energyRow("Bezug T1",m.import_energy_t1)}${this._energyRow("Bezug T2",m.import_energy_t2)}${this._energyRow("Einspeisung T1",m.export_energy_t1)}${this._energyRow("Einspeisung T2",m.export_energy_t2)}</div>` : ""}
          <div class="panel"><h3>Datenqualität</h3>${this._energyRow("Alter der Daten",m.data_age,0)}${this._energyRow("Bezugsspitze",m.peak_import_today,0)}${this._energyRow("Einspeisespitze",m.peak_export_today,0)}</div>
        </div>
        ${hasSolar ? `<div class="solar"><h3>Optionaler Wechselrichtervergleich</h3><div class="solar-grid"><div><span>Wechselrichter</span><strong>${this._format(m.inverter_grid_power)}</strong></div><div><span>Abweichung</span><strong>${this._format(m.inverter_absolute_difference)}</strong></div><div><span>Übereinstimmung</span><strong>${this._format(m.inverter_agreement,1)}</strong></div></div></div>` : ""}
      </ha-card>`;

    this.shadowRoot.querySelectorAll("[data-entity]").forEach((element) => {
      element.addEventListener("click", () => {
        if (!element.dataset.entity) return;
        this.dispatchEvent(new CustomEvent("hass-more-info", { bubbles:true, composed:true, detail:{ entityId:element.dataset.entity } }));
      });
    });
  }
}

if (!customElements.get("gplug-energy-card")) customElements.define("gplug-energy-card", GPlugEnergyCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "gplug-energy-card",
  name: "gPlug Energy Cockpit",
  description: "Adaptives Smartmeter-Dashboard mit optionalem Wechselrichtervergleich",
  preview: true,
  documentationURL: "https://gplug.ch/",
});
console.info(`%c GPLUG-ENERGY-CARD %c ${GPLUG_CARD_VERSION} `, "color:white;background:#17365d;font-weight:bold", "color:#17365d;background:#d9eaf7");

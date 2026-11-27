(function () {
  const CARD_TYPE = 'sun-solar-dashboard-card';
  const EDITOR_TYPE = 'sun-solar-dashboard-card-editor';
  const DEFAULT_ETA = 'sensor.sun_solar_all_batteries_eta';

  if (customElements.get(CARD_TYPE)) return;

  function number(value) {
    if (value == null || value === '') return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  // ── Solar elevation using J2000 ─────────────────────────────────

  function getSunElevation(date, lat, lon) {
    const JD = date.getTime() / 86400000 + 2440587.5;
    const n = JD - 2451545.0;
    const L = ((280.460 + 0.9856474 * n) % 360 + 360) % 360;
    const g = ((357.528 + 0.9856003 * n) % 360 + 360) % 360;
    const gRad = g * Math.PI / 180;
    const lambda = L + 1.915 * Math.sin(gRad) + 0.020 * Math.sin(2 * gRad);
    const lambdaRad = lambda * Math.PI / 180;
    const epsilon = 23.439 - 0.0000004 * n;
    const epsilonRad = epsilon * Math.PI / 180;
    const sinDec = Math.sin(epsilonRad) * Math.sin(lambdaRad);
    const decl = Math.asin(sinDec);
    const RA_hours = Math.atan2(
      Math.cos(epsilonRad) * Math.sin(lambdaRad),
      Math.cos(lambdaRad)
    ) * 12 / Math.PI;
    const GMST = ((18.697374558 + 24.06570982441908 * n) % 24 + 24) % 24;
    const LMST = ((GMST + lon / 15) % 24 + 24) % 24;
    const HA = ((LMST - RA_hours + 24) % 24);
    const HArad = (HA > 12 ? HA - 24 : HA) * 15 * Math.PI / 180;
    const latRad = lat * Math.PI / 180;
    const sinElev = Math.sin(latRad) * Math.sin(decl) +
      Math.cos(latRad) * Math.cos(decl) * Math.cos(HArad);
    return Math.asin(Math.max(-1, Math.min(1, sinElev))) * 180 / Math.PI;
  }

  // ── Chart helpers ────────────────────────────────────────────────────────

  function smoothPath(points) {
    if (points.length < 2) return '';
    let d = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
    for (let i = 1; i < points.length; i++) {
      const cpx = ((points[i - 1].x + points[i].x) / 2).toFixed(1);
      d += ` C ${cpx} ${points[i - 1].y.toFixed(1)} ${cpx} ${points[i].y.toFixed(1)} ${points[i].x.toFixed(1)} ${points[i].y.toFixed(1)}`;
    }
    return d;
  }

  function formatHour(h) {
    if (h === 0 || h === 24) return '0h';
    if (h === 12) return '12h';
    return `${h}h`;
  }

  class SunSolarCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._history = [];
      this._config = {};
      this._refreshTimer = null;
    }

    static getStubConfig() {
      return {};
    }

    static getConfigElement() {
      return document.createElement(EDITOR_TYPE);
    }

    setConfig(config) {
      const start = config.start_hour ?? 4;
      const end = config.end_hour ?? 22;
      const maxPower = config.max_power == null ? null : number(config.max_power);
      if (typeof config.power_entity !== 'string' || !config.power_entity) {
        throw new Error('Select a PV power sensor (power_entity).');
      }
      if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end > 24 || start >= end) {
        throw new Error('Chart hours must be integers between 0 and 24, with start before end.');
      }
      if (config.max_power != null && !(maxPower > 0)) {
        throw new Error('max_power must be positive.');
      }
      this._config = {
        power_entity: config.power_entity,
        energy_entity: config.energy_entity || null,
        battery_soc_entity: config.battery_soc_entity || null,
        eta_entity: config.eta_entity || DEFAULT_ETA,
        title: config.title || 'Solar PV · Heute',
        start_hour: start,
        end_hour: end,
        max_power: maxPower,
      };
      this._history = [];
      this._build();
      this._startRefresh();
      if (this._hass) this._updateStats();
    }

    set hass(hass) {
      this._hass = hass;
      if (this._config.power_entity) {
        if (this.isConnected && this._refreshTimer === null) this._startRefresh();
        this._updateStats();
      }
    }

    connectedCallback() {
      this._startRefresh();
    }

    disconnectedCallback() {
      clearInterval(this._refreshTimer);
      this._refreshTimer = null;
    }

    _startRefresh() {
      if (!this.isConnected || !this._hass || !this._config.power_entity) return;
      clearInterval(this._refreshTimer);
      this._fetchHistory();
      this._refreshTimer = setInterval(() => this._fetchHistory(), 60000);
    }

    _build() {
      this.shadowRoot.innerHTML = `
        <style>
          :host { display: block; }

          .card {
            background: linear-gradient(160deg, #091829 0%, #0e2540 45%, #162f52 100%);
            border-radius: 18px;
            overflow: hidden;
            position: relative;
            padding-bottom: 4px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
          }

          .header {
            padding: 18px 22px 6px;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
          }

          .label {
            font-family: var(--code-font-family, monospace);
            font-size: 10px;
            letter-spacing: 2.5px;
            color: rgba(255,255,255,0.4);
            text-transform: uppercase;
            margin-bottom: 4px;
          }

          .power-row {
            display: flex;
            align-items: baseline;
            gap: 6px;
          }

          .power-val {
            font-family: var(--code-font-family, monospace);
            font-size: 44px;
            font-weight: 700;
            color: #fff;
            line-height: 1;
            letter-spacing: -1px;
          }

          .power-unit {
            font-family: var(--code-font-family, monospace);
            font-size: 16px;
            color: rgba(255,255,255,0.55);
            font-weight: 400;
          }

          .stats {
            display: flex;
            gap: 28px;
            padding: 6px 22px 0;
            flex-wrap: wrap;
          }

          .stat { display: flex; flex-direction: column; gap: 1px; }

          .stat-label {
            font-family: var(--code-font-family, monospace);
            font-size: 9px;
            letter-spacing: 2px;
            color: rgba(255,255,255,0.35);
            text-transform: uppercase;
          }

          .stat-value {
            font-family: var(--code-font-family, monospace);
            font-size: 15px;
            font-weight: 700;
            color: rgba(255,220,80,0.9);
          }

          /* Akku-voll-Info bekommt eine leicht grünliche Farbe zur Unterscheidung */
          .stat-value.battery {
            color: rgba(110,231,183,0.9);
          }

          /* SOC-Wert gedimmt neben der ETA */
          .stat-value .soc-hint {
            font-size: 10px;
            font-weight: 400;
            color: rgba(110,231,183,0.5);
            margin-left: 4px;
          }

          .chart-wrap {
            margin-top: 10px;
            width: 100%;
            position: relative;
          }

          svg.chart {
            display: block;
            width: 100%;
            height: auto;
          }

          .time-axis {
            display: flex;
            justify-content: space-between;
            padding: 2px 8px 10px;
          }

          .time-label {
            font-family: var(--code-font-family, monospace);
            font-size: 9px;
            color: rgba(255,255,255,0.25);
            letter-spacing: 0.5px;
          }
        </style>

        <div class="card">
          <div class="header">
            <div>
              <div class="label" id="lbl-title">Solar PV · Heute</div>
              <div class="power-row">
                <span class="power-val" id="power-val">—</span>
                <span class="power-unit">kW</span>
              </div>
            </div>
          </div>
          <div class="stats">
            <div class="stat">
              <div class="stat-label">Erzeugt</div>
              <div class="stat-value"><span id="energy-val">—</span> kWh</div>
            </div>
            <div class="stat">
              <div class="stat-label">Sonnenstand</div>
              <div class="stat-value"><span id="sun-val">—</span>°</div>
            </div>
            <div class="stat" id="battery-stat">
              <div class="stat-label">Akku voll</div>
              <div class="stat-value battery">
                <span id="battery-eta">—</span><span class="soc-hint" id="battery-soc-hint"></span>
              </div>
            </div>
          </div>
          <div class="chart-wrap">
            <svg class="chart" id="chart" viewBox="0 0 800 210" preserveAspectRatio="none"
                 xmlns="http://www.w3.org/2000/svg"></svg>
          </div>
          <div class="time-axis" id="time-axis"></div>
        </div>
      `;
      this.shadowRoot.getElementById('lbl-title').textContent = this._config.title;
    }

    _updateStats() {
      const states = this._hass.states;
      const powerState = states[this._config.power_entity];
      const rawPower = number(powerState?.state);
      const kw = rawPower === null ? null :
        (powerState.attributes?.unit_of_measurement === 'kW' ? rawPower : rawPower / 1000);
      const rawEnergy = number(states[this._config.energy_entity]?.state);
      const elevation = number(states['sun.sun']?.attributes?.elevation);
      const soc = number(states[this._config.battery_soc_entity]?.state);
      const eta = states[this._config.eta_entity]?.attributes?.eta_display;
      const display = typeof eta === 'string' && /^(voll|--:--|[0-2][0-9]:[0-5][0-9])$/.test(eta)
        ? eta : '--:--';

      this.shadowRoot.getElementById('power-val').textContent = kw?.toFixed(2) ?? '—';
      this.shadowRoot.getElementById('energy-val').textContent = rawEnergy?.toFixed(1) ?? '—';
      this.shadowRoot.getElementById('sun-val').textContent = elevation?.toFixed(1) ?? '—';
      this.shadowRoot.getElementById('battery-eta').textContent = display;
      this.shadowRoot.getElementById('battery-soc-hint').textContent = soc === null ? '' : `${soc.toFixed(0)}%`;
      this._drawChart();
    }

    async _fetchHistory() {
      const config = this._config;
      const request = this._historyRequest = Symbol();
      const now = new Date();
      const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      try {
        const result = await this._hass.callApi(
          'GET',
          `history/period/${startOfDay.toISOString()}` +
          `?filter_entity_id=${encodeURIComponent(config.power_entity)}` +
          `&minimal_response=true&no_attributes=true`
        );
        if (this._historyRequest === request && this._config === config && this.isConnected) {
          this._history = (result?.[0] ?? [])
            .map(s => {
              const t = s.lu ? new Date(s.lu * 1000) : new Date(s.last_changed || s.last_updated);
              const v = number(s.s ?? s.state);
              return { t, v };
            })
            .filter(s => s.v !== null && s.v >= 0 && s.t >= startOfDay);
          this._drawChart();
        }
      } catch (e) {
        console.warn('[sun-solar-card] Could not load PV history:', e);
      }
    }

    // ── Draw the chart ──────────────────────────────────────────────────────────

    _drawChart() {
      const svg = this.shadowRoot.getElementById('chart');
      if (!svg || !this._hass) return;

      const W = 800, H = 210;
      const PAD_TOP = 15, PAD_BOT = 8;
      const chartH = H - PAD_TOP - PAD_BOT;

      const startHour  = this._config.start_hour;
      const endHour    = this._config.end_hour;
      const totalHours = endHour - startHour;

      const lat = this._hass.config.latitude;
      const lon = this._hass.config.longitude;
      const now   = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

      const timeToX = (date) => {
        const h = date.getHours() + date.getMinutes() / 60 + date.getSeconds() / 3600;
        return ((h - startHour) / totalHours) * W;
      };

      // Sample solar elevation every ten minutes
      const sunPoints = [];
      for (let h = startHour; h <= endHour; h += 1 / 6) {
        const d = new Date(today);
        d.setHours(Math.floor(h), Math.round((h % 1) * 60), 0, 0);
        const elev = getSunElevation(d, lat, lon);
        const x = ((h - startHour) / totalHours) * W;
        sunPoints.push({ x, elev, h });
      }

      const maxElev  = Math.max(...sunPoints.map(p => p.elev), 5);
      const elevToY  = (elev) => {
        const norm = Math.max(0, elev) / maxElev;
        return PAD_TOP + chartH - norm * chartH;
      };

      const riseSet  = sunPoints.filter(p => p.elev > 0);
      const sunriseX = riseSet.length > 0 ? riseSet[0].x : 0;
      const sunsetX  = riseSet.length > 0 ? riseSet[riseSet.length - 1].x : W;

      const unit       = this._hass.states[this._config.power_entity]?.attributes?.unit_of_measurement || 'W';
      const unitFactor = unit === 'kW' ? 1000 : 1;
      const maxPowerW  = this._config.max_power != null
        ? Math.max(this._config.max_power, 1)
        : Math.max(...this._history.map(s => s.v * unitFactor), 1000);
      const powerToY   = (watt) => {
        const norm = Math.min(1, watt / maxPowerW);
        return PAD_TOP + chartH - norm * chartH * 0.92;
      };

      let prodLinePath = '';
      let prodAreaPath = '';
      if (this._history.length > 1) {
        const pts = this._history.map(s => ({
          x: timeToX(s.t),
          y: powerToY(s.v * unitFactor)
        }));
        prodLinePath = smoothPath(pts);
        const lastPt = pts[pts.length - 1];
        prodAreaPath = prodLinePath +
          ` L ${lastPt.x.toFixed(1)} ${(PAD_TOP + chartH).toFixed(1)}` +
          ` L ${pts[0].x.toFixed(1)} ${(PAD_TOP + chartH).toFixed(1)} Z`;
      }

      const currentElev = getSunElevation(now, lat, lon);
      const currentX    = timeToX(now);
      const currentSunY = elevToY(currentElev);
      const sunVisible  = currentElev > 0 && currentX >= 0 && currentX <= W;

      const eta = this._hass.states[this._config.eta_entity];
      const etaDate = eta?.attributes?.status === 'charging' ? new Date(eta.state) : null;
      const etaLineX = etaDate && etaDate > now && etaDate.toDateString() === now.toDateString()
        ? timeToX(etaDate) : null;

      let s = `
        <defs>
          <linearGradient id="skyBg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stop-color="#1a4a8a" stop-opacity="0.22"/>
            <stop offset="100%" stop-color="#091829" stop-opacity="0"/>
          </linearGradient>
          <radialGradient id="sunAura" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stop-color="#fde68a" stop-opacity="0.35"/>
            <stop offset="60%"  stop-color="#f59e0b" stop-opacity="0.12"/>
            <stop offset="100%" stop-color="#f59e0b" stop-opacity="0"/>
          </radialGradient>
          <linearGradient id="prodFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stop-color="#f59e0b" stop-opacity="0.65"/>
            <stop offset="75%"  stop-color="#f59e0b" stop-opacity="0.12"/>
            <stop offset="100%" stop-color="#f59e0b" stop-opacity="0.02"/>
          </linearGradient>
          <linearGradient id="prodLine" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%"   stop-color="#fbbf24" stop-opacity="0.15"/>
            <stop offset="30%"  stop-color="#fbbf24" stop-opacity="1"/>
            <stop offset="85%"  stop-color="#fbbf24" stop-opacity="0.8"/>
            <stop offset="100%" stop-color="#fbbf24" stop-opacity="0.3"/>
          </linearGradient>
          <filter id="glow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur"/>
            <feMerge>
              <feMergeNode in="blur"/>
              <feMergeNode in="blur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
          <filter id="glowLarge" x="-200%" y="-200%" width="500%" height="500%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="18" result="blur"/>
            <feMerge>
              <feMergeNode in="blur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
          <clipPath id="chartClip">
            <rect x="0" y="0" width="${W}" height="${H}"/>
          </clipPath>
        </defs>

        <rect x="${sunriseX.toFixed(1)}" y="0"
              width="${(sunsetX - sunriseX).toFixed(1)}" height="${H}"
              fill="url(#skyBg)" clip-path="url(#chartClip)"/>
      `;

      // Solar arc
      const arcAbove = sunPoints.filter(p => p.elev > 0);
      if (arcAbove.length > 2) {
        const arcPts = arcAbove.map(p => ({ x: p.x, y: elevToY(p.elev) }));
        s += `<path d="${smoothPath(arcPts)}" fill="none"
               stroke="rgba(251,191,36,0.22)" stroke-width="1.5"
               stroke-dasharray="5 7" clip-path="url(#chartClip)"/>`;
      }

      // PV production area and line
      if (prodAreaPath) {
        s += `<path d="${prodAreaPath}" fill="url(#prodFill)"
               clip-path="url(#chartClip)"/>`;
      }
      if (prodLinePath) {
        s += `<path d="${prodLinePath}" fill="none"
               stroke="url(#prodLine)" stroke-width="2.5" stroke-linejoin="round"
               clip-path="url(#chartClip)"/>`;
      }

      // Horizon
      s += `<line x1="0" y1="${(PAD_TOP + chartH).toFixed(1)}"
              x2="${W}" y2="${(PAD_TOP + chartH).toFixed(1)}"
              stroke="rgba(255,255,255,0.06)" stroke-width="1"/>`;

      // Current time marker
      if (currentX >= 0 && currentX <= W) {
        s += `<line x1="${currentX.toFixed(1)}" y1="0"
                x2="${currentX.toFixed(1)}" y2="${H}"
                stroke="rgba(255,255,255,0.08)" stroke-width="1"
                stroke-dasharray="3 5"/>`;
      }

      // ── Battery forecast marker ────────────────────────────────────────────
      // Dashed line and label
      if (etaLineX !== null && etaLineX >= 0 && etaLineX <= W) {
        s += `<line x1="${etaLineX.toFixed(1)}" y1="0"
                x2="${etaLineX.toFixed(1)}" y2="${H}"
                stroke="rgba(110,231,183,0.45)" stroke-width="1.5"
                stroke-dasharray="4 5" clip-path="url(#chartClip)"/>`;
        // Battery icon above the marker
        const labelX = Math.min(etaLineX + 5, W - 40);
        s += `<text x="${labelX.toFixed(1)}" y="14"
                font-family="monospace" font-size="9" fill="rgba(110,231,183,0.7)"
                clip-path="url(#chartClip)">🔋</text>`;
      }

      // Current sun position
      if (sunVisible) {
        s += `<ellipse cx="${currentX.toFixed(1)}" cy="${currentSunY.toFixed(1)}"
                rx="55" ry="55" fill="url(#sunAura)"
                filter="url(#glowLarge)" clip-path="url(#chartClip)"/>`;
        s += `<circle cx="${currentX.toFixed(1)}" cy="${currentSunY.toFixed(1)}"
                r="15" fill="rgba(251,191,36,0.12)" clip-path="url(#chartClip)"/>`;
        s += `<circle cx="${currentX.toFixed(1)}" cy="${currentSunY.toFixed(1)}"
                r="8" fill="#fde68a" filter="url(#glow)" clip-path="url(#chartClip)"/>`;
        s += `<circle cx="${currentX.toFixed(1)}" cy="${currentSunY.toFixed(1)}"
                r="4.5" fill="#fffbeb" clip-path="url(#chartClip)"/>`;
      }

      svg.innerHTML = s;
      this._updateTimeAxis(startHour, endHour);
    }

    _updateTimeAxis(startHour, endHour) {
      const axis = this.shadowRoot.getElementById('time-axis');
      if (!axis) return;
      const labels = [];
      for (let h = startHour; h <= endHour; h += 2) {
        labels.push(formatHour(h));
      }
      axis.innerHTML = labels
        .map(l => `<span class="time-label">${l}</span>`)
        .join('');
    }

    getCardSize() { return 4; }
  }

  const fieldLabels = {
    power_entity: 'PV power sensor',
    energy_entity: 'Daily solar energy sensor',
    battery_soc_entity: 'Battery SOC sensor (optional)',
    eta_entity: 'Forecast sensor (optional override)',
    title: 'Title',
    start_hour: 'Chart start hour',
    end_hour: 'Chart end hour',
    max_power: 'Chart power maximum (W)',
  };
  const fields = [
    { name: 'power_entity', required: true, selector: { entity: { domain: 'sensor' } } },
    ...['energy_entity', 'battery_soc_entity', 'eta_entity'].map(name => ({
      name, selector: { entity: { domain: 'sensor' } },
    })),
    { name: 'title', selector: { text: {} } },
    ...['start_hour', 'end_hour'].map(name => ({
      name, selector: { number: { min: 0, max: 24, step: 1, mode: 'box' } },
    })),
    { name: 'max_power', selector: { number: { min: 1, mode: 'box', unit_of_measurement: 'W' } } },
  ];

  class SunSolarCardEditor extends HTMLElement {
    constructor() {
      super();
      this._form = document.createElement('ha-form');
      this._form.schema = fields;
      this._form.computeLabel = field => fieldLabels[field.name];
      this._form.addEventListener('value-changed', event => {
        event.stopPropagation();
        this.dispatchEvent(new CustomEvent('config-changed', {
          detail: { config: { ...event.detail.value, type: `custom:${CARD_TYPE}` } },
          bubbles: true,
          composed: true,
        }));
      });
    }

    connectedCallback() {
      this.appendChild(this._form);
    }

    set hass(value) {
      this._form.hass = value;
    }

    setConfig(config) {
      this._form.data = config;
    }
  }

  customElements.define(EDITOR_TYPE, SunSolarCardEditor);
  customElements.define(CARD_TYPE, SunSolarCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TYPE,
    name: 'Sun Solar Dashboard',
    description: 'PV production, sun position and the battery forecast from Sun Solar.',
    preview: false,
  });
})();

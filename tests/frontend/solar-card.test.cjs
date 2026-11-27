const assert = require("node:assert/strict");
const fs = require("node:fs");
const { test } = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(
  "custom_components/sun_solar/www/sun-solar-dashboard-card.js",
  "utf8",
);

function loadCard() {
  class FixedDate extends Date {
    constructor(...args) {
      super(...(args.length ? args : ["2026-11-27T12:00:00"]));
    }
  }
  const elements = new Map();
  const context = vm.createContext({
    customElements: {
      get: (name) => elements.get(name),
      define: (name, element) => {
        assert.equal(elements.has(name), false);
        elements.set(name, element);
      },
    },
    HTMLElement: class {
      attachShadow() {
        const nodes = new Map();
        this.shadowRoot = {
          getElementById(id) {
            if (!nodes.has(id)) nodes.set(id, {});
            return nodes.get(id);
          },
        };
      }
    },
    window: {},
    Date: FixedDate,
  });
  vm.runInContext(source, context);
  vm.runInContext(source, context);
  assert.equal(context.window.customCards.length, 1);
  return new (elements.get("sun-solar-dashboard-card"))();
}

const forecastId = "sensor.sun_solar_all_batteries_eta";
const now = new Date("2026-11-27T12:00:00");

test("displays integration forecast and uses its timestamp for the marker", () => {
  const card = loadCard();
  card.setConfig({ power_entity: "sensor.test_pv_power", start_hour: 0, end_hour: 24 });
  const forecast = new Date(now);
  forecast.setHours(14, 30);
  const etas = { state: forecast.toISOString(), attributes: { status: "charging", eta_display: "14:30" } };
  card.hass = {
    config: { latitude: 52, longitude: 13 },
    states: { [forecastId]: etas, "sensor.test_pv_power": { state: "1000" } },
  };
  assert.equal(card.shadowRoot.getElementById("power-val").textContent, "1.00");
  assert.equal(card.shadowRoot.getElementById("battery-eta").textContent, "14:30");

  assert.match(card.shadowRoot.getElementById("chart").innerHTML, /🔋/);

  etas.state = "unknown";
  etas.attributes = { status: "charging_past_sunset", eta_display: "--:--" };
  card.hass = card._hass;
  assert.equal(card.shadowRoot.getElementById("battery-eta").textContent, "--:--");
  assert.doesNotMatch(card.shadowRoot.getElementById("chart").innerHTML, /🔋/);
});

test("keeps legacy display settings and shows full with one battery", () => {
  const card = loadCard();
  assert.throws(() => card.setConfig({ power_entity: "sensor.test_pv_power", start_hour: 23 }));
  card.setConfig({
    power_entity: "sensor.test_pv_power",
    battery_soc_entity: "sensor.test_soc",
    eta_entity: "sensor.test_eta",
    title: "<Local title>",
  });
  card.hass = {
    config: { latitude: 52, longitude: 13 },
    states: {
      "sensor.test_soc": { state: "99.5" },
      "sensor.test_eta": { state: new Date().toISOString(), attributes: { status: "full", eta_display: "voll" } },
    },
  };
  assert.equal(card.shadowRoot.getElementById("battery-eta").textContent, "voll");
  assert.equal(card.shadowRoot.getElementById("battery-soc-hint").textContent, "100%");
  assert.equal(card.shadowRoot.getElementById("lbl-title").textContent, "<Local title>");
  assert.doesNotMatch(card.shadowRoot.getElementById("chart").innerHTML, /🔋/);
});

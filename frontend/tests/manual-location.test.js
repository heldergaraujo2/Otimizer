const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "route-safety.js"), "utf8");

function loadUi() {
  const context = {
    console,
    setStatus() {},
    $() { return { hidden: true, textContent: "", innerHTML: "", classList: { toggle() {}, add() {} }, insertAdjacentHTML() {}, addEventListener() {} }; },
    currentRoute: [],
    markers: [],
    visitedStops: new Set(),
    selectedIndex: -1,
    L: undefined,
    confirm: () => true,
  };
  context.window = context;
  vm.runInNewContext(source, context);
  return context.OtimizerRouteUI;
}

test("manual location is treated as a navigable map point", () => {
  const ui = loadUi();
  const stop = {
    latitude: -16.705,
    longitude: -49.255,
    location: {
      source: "manual",
      confidence: 1,
      access_latitude: -16.705,
      access_longitude: -49.255,
    },
  };
  assert.deepEqual(ui.mapCoordinates(stop), { latitude: -16.705, longitude: -49.255, kind: "manual" });
  assert.equal(ui.stopState(stop), "located");
  assert.deepEqual(ui.navigationTarget(stop), { latitude: -16.705, longitude: -49.255 });
});

test("manual location is explicitly described to the driver", () => {
  const ui = loadUi();
  const stop = {
    location: {
      source: "manual",
      confidence: 1,
      access_latitude: -16.705,
      access_longitude: -49.255,
    },
  };
  assert.equal(ui.locationSummary(stop), "Localização marcada manualmente pelo motorista");
});

test("frontend sends manual location overrides through the optimization request", () => {
  const appSource = fs.readFileSync(path.join(__dirname, "..", "app.js"), "utf8");
  assert.match(appSource, /manualLocations = \{\}/);
  assert.match(appSource, /manual_locations/);
  assert.match(appSource, /otimizerManualLocationSelected/);
  assert.match(appSource, /Reotimizando toda a rota/);
});

test("pending and approximate stops expose manual map placement", () => {
  const appSource = fs.readFileSync(path.join(__dirname, "..", "route-safety.js"), "utf8");
  assert.match(appSource, /Marcar localização no mapa/);
  assert.match(appSource, /otimizerStartManualPlacement/);
  assert.match(appSource, /Confirmar localização da parada/);
});

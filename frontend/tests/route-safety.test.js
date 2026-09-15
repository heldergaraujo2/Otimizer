const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "route-safety.js"), "utf8");

function createHarness() {
  const elements = new Map();
  const document = {
    querySelectorAll: () => [],
    querySelector: () => null,
  };
  const context = {
    console,
    window: {},
    document,
    fetch: async () => ({ ok: true, json: async () => ({ routes: [{ geometry: {} }] }) }),
    escapeHtml: (value) => String(value ?? ""),
    $: (id) => {
      if (!elements.has(id)) {
        elements.set(id, {
          hidden: true,
          textContent: "",
          innerHTML: "",
          dataset: {},
          classList: { add() {}, toggle() {} },
        });
      }
      return elements.get(id);
    },
    L: {},
    setTimeout,
    clearTimeout,
  };
  const bootstrap = `
    let currentRoute = [];
    let visitedStops = new Set();
    let markers = [];
    let map = null;
    let routeLine = null;
    let selectedIndex = -1;
    function stopIcon() {}
    function markStopVisited() {}
    async function fetchRouteGeometry() {}
    async function renderMap() {}
    function showStop() {}
    function renderStops() {}
    ${source}
    globalThis.__state = {
      elements,
      get currentRoute() { return currentRoute; },
      set currentRoute(value) { currentRoute = value; },
      get renderStops() { return renderStops; },
      get showStop() { return showStop; },
      get fetchRouteGeometry() { return fetchRouteGeometry; },
      get ui() { return window.OtimizerRouteUI; },
    };
  `;
  const vmContext = vm.createContext({ ...context, elements });
  vm.runInContext(bootstrap, vmContext);
  return vm.runInContext("globalThis.__state", vmContext);
}

test("identifica parada sem coordenadas como pendente", () => {
  const h = createHarness();
  const stop = { sequence: 4, latitude: null, longitude: null, deliveries: [], location: {} };
  assert.equal(h.ui.stopState(stop), "pending");
  assert.equal(h.ui.navigationUrl(stop), null);
});

test("não habilita navegação usando apenas o centro da propriedade", () => {
  const h = createHarness();
  const stop = {
    sequence: 5,
    latitude: -16.70,
    longitude: -49.20,
    deliveries: [],
    location: {
      source: "cadastral",
      property_latitude: -16.701,
      property_longitude: -49.201,
      access_latitude: null,
      access_longitude: null,
    },
  };
  assert.equal(h.ui.stopState(stop), "approximate");
  assert.equal(h.ui.navigationUrl(stop), null);
});

test("usa ponto de acesso cadastral para navegação quando disponível", () => {
  const h = createHarness();
  const stop = {
    sequence: 6,
    latitude: -16.70,
    longitude: -49.20,
    deliveries: [],
    location: { source: "cadastral", access_latitude: -16.702, access_longitude: -49.202 },
  };
  const url = h.ui.navigationUrl(stop);
  assert.match(url, /-16\.702/);
  assert.match(url, /-49\.202/);
});

test("mantém parada pendente na lista e informa seu estado", () => {
  const h = createHarness();
  const stop = {
    sequence: 7,
    delivery_count: 1,
    latitude: null,
    longitude: null,
    deliveries: [{ address: "Rua A" }],
    location: {},
  };
  h.renderStops([stop]);
  assert.match(h.elements.get("stops").innerHTML, /Localização pendente/);
});

test("não gera link de navegação para parada pendente no detalhe", () => {
  const h = createHarness();
  const stop = {
    sequence: 8,
    delivery_count: 1,
    latitude: null,
    longitude: null,
    deliveries: [{ address: "Rua B" }],
    location: {},
  };
  h.currentRoute = [stop];
  h.showStop(0);
  assert.match(h.elements.get("detail-content").innerHTML, /Localização de navegação pendente/);
  assert.doesNotMatch(h.elements.get("detail-content").innerHTML, /google\.com\/maps\/dir/);
});

test("não tenta roteamento OSRM incluindo parada sem coordenadas", async () => {
  const h = createHarness();
  const located = { sequence: 1, latitude: -16.70, longitude: -49.20, deliveries: [], location: {} };
  const located2 = { sequence: 3, latitude: -16.71, longitude: -49.21, deliveries: [], location: {} };
  const pending = { sequence: 2, latitude: null, longitude: null, deliveries: [], location: {} };
  const geometry = await h.fetchRouteGeometry([located, pending, located2]);
  assert.ok(geometry);
  assert.equal(h.ui.mapCoordinates(located).latitude, -16.70);
  assert.equal(h.ui.mapCoordinates(pending), null);
});

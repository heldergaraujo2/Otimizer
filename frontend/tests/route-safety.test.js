const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "route-safety.js"), "utf8");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[char]));
}

function createHarness() {
  const elements = new Map();
  const requests = [];
  const document = {
    querySelectorAll: () => [],
    querySelector: () => null,
  };
  const context = {
    console,
    window: {},
    document,
    fetch: async (url) => {
      requests.push(url);
      return { ok: true, json: async () => ({ routes: [{ geometry: {} }] }) };
    },
    escapeHtml,
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
      requests,
      get currentRoute() { return currentRoute; },
      set currentRoute(value) { currentRoute = value; },
      get renderStops() { return renderStops; },
      get showStop() { return showStop; },
      get fetchRouteGeometry() { return fetchRouteGeometry; },
      get ui() { return window.OtimizerRouteUI; },
    };
  `;
  const vmContext = vm.createContext({ ...context, elements, requests });
  vm.runInContext(bootstrap, vmContext);
  return vm.runInContext("globalThis.__state", vmContext);
}

test("identifica parada sem coordenadas como pendente", () => {
  const h = createHarness();
  const stop = { sequence: 4, latitude: null, longitude: null, deliveries: [], location: {} };
  assert.equal(h.ui.stopState(stop), "pending");
  assert.equal(h.ui.navigationUrl(stop), null);
});

test("rejeita 0,0 como coordenada de mapa", () => {
  const h = createHarness();
  const stop = { sequence: 4, latitude: 0, longitude: 0, deliveries: [], location: {} };
  assert.equal(h.ui.validCoordinatePair(0, 0), false);
  assert.equal(h.ui.mapCoordinates(stop), null);
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

test("escapa dados variáveis da parada antes de renderizar HTML", () => {
  const h = createHarness();
  const stop = {
    sequence: '<img src=x onerror="alert(1)">',
    delivery_count: '<script>alert(1)</script>',
    latitude: null,
    longitude: null,
    deliveries: [{ address: "Rua <A>" }],
    location: {},
  };
  h.renderStops([stop]);
  const html = h.elements.get("stops").innerHTML;
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
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

test("desenha apenas segmentos contínuos e nunca envia a parada pendente ao OSRM", async () => {
  const h = createHarness();
  const first = { sequence: 1, latitude: -16.70, longitude: -49.20, deliveries: [], location: {} };
  const second = { sequence: 2, latitude: -16.71, longitude: -49.21, deliveries: [], location: {} };
  const pending = { sequence: 3, latitude: null, longitude: null, deliveries: [], location: {} };
  const fourth = { sequence: 4, latitude: -16.72, longitude: -49.22, deliveries: [], location: {} };
  const fifth = { sequence: 5, latitude: -16.73, longitude: -49.23, deliveries: [], location: {} };

  const geometry = await h.fetchRouteGeometry([first, second, pending, fourth, fifth]);

  assert.equal(geometry.type, "FeatureCollection");
  assert.equal(geometry.features.length, 2);
  assert.equal(h.requests.length, 2);
  assert.match(h.requests[0], /-49\.2,-16\.7;-49\.21,-16\.71/);
  assert.match(h.requests[1], /-49\.22,-16\.72;-49\.23,-16\.73/);
  assert.equal(h.ui.mapCoordinates(pending), null);
});

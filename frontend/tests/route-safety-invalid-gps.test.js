const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "route-safety.js"), "utf8");

function loadUi() {
  const context = {
    console,
    window: {},
    document: { querySelectorAll: () => [], querySelector: () => null },
    escapeHtml: (value) => String(value ?? ""),
    $: () => ({ classList: { add() {}, toggle() {} } }),
    L: {},
  };
  vm.runInNewContext(source, context);
  return context.window.OtimizerRouteUI;
}

test("rejeita GPS 0,0 como coordenada utilizável", () => {
  const ui = loadUi();
  assert.equal(ui.validCoordinatePair(0, 0), true);
  assert.equal(ui.mapCoordinates({ latitude: 0, longitude: 0, location: {} }), {
    latitude: 0,
    longitude: 0,
    kind: "route",
  });
});

test("não confunde coordenada inválida com localização pendente", () => {
  const ui = loadUi();
  const stop = { latitude: "not-a-number", longitude: -49.2, location: {} };
  assert.equal(ui.mapCoordinates(stop), null);
  assert.equal(ui.navigationUrl(stop), null);
});

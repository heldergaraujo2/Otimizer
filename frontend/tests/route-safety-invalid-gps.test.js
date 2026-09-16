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

test("aceita apenas coordenadas numéricas finitas dentro dos limites", () => {
  const ui = loadUi();
  assert.equal(ui.validCoordinatePair(-16.7, -49.2), true);
  assert.equal(ui.validCoordinatePair("-16.7", "-49.2"), true);
  assert.equal(ui.validCoordinatePair("not-a-number", -49.2), false);
  assert.equal(ui.validCoordinatePair(-91, -49.2), false);
  assert.equal(ui.validCoordinatePair(-16.7, 181), false);
});

test("não confunde coordenada inválida com localização pendente", () => {
  const ui = loadUi();
  const stop = { latitude: "not-a-number", longitude: -49.2, location: {} };
  assert.equal(ui.mapCoordinates(stop), null);
  assert.equal(ui.navigationUrl(stop), null);
});

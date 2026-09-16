const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const indexSource = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const appPosition = indexSource.indexOf('src="app.js"');
const safetyPosition = indexSource.indexOf('src="route-safety.js"');

test("carrega a camada de segurança da rota depois do app", () => {
  assert.notEqual(appPosition, -1, "app.js precisa estar presente no HTML");
  assert.notEqual(safetyPosition, -1, "route-safety.js precisa estar presente no HTML");
  assert.ok(
    safetyPosition > appPosition,
    "route-safety.js precisa ser carregado depois de app.js enquanto a camada sobrescreve as funções de UI"
  );
});

const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const test = require("node:test");

const source = fs.readFileSync(path.join(__dirname, "..", "manual-route.js"), "utf8");
const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");

test("manual route exposes address fields and optional map pin", () => {
  assert.match(source, /manual-street/);
  assert.match(source, /manual-number/);
  assert.match(source, /manual-neighborhood/);
  assert.match(source, /manual-quadra/);
  assert.match(source, /manual-lote/);
  assert.match(source, /manual-map/);
  assert.match(source, /latitude:\s*hasMunicipalPoint\s*\?\s*latitude\s*:\s*null/);
  assert.match(source, /longitude:\s*hasMunicipalPoint\s*\?\s*longitude\s*:\s*null/);
});

test("manual route invalidates a municipal street pin when its context changes", () => {
  assert.match(source, /function invalidateMunicipalStreetSelection\(\)/);
  assert.match(source, /manual-neighborhood\"\)\.addEventListener\(\"input\", invalidateMunicipalStreetSelection\)/);
  assert.match(source, /manual-city\"\)\.addEventListener\(\"input\", invalidateMunicipalStreetSelection\)/);
  assert.match(source, /delete streetInput\.dataset\.selectedLatitude/);
  assert.match(source, /delete streetInput\.dataset\.selectedLongitude/);
  assert.match(source, /delete streetInput\.dataset\.selectedStreetId/);
});

test("manual route sends its stops to the dedicated optimization endpoint", () => {
  assert.match(source, /\/optimize-manual/);
  assert.match(source, /return_to_start/);
  assert.match(source, /objective/);
  assert.match(html, /manual-route\.js/);
});

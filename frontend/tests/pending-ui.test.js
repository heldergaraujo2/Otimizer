const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const test = require("node:test");

const source = fs.readFileSync(path.join(__dirname, "..", "pending-ui.js"), "utf8");
const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");

test("pending UI announces the number of stops outside optimization", () => {
  assert.match(source, /fora da otimização/);
  assert.match(source, /pending-alert/);
  assert.match(html, /id="pending-alert"/);
});

test("pending UI moves unresolved stops before optimized stops", () => {
  assert.match(source, /pendingIndexes/);
  assert.match(source, /\[\.\.\.pendingIndexes, \.\.\.route\.map/);
  assert.match(source, /stop-outside-optimization/);
});

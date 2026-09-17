import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../admin.html", import.meta.url), "utf8");
const js = fs.readFileSync(new URL("../admin.js", import.meta.url), "utf8");
const css = fs.readFileSync(new URL("../admin.css", import.meta.url), "utf8");

test("admin panel is a dedicated surface and does not contain backend credentials", () => {
  assert.match(html, /id="login-form"/);
  assert.match(html, /id="admin-panel"/);
  assert.match(html, /id="generate-form"/);
  assert.match(js, /\/admin\/licenses/);
  assert.match(js, /\/admin\/devices\//);
  assert.match(js, /account\.role !== "ADMIN"/);
  assert.doesNotMatch(js, /device_key_hash/);
  assert.doesNotMatch(js, /password_hash/);
  assert.doesNotMatch(js, /client_secret|api_secret|private_key/i);
  assert.ok(css.length > 500);
});

test("admin panel exposes the complete license lifecycle actions", () => {
  for (const action of ["activate", "renew", "suspend", "reactivate", "revoke"]) {
    assert.match(js, new RegExp(`/${action}`));
  }
  assert.match(js, /history/);
  assert.match(js, /devices/);
});

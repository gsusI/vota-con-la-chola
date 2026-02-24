const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI loads cross-method stability module", () => {
  const html = readCitizenHtml();
  assert.match(html, /<script\s+src=["']\.\/cross_method_stability\.js["']><\/script>/i);
  assert.match(html, /function\s+buildCrossMethodStability\s*\(/i);
  assert.match(html, /function\s+renderCrossMethodStabilityPanel\s*\(/i);
});

test("citizen coherence view includes cross-method stability contract markers", () => {
  const html = readCitizenHtml();
  assert.match(html, /data-cross-method-stability/i);
  assert.match(html, /data-cross-method-status/i);
  assert.match(html, /data-cross-method-uncertainty/i);
  assert.match(html, /stabilityRows/i);
  assert.match(html, /crossMethodRowsForTopics/i);
});

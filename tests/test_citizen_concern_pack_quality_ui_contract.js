const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI loads optional concern-pack quality artifact", () => {
  const html = readCitizenHtml();
  assert.match(html, /function\s+concernPackQualityPathForMethod\s*\(/i);
  assert.match(html, /concern_pack_quality_votes\.json/i);
  assert.match(html, /concern_pack_quality_declared\.json/i);
  assert.match(html, /loadConcernPackQualityRows\s*\(/i);
  assert.match(html, /concernPackQualityById/i);
});

test("citizen UI exposes weak-pack markers in tags and hints", () => {
  const html = readCitizenHtml();
  assert.match(html, /data-pack-weak/i);
  assert.match(html, /data-pack-weak-hint/i);
  assert.match(html, /paquete débil/i);
  assert.match(html, /paquetes débiles/i);
  assert.match(html, /calidad del paquete/i);
});

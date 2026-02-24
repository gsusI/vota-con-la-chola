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
  assert.match(html, /fetchJson\(["']\.\/data\/concern_pack_quality\.json["']\)/i);
  assert.match(html, /loadConcernPackQualityRows\s*\(/i);
  assert.match(html, /concernPackQualityById/i);
});

test("citizen UI exposes weak-pack markers in tags and hints", () => {
  const html = readCitizenHtml();
  assert.match(html, /data-pack-weak/i);
  assert.match(html, /data-pack-weak-hint/i);
  assert.match(html, /pack_debil/i);
  assert.match(html, /packs_weak/i);
  assert.match(html, /pack_quality/i);
});

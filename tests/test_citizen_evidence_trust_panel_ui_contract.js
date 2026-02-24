const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI loads evidence trust panel module", () => {
  const html = readCitizenHtml();
  assert.match(html, /<script\s+src=["']\.\/evidence_trust_panel\.js["']><\/script>/i);
  assert.match(html, /function\s+buildEvidenceTrustPanel\s*\(/i);
  assert.match(html, /function\s+renderEvidenceTrustPanel\s*\(/i);
});

test("citizen UI renders evidence trust panel markers in party cards", () => {
  const html = readCitizenHtml();
  assert.match(html, /data-evidence-trust-panel/i);
  assert.match(html, /data-evidence-trust-freshness/i);
  assert.match(html, /fuente_/i);
  assert.match(html, /edad_fuente=/i);
  assert.match(html, /metodo=/i);
});

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI loads unknown explainability module", () => {
  const html = readCitizenHtml();
  assert.match(html, /<script\s+src=["']\.\/unknown_explainability\.js["']><\/script>/i);
});

test("citizen UI includes unknown explainability contract markers", () => {
  const html = readCitizenHtml();
  assert.match(html, /renderUnknownExplainabilityHint\s*\(/i);
  assert.match(html, /data-unknown-explainability/i);
  assert.match(html, /data-unknown-explainability-summary/i);
});

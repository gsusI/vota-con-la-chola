const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI exposes preset recovery banner actions", () => {
  const html = readCitizenHtml();
  assert.match(html, /data-preset-clear-hash/i);
  assert.match(html, /data-preset-copy-canonical/i);
  assert.match(html, /presetHashWasNormalized/i);
  assert.match(html, /presetRecoveredFrom/i);
});

test("citizen UI normalizes canonical preset hash when needed", () => {
  const html = readCitizenHtml();
  assert.match(html, /presetCanonicalHash/i);
  assert.match(html, /history\.replaceState\(\{\},\s*\"\",\s*`\$\{u\.pathname\}\$\{u\.search\}\$\{u\.hash\}`\)/i);
});

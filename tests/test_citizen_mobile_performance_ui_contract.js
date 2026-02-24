const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI defines mobile interaction latency markers", () => {
  const html = readCitizenHtml();
  assert.match(html, /SEARCH_INPUT_DEBOUNCE_MS\s*=\s*120/i);
  assert.match(html, /RENDER_COMPARE_SCHEDULE\s*=\s*["']raf["']/i);
  assert.match(html, /MOBILE_LATENCY_OBS_VERSION\s*=\s*["']v1["']/i);
  assert.match(html, /function\s+scheduleRenderCompare\s*\(/i);
  assert.match(html, /function\s+markInputLatencySampleStart\s*\(/i);
  assert.match(html, /function\s+commitInputLatencySample\s*\(/i);
  assert.match(html, /addEventListener\("input",\s*onConcernSearchInputRaw\)/i);
  assert.match(html, /addEventListener\("input",\s*onTopicSearchInputRaw\)/i);
});

test("citizen UI includes mobile-friendly rendering and reduced-motion guards", () => {
  const html = readCitizenHtml();
  assert.match(html, /content-visibility\s*:\s*auto/i);
  assert.match(html, /@media\s*\(max-width:\s*760px\)/i);
  assert.match(html, /@media\s*\(prefers-reduced-motion:\s*reduce\)/i);
});

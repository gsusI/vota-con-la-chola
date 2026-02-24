const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI defines mobile latency observability markers", () => {
  const html = readCitizenHtml();
  assert.match(html, /MOBILE_LATENCY_OBS_VERSION\s*=\s*["']v1["']/i);
  assert.match(html, /MOBILE_LATENCY_STORAGE_KEY\s*=\s*["']vclc_mobile_latency_samples_v1["']/i);
  assert.match(html, /function\s+markInputLatencySampleStart\s*\(/i);
  assert.match(html, /function\s+commitInputLatencySample\s*\(/i);
  assert.match(html, /__vclcMobileLatencyExport/i);
  assert.match(html, /__vclcMobileLatencySummary/i);
  assert.match(html, /addEventListener\("input",\s*onConcernSearchInputRaw\)/i);
  assert.match(html, /addEventListener\("input",\s*onTopicSearchInputRaw\)/i);
});

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI defines concern-pack outcome telemetry markers", () => {
  const html = readCitizenHtml();
  assert.match(html, /CONCERN_PACK_OUTCOME_TELEMETRY_VERSION\s*=\s*["']v1["']/i);
  assert.match(html, /CONCERN_PACK_OUTCOME_STORAGE_KEY\s*=\s*["']vclc_concern_pack_outcome_events_v1["']/i);
  assert.match(html, /function\s+recordConcernPackOutcomeEvent\s*\(/i);
  assert.match(html, /function\s+summarizeConcernPackOutcomeEvents\s*\(/i);
  assert.match(html, /__vclcConcernPackOutcomeSummary/i);
  assert.match(html, /__vclcConcernPackOutcomeExport/i);
  assert.match(html, /__vclcConcernPackOutcomeClear/i);
});

test("citizen UI records key concern-pack outcome events", () => {
  const html = readCitizenHtml();
  assert.match(html, /recordConcernPackOutcomeEvent\("pack_selected"/i);
  assert.match(html, /recordConcernPackOutcomeEvent\("pack_cleared"/i);
  assert.match(html, /recordConcernPackOutcomeEvent\("topic_open_with_pack"/i);
  assert.match(html, /<span>pack_follow<\/span>/i);
});

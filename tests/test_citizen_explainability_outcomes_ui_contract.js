const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI defines explainability outcomes telemetry markers", () => {
  const html = readCitizenHtml();
  assert.match(html, /EXPLAINABILITY_OUTCOME_TELEMETRY_VERSION\s*=\s*["']v1["']/i);
  assert.match(html, /EXPLAINABILITY_OUTCOME_STORAGE_KEY\s*=\s*["']vclc_explainability_outcome_events_v1["']/i);
  assert.match(html, /function\s+recordExplainabilityOutcomeEvent\s*\(/i);
  assert.match(html, /function\s+summarizeExplainabilityOutcomeEvents\s*\(/i);
  assert.match(html, /__vclcExplainabilityOutcomeSummary/i);
  assert.match(html, /__vclcExplainabilityOutcomeExport/i);
  assert.match(html, /__vclcExplainabilityOutcomeClear/i);
});

test("citizen UI wires glossary and help-copy interactions to explainability outcomes telemetry", () => {
  const html = readCitizenHtml();
  assert.match(html, /data-explainability-glossary=["']1["']/i);
  assert.match(html, /data-explainability-term=/i);
  assert.match(html, /data-explainability-copy=["']1["']/i);
  assert.match(html, /recordExplainabilityOutcomeEvent\("explainability_glossary_opened"/i);
  assert.match(html, /recordExplainabilityOutcomeEvent\("explainability_glossary_term_interacted"/i);
  assert.match(html, /recordExplainabilityOutcomeEvent\("explainability_help_copy_interacted"/i);
  assert.match(html, /installExplainabilityOutcomeTelemetry\s*\(/i);
});

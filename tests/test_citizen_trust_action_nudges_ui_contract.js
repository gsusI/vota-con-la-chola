const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI defines trust-action nudge telemetry markers", () => {
  const html = readCitizenHtml();
  assert.match(html, /TRUST_ACTION_NUDGE_TELEMETRY_VERSION\s*=\s*["']v1["']/i);
  assert.match(html, /TRUST_ACTION_NUDGE_STORAGE_KEY\s*=\s*["']vclc_trust_action_nudge_events_v1["']/i);
  assert.match(html, /function\s+recordTrustActionNudgeEvent\s*\(/i);
  assert.match(html, /__vclcTrustActionNudgeSummary/i);
  assert.match(html, /__vclcTrustActionNudgeExport/i);
  assert.match(html, /__vclcTrustActionNudgeClear/i);
});

test("citizen UI exposes next-evidence nudge markers and click wiring", () => {
  const html = readCitizenHtml();
  assert.match(html, /function\s+buildTrustActionNudge\s*\(/i);
  assert.match(html, /function\s+renderTrustActionNudge\s*\(/i);
  assert.match(html, /data-trust-action-nudge/i);
  assert.match(html, /data-trust-action-nudge-link/i);
  assert.match(html, /trust_next_evidence/i);
  assert.match(html, /recordTrustActionNudgeEvent\("trust_action_nudge_shown"/i);
  assert.match(html, /recordTrustActionNudgeEvent\("trust_action_nudge_clicked"/i);
});

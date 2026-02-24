const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI loads onboarding funnel module", () => {
  const html = readCitizenHtml();
  assert.match(html, /<script\s+src=["']\.\/onboarding_funnel\.js["']><\/script>/i);
});

test("citizen onboarding includes next-action CTA contract markers", () => {
  const html = readCitizenHtml();
  assert.match(html, /data-onboard-next/i);
  assert.match(html, /runOnboardingAction\s*\(/i);
  assert.match(html, /computeOnboardingContract\s*\(/i);
});

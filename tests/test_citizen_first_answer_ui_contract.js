const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI loads first-answer accelerator module", () => {
  const html = readCitizenHtml();
  assert.match(html, /<script\s+src=["']\.\/first_answer_accelerator\.js["']><\/script>/i);
});

test("citizen onboarding exposes first-answer CTA markers", () => {
  const html = readCitizenHtml();
  assert.match(html, /data-first-answer-run/i);
  assert.match(html, /data-first-answer-run-inline/i);
  assert.match(html, /runFirstAnswerRecommendation\s*\(/i);
  assert.match(html, /computeFirstAnswerPlanFromState\s*\(/i);
});

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI defines coherence drilldown link builders", () => {
  const html = readCitizenHtml();
  assert.match(html, /function\s+resolveConcernIdForTopic\s*\(/i);
  assert.match(html, /function\s+buildCoherenceDrilldownLink\s*\(/i);
  assert.match(html, /searchParams\.set\("party_id"/i);
  assert.match(html, /searchParams\.set\("topic_id"/i);
  assert.match(html, /searchParams\.set\("concern"/i);
  assert.match(html, /searchParams\.set\("view",\s*view\)/i);
  assert.match(html, /searchParams\.set\("bucket",\s*bucket\)/i);
  assert.match(html, /searchParams\.set\("source",\s*"citizen_coherence"\)/i);
});

test("coherence cards expose strict drilldown markers for mismatch trace links", () => {
  const html = readCitizenHtml();
  assert.match(html, /data-coherence-drilldown-link="1"/i);
  assert.match(html, /data-party-id="\$\{esc\(String\(pid\)\)\}"/i);
  assert.match(html, /data-topic-id="\$\{esc\(/i);
  assert.match(html, /data-concern-id="\$\{esc\(/i);
  assert.match(html, /auditTid/i);
  assert.match(html, /drillConcernId/i);
  assert.match(html, /Auditar mismatch/i);
});

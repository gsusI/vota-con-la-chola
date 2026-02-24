const test = require("node:test");
const assert = require("node:assert/strict");

const trust = require("../ui/citizen/evidence_trust_panel.js");

test("evidence trust panel computes freshness, trust level, and drilldown metadata", () => {
  const got = trust.buildEvidenceTrustPanel({
    as_of_date: "2026-02-23",
    computed_method: "combined",
    coverage_ratio: 0.7,
    coverage: {
      evidence_count_total: 42,
      members_total: 120,
      members_with_signal: 90,
      last_evidence_date: "2026-02-10",
    },
    links: {
      explorer_temas: "../explorer-temas/?topic_id=1",
      explorer_positions: "../explorer/?t=topic_positions",
      explorer_evidence: "../explorer/?t=topic_evidence",
    },
  });

  assert.equal(got.panel_version, "evidence_trust_panel_v1");
  assert.equal(got.method, "combined");
  assert.equal(got.method_label, "combinado");
  assert.equal(got.source_age_days, 13);
  assert.equal(got.freshness_tier, "fresh");
  assert.equal(got.trust_level, "high");
  assert.equal(got.evidence_count_total, 42);
  assert.equal(got.has_drilldown, true);
  assert.equal(got.drilldown_total, 3);
  assert.equal(got.should_show, true);
});

test("evidence trust panel handles missing dates and links deterministically", () => {
  const got = trust.buildEvidenceTrustPanel({
    as_of_date: "2026-02-23",
    method: "declared",
    coverage_ratio: 0.15,
    coverage: {
      evidence_count_total: 0,
      members_total: 0,
      members_with_signal: 0,
      last_evidence_date: "",
    },
    links: {},
  });

  assert.equal(got.method, "declared");
  assert.equal(got.method_label, "dichos");
  assert.equal(got.source_age_days, null);
  assert.equal(got.freshness_tier, "unknown");
  assert.equal(got.has_drilldown, false);
  assert.equal(got.drilldown_total, 0);
  assert.equal(got.trust_level, "low");
  assert.ok(Array.isArray(got.trust_reasons));
  assert.ok(got.trust_reasons.includes("source_age_unknown"));
  assert.ok(got.trust_reasons.includes("missing_drilldown_links"));
});

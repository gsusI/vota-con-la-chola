const test = require("node:test");
const assert = require("node:assert/strict");

const trust = require("../ui/citizen/evidence_trust_panel.js");

test("trust-action nudge picks low-trust unknown candidate with evidence link", () => {
  const got = trust.buildTrustActionNudge({
    view_mode: "topic",
    concern_id: "vivienda",
    concern_label: "Vivienda",
    topic_id: 101,
    topic_label: "Alquiler",
    rows: [
      {
        party_id: 2,
        party_label: "Partido B",
        stance: "unclear",
        trust_level: "low",
        coverage_ratio: 0.18,
        evidence_count_total: 12,
        links: { explorer_evidence: "../explorer/?t=topic_evidence&topic_id=101&party_id=2" },
      },
      {
        party_id: 1,
        party_label: "Partido A",
        stance: "support",
        trust_level: "high",
        coverage_ratio: 0.7,
        evidence_count_total: 20,
        links: { explorer_evidence: "../explorer/?t=topic_evidence&topic_id=101&party_id=1" },
      },
    ],
  });

  assert.equal(got.nudge_version, "trust_action_nudge_v1");
  assert.equal(got.should_show, true);
  assert.ok(got.selected);
  assert.equal(got.selected.party_id, 2);
  assert.equal(got.selected.kind, "evidence_click");
  assert.equal(got.selected.reason_code, "unknown_with_trust_gap");
  assert.match(String(got.selected.message_short || ""), /Partido B/);
  assert.match(String(got.selected.link_target || ""), /party_id=2/);
});

test("trust-action nudge tie-breaks deterministically by party label", () => {
  const got = trust.buildTrustActionNudge({
    view_mode: "concern",
    concern_id: "sanidad",
    rows: [
      {
        party_id: 9,
        party_label: "Zeta",
        stance: "no_signal",
        trust_level: "medium",
        coverage_ratio: 0.2,
        evidence_count_total: 3,
        links: { explorer_evidence: "../explorer/?p=9" },
      },
      {
        party_id: 8,
        party_label: "Alfa",
        stance: "no_signal",
        trust_level: "medium",
        coverage_ratio: 0.2,
        evidence_count_total: 3,
        links: { explorer_evidence: "../explorer/?p=8" },
      },
    ],
  });

  assert.equal(got.should_show, true);
  assert.equal(got.selected.party_label, "Alfa");
  assert.equal(got.selected.party_id, 8);
});

test("trust-action nudge hides when no evidence links are available", () => {
  const got = trust.buildTrustActionNudge({
    view_mode: "topic",
    topic_id: 42,
    rows: [
      {
        party_id: 1,
        party_label: "Sin link",
        stance: "unclear",
        trust_level: "low",
        coverage_ratio: 0.1,
        evidence_count_total: 0,
        links: {},
      },
    ],
  });

  assert.equal(got.should_show, false);
  assert.equal(got.selected, null);
  assert.equal(got.available_candidates_total, 0);
});

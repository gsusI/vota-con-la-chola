const test = require("node:test");
const assert = require("node:assert/strict");

const stability = require("../ui/citizen/cross_method_stability.js");

test("cross-method stability reports stable on aligned comparable stances", () => {
  const got = stability.buildCrossMethodStability({
    rows: [
      { votes: "support", declared: "support", combined: "support" },
      { votes: "oppose", declared: "oppose", combined: "oppose" },
      { votes: "support", declared: "support", combined: "support" },
    ],
  });

  assert.equal(got.stability_version, "cross_method_stability_v1");
  assert.equal(got.status, "stable");
  assert.equal(got.uncertainty_level, "low");
  assert.equal(got.pair_stats.votes_declared.mismatch, 0);
  assert.equal(got.pair_stats.combined_votes.mismatch, 0);
  assert.equal(got.weighted_stability_score, 1);
});

test("cross-method stability reports uncertain when declared signal is mostly unknown", () => {
  const got = stability.buildCrossMethodStability({
    rows: [
      { votes: "support", declared: "no_signal", combined: "support" },
      { votes: "oppose", declared: "unclear", combined: "oppose" },
      { votes: "support", declared: "no_signal", combined: "support" },
      { votes: "oppose", declared: "mixed", combined: "oppose" },
    ],
  });

  assert.equal(got.status, "uncertain");
  assert.ok(Array.isArray(got.uncertainty_reasons));
  assert.ok(got.uncertainty_reasons.includes("low_votes_declared_comparable"));
  assert.ok(got.coverage_by_method.declared.unknown_pct >= 0.75);
  assert.equal(got.uncertainty_level, "high");
});

test("cross-method stability reports unstable on high votes-vs-declared mismatch", () => {
  const got = stability.buildCrossMethodStability({
    rows: [
      { votes: "support", declared: "oppose", combined: "support" },
      { votes: "oppose", declared: "support", combined: "oppose" },
      { votes: "support", declared: "oppose", combined: "support" },
      { votes: "oppose", declared: "support", combined: "oppose" },
      { votes: "support", declared: "oppose", combined: "support" },
      { votes: "oppose", declared: "support", combined: "oppose" },
    ],
    min_comparable_ratio: 0.1,
    high_mismatch_threshold: 0.35,
  });

  assert.equal(got.status, "unstable");
  assert.ok(got.uncertainty_reasons.includes("high_votes_declared_mismatch"));
  assert.equal(got.pair_stats.votes_declared.mismatch_pct_of_comparable, 1);
  assert.ok(got.weighted_stability_score < 0.55);
});

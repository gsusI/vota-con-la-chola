const test = require("node:test");
const assert = require("node:assert/strict");

const explainability = require("../ui/citizen/unknown_explainability.js");

test("unknown explainability flags no_signal-dominant uncertainty", () => {
  const got = explainability.buildUnknownExplainability({
    counts: { support: 1, unclear: 2, no_signal: 7 },
    total: 10,
  });

  assert.equal(got.explainability_version, "unknown_explainability_v1");
  assert.equal(got.dominant_unknown, "no_signal");
  assert.equal(got.should_show, true);
  assert.equal(got.unknown_total, 9);
  assert.equal(got.unknown_ratio, 0.9);
  assert.match(String(got.reason_label || ""), /sin_senal/i);
});

test("unknown explainability flags low-coverage unclear dominance", () => {
  const got = explainability.buildUnknownExplainability({
    counts: { support: 1, unclear: 5, no_signal: 1 },
    total: 7,
    coverage_ratio: 1 / 7,
  });

  assert.equal(got.dominant_unknown, "unclear");
  assert.equal(got.should_show, true);
  assert.equal(got.unknown_total, 6);
  assert.equal(got.reason_label, "unknown por cobertura baja");
  assert.match(String(got.reduce_uncertainty || ""), /umbral/i);
});

test("unknown explainability flags mixed uncertainty when no cause dominates", () => {
  const got = explainability.buildUnknownExplainability({
    counts: { support: 2, unclear: 2, no_signal: 2 },
    total: 6,
  });

  assert.equal(got.dominant_unknown, "mixed");
  assert.equal(got.should_show, true);
  assert.equal(got.unknown_total, 4);
  assert.equal(got.unknown_ratio, 0.666667);
  assert.equal(got.reason_label, "unknown mixto");
});

test("unknown explainability hides hint when no unknown cells exist", () => {
  const got = explainability.buildUnknownExplainability({
    counts: { support: 2, oppose: 1, mixed: 1 },
  });

  assert.equal(got.dominant_unknown, "none");
  assert.equal(got.should_show, false);
  assert.equal(got.unknown_total, 0);
});

const test = require("node:test");
const assert = require("node:assert/strict");

const funnel = require("../ui/citizen/onboarding_funnel.js");

test("funnel picks apply_pack first when suggested pack exists", () => {
  const got = funnel.computeFunnelState({
    packReady: false,
    concernReady: false,
    topicReady: false,
    alignmentReady: false,
    preferenceReady: false,
    hasRecommendedPack: true,
    hasRecommendedConcern: true,
    hasRecommendedTopic: true,
  });
  assert.equal(got.next_action.id, "apply_pack");
  assert.equal(got.required_total, 4);
  assert.equal(got.required_done, 0);
  assert.equal(got.required_completion_pct, 0);
});

test("funnel skips pack when no recommendation and advances to concern", () => {
  const got = funnel.computeFunnelState({
    packReady: false,
    concernReady: false,
    topicReady: false,
    alignmentReady: false,
    preferenceReady: false,
    hasRecommendedPack: false,
    hasRecommendedConcern: true,
    hasRecommendedTopic: true,
  });
  assert.equal(got.next_action.id, "select_concern");
  const packStep = got.steps.find((s) => s.id === "pack");
  assert.ok(packStep);
  assert.equal(packStep.required, false);
  assert.equal(packStep.done, true);
});

test("funnel action order after concern is topic then alignment then preference", () => {
  const topicPending = funnel.computeFunnelState({
    packReady: true,
    concernReady: true,
    topicReady: false,
    alignmentReady: false,
    preferenceReady: false,
    hasRecommendedPack: true,
    hasRecommendedConcern: true,
    hasRecommendedTopic: true,
  });
  assert.equal(topicPending.next_action.id, "open_topic");

  const alignmentPending = funnel.computeFunnelState({
    packReady: true,
    concernReady: true,
    topicReady: true,
    alignmentReady: false,
    preferenceReady: false,
    hasRecommendedPack: true,
    hasRecommendedConcern: true,
    hasRecommendedTopic: true,
  });
  assert.equal(alignmentPending.next_action.id, "open_alignment");

  const preferencePending = funnel.computeFunnelState({
    packReady: true,
    concernReady: true,
    topicReady: true,
    alignmentReady: true,
    preferenceReady: false,
    hasRecommendedPack: true,
    hasRecommendedConcern: true,
    hasRecommendedTopic: true,
  });
  assert.equal(preferencePending.next_action.id, "set_preference");
  assert.equal(preferencePending.required_done, 3);
  assert.equal(preferencePending.required_completion_pct, 0.75);
});

test("funnel returns done when all required steps are complete", () => {
  const got = funnel.computeFunnelState({
    packReady: true,
    concernReady: true,
    topicReady: true,
    alignmentReady: true,
    preferenceReady: true,
    hasRecommendedPack: true,
    hasRecommendedConcern: true,
    hasRecommendedTopic: true,
  });
  assert.equal(got.next_action.id, "done");
  assert.equal(got.required_done, 4);
  assert.equal(got.required_completion_pct, 1);
});

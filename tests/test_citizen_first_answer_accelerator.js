const test = require("node:test");
const assert = require("node:assert/strict");

const accelerator = require("../ui/citizen/first_answer_accelerator.js");

test("first-answer accelerator ranks concerns/topics and preserves evidence links", () => {
  const got = accelerator.computeFirstAnswerPlan({
    concerns: [
      { id: "vivienda", label: "Vivienda" },
      { id: "sanidad", label: "Sanidad" },
    ],
    topics: [
      {
        topic_id: 101,
        label: "Vivienda y alquiler",
        is_high_stakes: true,
        stakes_rank: 1,
        concern_ids: ["vivienda"],
        links: {
          explorer_temas: "../explorer-temas/?topic_id=101",
          explorer_positions: "../explorer/?t=topic_positions&topic_id=101",
          explorer_evidence: "../explorer/?t=topic_evidence&topic_id=101",
        },
      },
      {
        topic_id: 102,
        label: "Vivienda social",
        is_high_stakes: false,
        stakes_rank: 2,
        concern_ids: ["vivienda"],
        links: {
          explorer_temas: "../explorer-temas/?topic_id=102",
        },
      },
      {
        topic_id: 201,
        label: "Listas de espera",
        is_high_stakes: true,
        stakes_rank: 1,
        concern_ids: ["sanidad"],
        links: {
          explorer_temas: "../explorer-temas/?topic_id=201",
        },
      },
    ],
    parties: [{ party_id: 1 }, { party_id: 2 }, { party_id: 3 }],
    positions: [
      { topic_id: 101, party_id: 1, stance: "support", confidence: 0.9 },
      { topic_id: 101, party_id: 2, stance: "oppose", confidence: 0.8 },
      { topic_id: 101, party_id: 3, stance: "support", confidence: 0.7 },
      { topic_id: 102, party_id: 1, stance: "unclear", confidence: 0.2 },
      { topic_id: 102, party_id: 2, stance: "no_signal", confidence: 0.0 },
      { topic_id: 102, party_id: 3, stance: "support", confidence: 0.6 },
      { topic_id: 201, party_id: 1, stance: "no_signal", confidence: 0.0 },
      { topic_id: 201, party_id: 2, stance: "unclear", confidence: 0.1 },
      { topic_id: 201, party_id: 3, stance: "no_signal", confidence: 0.0 },
    ],
  });

  assert.equal(got.fallback_used, false);
  assert.equal(got.reason, "ranked");
  assert.equal(got.concern_rank[0].concern_id, "vivienda");
  assert.equal(got.recommended.concern_id, "vivienda");
  assert.equal(got.recommended.topic_id, 101);
  assert.equal(got.recommended.reason, "ranked");
  assert.match(String(got.recommended.links.explorer_evidence || ""), /topic_id=101/);
  assert.ok(Number(got.recommended.score || 0) > 0);
});

test("first-answer accelerator uses deterministic fallback when concern ranking is empty", () => {
  const got = accelerator.computeFirstAnswerPlan({
    concerns: [{ id: "empleo", label: "Empleo" }],
    topics: [
      {
        topic_id: 301,
        label: "Productividad",
        is_high_stakes: false,
        stakes_rank: null,
        concern_ids: [],
        links: {
          explorer_temas: "../explorer-temas/?topic_id=301",
        },
      },
    ],
    parties: [{ party_id: 1 }, { party_id: 2 }],
    positions: [],
  });

  assert.equal(got.fallback_used, true);
  assert.equal(got.reason, "fallback");
  assert.ok(got.recommended);
  assert.equal(got.recommended.concern_id, "empleo");
  assert.equal(got.recommended.topic_id, 301);
  assert.equal(got.recommended.reason, "fallback");
});

test("first-answer accelerator tie-breaks equal-scored topics deterministically by topic order", () => {
  const got = accelerator.computeFirstAnswerPlan({
    concerns: [{ id: "vivienda", label: "Vivienda" }],
    topics: [
      {
        topic_id: 101,
        label: "A topic",
        is_high_stakes: false,
        stakes_rank: 2,
        concern_ids: ["vivienda"],
      },
      {
        topic_id: 102,
        label: "B topic",
        is_high_stakes: false,
        stakes_rank: 2,
        concern_ids: ["vivienda"],
      },
    ],
    parties: [{ party_id: 1 }, { party_id: 2 }],
    positions: [
      { topic_id: 101, party_id: 1, stance: "support", confidence: 0.8 },
      { topic_id: 101, party_id: 2, stance: "oppose", confidence: 0.8 },
      { topic_id: 102, party_id: 1, stance: "support", confidence: 0.8 },
      { topic_id: 102, party_id: 2, stance: "oppose", confidence: 0.8 },
    ],
  });

  assert.equal(got.fallback_used, false);
  assert.equal(got.recommended.topic_id, 101);
  assert.equal(got.concern_rank[0].top_topic.topic_id, 101);
});

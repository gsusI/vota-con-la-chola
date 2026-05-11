const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readClasificacionesHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "leaderboards.html");
  return fs.readFileSync(p, "utf8");
}

test("leaderboards UI loads ranking robustness artifacts", () => {
  const html = readClasificacionesHtml();
  assert.match(html, /robustnessCombined:\s*["']\.\/data\/citizen_ranking_robustness\.json["']/i);
  assert.match(html, /robustnessVotes:\s*["']\.\/data\/citizen_ranking_robustness_votes\.json["']/i);
  assert.match(html, /robustnessDeclared:\s*["']\.\/data\/citizen_ranking_robustness_declared\.json["']/i);
  assert.match(html, /function\s+board11WhatChangesRanking\s*\(/i);
  assert.match(html, /data-ranking-robustness=["']1["']/i);
  assert.match(html, /data-ranking-what-changes=["']1["']/i);
});

test("leaderboards UI exposes ranking fragility helpers", () => {
  const html = readClasificacionesHtml();
  assert.match(html, /function\s+rankBandTagClass\s*\(/i);
  assert.match(html, /function\s+rankRangeLabel\s*\(/i);
  assert.match(html, /function\s+renderDriverTopics\s*\(/i);
  assert.match(html, /Qué podría mover la clasificación/i);
  assert.match(html, /Rango de métodos/i);
  assert.match(html, /Vecino crítico/i);
});

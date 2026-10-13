import test from "node:test";
import assert from "node:assert/strict";

import { agreementKind, buildQuestions, cellValue, partyReactions, pendingSubId, scoreParties, scorePercent } from "../ui/site/app/citizen/vota/votingAidModel.mjs";
import { axisParties, directionText, filterPeople, personAxisRows, personChoice, pushOf, readHash, votesForAxis, writeHash } from "../ui/site/app/citizen/vota/voteAtlasModel.mjs";

const parties = [
  { party_id: "a", label: "A" },
  { party_id: "b", label: "B" },
];

const multi = {
  statement_id: "eje-x",
  axis_id: "x",
  theme: "Tema",
  text: "Más X",
  votes_total: 3,
  cells: { a: { position: "agree", score: 0.9 }, b: { position: "mixed", score: -0.2 } },
  votes: [
    { id: "v1", vote_event_id: "e1", g: "m1", summary_yes: "Uno", parties: "SN", agree_vote: "Sí" },
    { id: "v2", vote_event_id: "e2", g: "m1", summary_yes: "Dos (misma moción)", parties: "SS", agree_vote: "Sí" },
    { id: "v3", vote_event_id: "e3", g: "m2", summary_yes: "Tres", parties: "NA", agree_vote: "No" },
  ],
};

test("continuous scores drive similarity, kinds and reactions", () => {
  assert.equal(cellValue("agree", 0.4), 0.4);
  assert.equal(cellValue("agree"), 1);
  assert.equal(cellValue("no_data", 0.5), undefined);
  assert.equal(agreementKind("agree", "agree", 0.9), "match");
  assert.equal(agreementKind("agree", "mixed", -0.2), "partial");
  assert.equal(agreementKind("disagree", "agree", 0.9), "clash");
  assert.equal(scorePercent(-1), 0);
  assert.equal(scorePercent(0.5), 75);
  const rows = scoreParties({ parties, statements: [multi] }, { "eje-x": "agree" });
  assert.equal(rows[0].partyId, "a");
  assert.equal(Math.round(rows[0].match * 100), 95);
  assert.equal(Math.round(rows[1].match * 100), 40);
  const r = partyReactions(multi, "agree", parties);
  assert.deepEqual(r.with.map((p) => p.party_id), ["a"]);
  assert.equal(r.partial[0].score, -0.2);
});

test("multi-vote statements get one concrete sub-question per initiative, reusing pool items", () => {
  const pool = { items: [{ id: "pool-e3", vote_event_id: "e3", title: "Título oficial", positions: { a: "disagree", b: "abstain" } }] };
  const qs = buildQuestions({ statements: [multi] }, pool);
  const st = qs.find((q) => q.statement_id === "eje-x");
  assert.deepEqual(st.subIds, ["eje-x~v1", "pool-e3"]);
  const sub = qs.find((q) => q.statement_id === "eje-x~v1");
  assert.equal(sub.parent, "eje-x");
  assert.equal(sub.source, "pool");
  assert.deepEqual(sub.cells, { a: { position: "agree" }, b: { position: "disagree" } });
  assert.equal(qs.find((q) => q.statement_id === "pool-e3").parent, "eje-x");
  const byId = Object.fromEntries(qs.map((q) => [q.statement_id, q]));
  assert.equal(pendingSubId(byId, { "eje-x": true }, {}), "eje-x~v1");
  assert.equal(pendingSubId(byId, { "eje-x": true }, { "eje-x~v1": "agree" }), "pool-e3");
  assert.equal(pendingSubId(byId, { "eje-x": true }, { "eje-x~v1": "agree" }, { "pool-e3": true }), null);
});

const atlas = {
  parties,
  axes: [{ axis_id: "x", label: "X", pos_short: "Más", neg_short: "Menos" }],
  party_axes: { a: { x: { score: 0.85, votes: 3 } }, b: { x: { score: -0.3, votes: 3 } } },
  votes: [
    { id: "v1", date: "2024-01-01", axes: [["x", "+", "alta"]] },
    { id: "v2", date: "2025-01-01", axes: [["y", "-", "media"], ["x", "-", "baja"]] },
  ],
};

test("atlas helpers", () => {
  assert.deepEqual(axisParties(atlas, "x").map((p) => p.party_id), ["b", "a"]);
  assert.equal(directionText(atlas.axes[0], 0.85), "Casi siempre hacia «Más»");
  assert.equal(directionText(atlas.axes[0], -0.3), "Tiende hacia «Menos»");
  assert.equal(directionText(atlas.axes[0], 0.1), "Dividido o neutral");
  const vs = votesForAxis(atlas, "x");
  assert.deepEqual(vs.map((v) => [v.id, v.sign, v.primary]), [["v2", "-", false], ["v1", "+", true]]);
  assert.equal(pushOf("S", "+"), "pos");
  assert.equal(pushOf("N", "+"), "neg");
  assert.equal(pushOf("A", "+"), "none");
});

test("people helpers", () => {
  const person = { name: "Ána Pérez", party_id: "a", first: 2, votes: "SN-", axes: { x: [-0.5, 4] } };
  assert.equal(personChoice(person, 1), ".");
  assert.equal(personChoice(person, 3), "N");
  assert.equal(filterPeople([person], { query: "ana perez" }).length, 1);
  assert.equal(filterPeople([person], { partyId: "b" }).length, 0);
  const rows = personAxisRows(atlas, person);
  assert.equal(rows[0].partyScore, 0.85);
  assert.equal(Math.round(rows[0].gap * 100), 135);
  assert.deepEqual(readHash(writeHash({ p: "p1", eje: "" })), { p: "p1" });
});

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CURRENT_VERSION, VOTING_AID_VERSIONS, otherVersions } from "../ui/site/app/citizen/vota/votingAidVersions.mjs";

test("every voting-aid version stays published with its own path, data and storage", () => {
  const here = path.dirname(fileURLToPath(import.meta.url));
  assert.equal(VOTING_AID_VERSIONS.filter((v) => v.current).length, 1);
  assert.equal(CURRENT_VERSION.path, "/citizen/vota/");
  for (const key of ["id", "path", "snapshot", "storageKey"]) {
    assert.equal(new Set(VOTING_AID_VERSIONS.map((v) => v[key])).size, VOTING_AID_VERSIONS.length, `${key} único por versión`);
  }
  for (const v of VOTING_AID_VERSIONS) {
    const file = path.join(here, "..", "ui", "site", "public", ...v.snapshot.split("/"));
    assert.ok(fs.existsSync(file), `falta ${v.snapshot}`);
    if (!v.current) assert.ok(fs.existsSync(path.join(here, "..", "ui", "site", "app", ...v.path.split("/").filter(Boolean), "page.js")), `falta la página ${v.path}`);
  }
  // The first version keeps the key its users already have answers under.
  assert.equal(VOTING_AID_VERSIONS.find((v) => v.id === "v1").storageKey, "vclc.votingAid.generales.v1");
  assert.deepEqual(otherVersions("v2").map((v) => v.id), ["v1"]);
});

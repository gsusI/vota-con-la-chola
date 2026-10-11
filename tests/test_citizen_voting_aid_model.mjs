import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  decodeShareCode,
  encodeShareCode,
  formatMatch,
  sanitizeState,
  scoreParties,
  shareCodeFromHash,
} from "../ui/gh-pages-next/app/citizen/vota/votingAidModel.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const publishedPath = path.join(here, "..", "ui", "gh-pages-next", "public", "citizen", "data", "voting_aid_generales_v1.json");

const snapshot = {
  parties: [
    { party_id: "a", label: "A" },
    { party_id: "b", label: "B" },
    { party_id: "c", label: "C" },
  ],
  statements: [
    { statement_id: "s1", cells: { a: { position: "agree" }, b: { position: "disagree" }, c: { position: "no_data" } } },
    { statement_id: "s2", cells: { a: { position: "abstain" }, b: { position: "disagree" }, c: { position: "no_data" } } },
    { statement_id: "s3", cells: { a: { position: "mixed" }, b: { position: "agree" }, c: { position: "no_data" } } },
  ],
};

test("scores use only answered statements with data and weigh important ones double", () => {
  const rows = scoreParties(snapshot, { s1: "agree", s2: "disagree" }, { s1: true });
  const byId = Object.fromEntries(rows.map((r) => [r.partyId, r]));
  // A: s1 agree/agree = 1 (x2), s2 disagree/abstain = 0.5 -> 2.5 / 3
  assert.equal(byId.a.match, 2.5 / 3);
  // B: s1 agree/disagree = 0 (x2), s2 disagree/disagree = 1 -> 1 / 3
  assert.equal(byId.b.match, 1 / 3);
  assert.equal(byId.a.compared, 2);
  // C has no data on anything: no score, sorted last, never imputed.
  assert.equal(byId.c.match, null);
  assert.equal(byId.c.compared, 0);
  assert.deepEqual(rows.map((r) => r.partyId), ["a", "b", "c"]);
});

test("neutral answers and skipped statements", () => {
  const rows = scoreParties(snapshot, { s3: "neutral" });
  const byId = Object.fromEntries(rows.map((r) => [r.partyId, r]));
  assert.equal(byId.a.match, 1); // neutral vs mixed (0)
  assert.equal(byId.b.match, 0.5); // neutral vs agree
  assert.equal(scoreParties(snapshot, {})[0].match, null);
});

test("share code round-trips and rejects codes for another statement set", () => {
  const code = encodeShareCode(snapshot.statements, { s1: "agree", s3: "disagree" }, { s3: true });
  assert.equal(code, "v1.a-D");
  assert.deepEqual(decodeShareCode(snapshot.statements, code), {
    answers: { s1: "agree", s3: "disagree" },
    important: { s3: true },
  });
  assert.equal(decodeShareCode(snapshot.statements, "v1.ad"), null);
  assert.equal(decodeShareCode(snapshot.statements, "v1.axz"), null);
  assert.equal(shareCodeFromHash("#r=v1.a-D"), "v1.a-D");
  assert.equal(shareCodeFromHash(""), null);
});

test("stored state drops unknown statements and invalid values", () => {
  const state = sanitizeState(snapshot.statements, {
    answers: { s1: "agree", gone: "agree", s2: "maybe" },
    important: { s1: true, s2: "yes" },
  });
  assert.deepEqual(state, { answers: { s1: "agree" }, important: { s1: true } });
  assert.equal(formatMatch(2 / 3), "67%");
  assert.equal(formatMatch(null), "—");
});

test("published snapshot is scorable end to end", () => {
  const published = JSON.parse(fs.readFileSync(publishedPath, "utf-8"));
  const answers = Object.fromEntries(published.statements.map((st) => [st.statement_id, "agree"]));
  const rows = scoreParties(published, answers);
  assert.equal(rows.length, published.parties.length);
  for (const row of rows) {
    assert.ok(row.match === null || (row.match >= 0 && row.match <= 1));
    assert.ok(row.compared <= published.statements.length);
  }
  const code = encodeShareCode(published.statements, answers);
  assert.deepEqual(decodeShareCode(published.statements, code).answers, answers);
});

test("theme labels, agreement kinds and next unanswered", async () => {
  const { themeLabel, agreementKind, nextUnansweredIndex } = await import(
    "../ui/gh-pages-next/app/citizen/vota/votingAidModel.mjs"
  );
  assert.equal(themeLabel({ statement_id: "educacion-x", concern_id: "educacion" }), "Educación");
  assert.equal(themeLabel({ statement_id: "territorio-amnistia", concern_id: "seguridad_justicia" }), "Modelo territorial");
  assert.equal(themeLabel({ statement_id: "exterior-armas", concern_id: null }), "Política exterior");
  assert.equal(themeLabel({ statement_id: "raro", concern_id: null }), "Otros");
  assert.equal(agreementKind("agree", "agree"), "match");
  assert.equal(agreementKind("agree", "disagree"), "clash");
  assert.equal(agreementKind("neutral", "agree"), "partial");
  assert.equal(agreementKind("agree", "no_data"), "none");
  const sts = snapshot.statements;
  assert.equal(nextUnansweredIndex(sts, { s1: "agree" }, 0), 1);
  assert.equal(nextUnansweredIndex(sts, { s3: "agree" }, 2), 0);
  assert.equal(nextUnansweredIndex(sts, { s1: "agree", s2: "agree", s3: "agree" }, 0), -1);
});

test("endless mode: merged questions, balanced order, share v2, milestones, reactions", async () => {
  const m = await import("../ui/gh-pages-next/app/citizen/vota/votingAidModel.mjs");
  const snap = JSON.parse(fs.readFileSync(publishedPath, "utf-8"));
  const poolPath = path.join(here, "..", "ui", "gh-pages-next", "public", "citizen", "data", "voting_aid_pool_v1.json");
  const pool = JSON.parse(fs.readFileSync(poolPath, "utf-8"));
  const questions = m.buildQuestions(snap, pool);
  assert.equal(questions.length, snap.statements.length + pool.items.length);
  assert.equal(new Set(questions.map((q) => q.statement_id)).size, questions.length);

  const order = m.playOrder(questions, 42);
  assert.equal(order.length, questions.length);
  assert.deepEqual(order.slice(0, snap.statements.length), snap.statements.map((s) => s.statement_id));
  assert.deepEqual(m.playOrder(questions, 42), order, "same seed, same order");
  // First 30 pool questions alternate sides: no side gets more than half.
  const byId = Object.fromEntries(questions.map((q) => [q.statement_id, q]));
  const firstPool = order.slice(snap.statements.length, snap.statements.length + 30).map((id) => byId[id].side);
  for (const side of ["psoe", "pp"]) assert.ok(firstPool.filter((s) => s === side).length <= 15, side);

  const answers = { [order[0]]: "agree" };
  const skipped = { [order[1]]: true };
  assert.equal(m.nextQuestionId(order, answers, skipped), order[2]);
  const allAnswered = Object.fromEntries(order.map((id) => [id, "neutral"]));
  assert.equal(m.nextQuestionId(order, allAnswered, {}), null);

  // Share v2 round trip on a sparse set including pool questions, and rejection on a changed set.
  const some = { [order[0]]: "agree", [order[200]]: "disagree", [order[333]]: "neutral" };
  const code = m.encodeShareCodeV2(questions, some, { [order[200]]: true });
  assert.deepEqual(m.decodeAnyShareCode(questions, code), { answers: some, important: { [order[200]]: true } });
  assert.equal(m.decodeShareCodeV2(questions.slice(1), code), null);
  assert.equal(m.decodeShareCodeV2(questions, code.replace(/\.[^.]*$/u, ".zzzzz")), null);

  // Scores work over the merged list.
  const rows = m.scoreParties({ parties: snap.parties, statements: questions }, some);
  assert.ok(rows.every((r) => r.compared <= 3));

  assert.deepEqual(m.milestoneFor(0), { current: null, next: m.MILESTONES[0] });
  assert.equal(m.milestoneFor(34).current.at, 33);
  assert.equal(m.milestoneFor(1000).next, null);

  const q = { cells: { a: { position: "agree" }, b: { position: "disagree" }, c: { position: "abstain" }, d: { position: "no_data" } } };
  const parties = ["a", "b", "c", "d"].map((id) => ({ party_id: id, label: id }));
  const r = m.partyReactions(q, "agree", parties);
  assert.deepEqual([r.with.map((p) => p.party_id), r.against.map((p) => p.party_id), r.partial.map((p) => p.party_id), r.none.map((p) => p.party_id)], [["a"], ["b"], ["c"], ["d"]]);
  const g = m.groupDetails([{ answer: "agree", position: "agree" }, { answer: "agree", position: "disagree" }]);
  assert.equal(g.match.length + g.clash.length, 2);
});

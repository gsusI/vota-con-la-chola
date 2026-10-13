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
} from "../ui/site/app/citizen/vota/votingAidModel.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const publishedPath = path.join(here, "..", "ui", "site", "public", "citizen", "data", "voting_aid_generales_v1.json");

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
    "../ui/site/app/citizen/vota/votingAidModel.mjs"
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
  const m = await import("../ui/site/app/citizen/vota/votingAidModel.mjs");
  const snap = JSON.parse(fs.readFileSync(publishedPath, "utf-8"));
  const poolPath = path.join(here, "..", "ui", "site", "public", "citizen", "data", "voting_aid_pool_v1.json");
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
  assert.deepEqual(r.partial[0].mix, { yes: 0, abstain: 1, no: 0 });

  // Pill fill: deputies for one vote; for an axis, votes counted in the direction that supports the statement.
  assert.deepEqual(m.voteMix({ counts: { a: [2, 1, 1] } }, "a"), { yes: 0.5, abstain: 0.25, no: 0.25 });
  const axis = {
    axis_id: "x",
    cells: { a: {}, b: {} },
    votes: [
      { parties: "SN", agree_vote: "Sí" },
      { parties: "SA", agree_vote: "No" },
      { parties: "N=", agree_vote: "No" },
      { parties: "S", agree_vote: "Sí" },
    ],
  };
  assert.deepEqual(m.voteMix(axis, "a"), { yes: 0.75, abstain: 0, no: 0.25 });
  assert.deepEqual(m.voteMix(axis, "b"), { yes: 0, abstain: 2 / 3, no: 1 / 3 });
  assert.equal(m.voteMix(axis, "zz"), null);
  const g = m.groupDetails([{ answer: "agree", position: "agree" }, { answer: "agree", position: "disagree" }]);
  assert.equal(g.match.length + g.clash.length, 2);
});

test("podium share text has no answers, only top three", async () => {
  const { podiumShareText } = await import("../ui/site/app/citizen/vota/votingAidModel.mjs");
  const text = podiumShareText(
    [
      { label: "A", match: 0.8 },
      { label: "B", match: 0.6 },
      { label: "C", match: 0.5 },
      { label: "D", match: 0.4 },
      { label: "E", match: null },
    ],
    42,
    "https://example.invalid/vota/",
  );
  assert.equal(text, "Mi podio en «¿Con quién coincides?» tras 42 votaciones del Congreso:\n🥇 A 80%\n🥈 B 60%\n🥉 C 50%\nhttps://example.invalid/vota/");
});

test("AI prompts carry exactly what was voted and never the user's answers", async () => {
  const m = await import("../ui/site/app/citizen/vota/votingAidModel.mjs");
  const snap = JSON.parse(fs.readFileSync(publishedPath, "utf-8"));
  const poolPath = path.join(here, "..", "ui", "site", "public", "citizen", "data", "voting_aid_pool_v1.json");
  const pool = JSON.parse(fs.readFileSync(poolPath, "utf-8"));
  const questions = m.buildQuestions(snap, pool);
  const poolQ = questions.find((q) => q.source === "pool" && q.text_url);
  const curated = questions.find((q) => q.source === "curated" && q.votes.length > 1);

  const why = m.buildAiPrompt(poolQ, snap.parties);
  assert.ok(why.includes(poolQ.text));
  assert.ok(why.includes(poolQ.source_url) && why.includes(poolQ.text_url));
  assert.ok(why.includes(poolQ.proposer));
  for (const p of snap.parties) assert.ok(why.includes(`${p.label}:`), p.label);

  const explain = m.buildAiPrompt(poolQ, snap.parties, { mode: "explain" });
  assert.ok(explain.includes(poolQ.text));
  assert.ok(!explain.includes(poolQ.proposer), "explain mode must not reveal the proposer");
  assert.ok(!/ sí, \d+ no/u.test(explain), "explain mode must not include results");
  assert.ok(!snap.parties.some((p) => explain.includes(`${p.label}:`)), "explain mode must not include party votes");

  const one = m.buildAiPrompt(curated, snap.parties, { partyId: "pp" });
  assert.ok(one.includes(curated.text) && one.includes("Votación 2:"));
  assert.ok(one.includes("PP:") && !one.includes("PSOE:"));

  for (const prompt of [why, explain, one]) {
    assert.ok(!/Tu respuesta|De acuerdo|En desacuerdo|Me da igual/u.test(prompt), "no user answer in prompt");
    assert.ok(prompt.length < 4000, `prompt too long: ${prompt.length}`);
  }
  // Explain mode masks proposers named inside official titles and leaves out curated outcome notes.
  const jornada = questions.find((q) => q.statement_id === "empleo-jornada-37-5");
  const jornadaExplain = m.buildAiPrompt(jornada, snap.parties, { mode: "explain" });
  assert.ok(!/Junts|VOX|Popular|decayó|aprobadas/u.test(jornadaExplain), jornadaExplain);
  assert.equal(
    m.maskProposers("Proposición de Ley del Grupo Parlamentario Socialista, sobre algo."),
    "Proposición de Ley de un grupo parlamentario, sobre algo.",
  );
  // Compound proposer lists go whole, up to the purpose clause (real title, vivienda-alquiler-temporada 2024-12-17).
  assert.equal(
    m.maskProposers(
      "Proposición de Ley de los Grupos Parlamentarios Plurinacional SUMAR, Republicano, Euskal Herria Bildu y Mixto, para la regulación de los contratos de alquiler temporales y alquiler de habitaciones.",
    ),
    "Proposición de Ley de varios grupos parlamentarios, para la regulación de los contratos de alquiler temporales y alquiler de habitaciones.",
  );
  assert.equal(
    m.maskProposers("Proposición no de Ley del Grupo Parlamentario Popular en el Congreso relativa a la vivienda."),
    "Proposición no de Ley de un grupo parlamentario relativa a la vivienda.",
  );
  assert.equal(m.maskProposers("Proposición presentada por el Grupo Parlamentario VOX sobre algo."), "Proposición sobre algo.");
  // No curated or pool vote title names a group after masking ("País Vasco" is a place, not EAJ-PNV).
  const groupName = /SUMAR|Republicano|Bildu|Mixto|Socialista|Popular|VOX|Junts|Grupo Parlamentario Vasco|EAJ|PNV/u;
  const titles = [
    ...snap.statements.flatMap((s) => (s.votes || []).map((v) => v.title)),
    ...pool.items.map((it) => it.title),
    ...questions.flatMap((q) => m.buildAiPrompt(q, snap.parties, { mode: "explain" }).split("\n").filter((l) => l.startsWith("- Qué se votó"))),
  ].filter(Boolean);
  assert.ok(titles.length >= 300, `titles scanned: ${titles.length}`);
  for (const t of titles) assert.ok(!groupName.test(m.maskProposers(t)), m.maskProposers(t));

  const links = m.aiLinks(why);
  assert.deepEqual(links.map((l) => l.id), ["chatgpt", "claude", "gemini"]);
  assert.equal(decodeURIComponent(links[0].href.split("?q=")[1]), why);
  assert.equal(decodeURIComponent(links[1].href.split("?q=")[1]), why);
  assert.equal(links[2].prefill, false);
});

test("official-text highlights attach to questions, flag omnibus and reach AI prompts", async () => {
  const m = await import("../ui/site/app/citizen/vota/votingAidModel.mjs");
  const snap = JSON.parse(fs.readFileSync(publishedPath, "utf-8"));
  const dataDir = path.join(here, "..", "ui", "site", "public", "citizen", "data");
  const pool = JSON.parse(fs.readFileSync(path.join(dataDir, "voting_aid_pool_v1.json"), "utf-8"));
  const highlights = JSON.parse(fs.readFileSync(path.join(dataDir, "voting_aid_highlights_v1.json"), "utf-8"));
  const questions = m.attachHighlights(m.buildQuestions(snap, pool), highlights);
  const withText = questions.filter((q) => q.highlights.length);
  assert.ok(withText.length >= 80, `questions with official text: ${withText.length}`);
  const omnibus = questions.filter((q) => q.omnibus);
  assert.ok(omnibus.length >= 5);
  for (const q of withText) for (const h of q.highlights) assert.match(h.doc.url, /^https:\/\/www\.(boe|congreso)\.es\//u);

  const q = omnibus.find((x) => x.source === "pool");
  const prompt = m.buildAiPrompt(q, snap.parties);
  assert.ok(prompt.includes("votación ómnibus") && prompt.includes("encabezados literales"));
  assert.ok(prompt.includes(q.highlights[0].doc.bullets[0]));
  assert.ok(prompt.length < 6000, `prompt length ${prompt.length}`);
  const explain = m.buildAiPrompt(q, snap.parties, { mode: "explain" });
  assert.ok(explain.includes("enumera las principales"));
  assert.ok(!snap.parties.some((p) => explain.includes(`${p.label}:`)));

  // Questions without any official text still work (every published vote has one today, so strip it).
  const bare = m.attachHighlights(m.buildQuestions(snap, pool), { docs: {}, by_vote: {} })[0];
  assert.equal(bare.highlights.length, 0);
  assert.equal(bare.omnibus, false);
  assert.ok(m.buildAiPrompt(bare, snap.parties).length > 0);
});

test("prefilled AI links stay under the URL budget for every question", async () => {
  const m = await import("../ui/site/app/citizen/vota/votingAidModel.mjs");
  const snap = JSON.parse(fs.readFileSync(publishedPath, "utf-8"));
  const dataDir = path.join(here, "..", "ui", "site", "public", "citizen", "data");
  const pool = JSON.parse(fs.readFileSync(path.join(dataDir, "voting_aid_pool_v1.json"), "utf-8"));
  const highlights = JSON.parse(fs.readFileSync(path.join(dataDir, "voting_aid_highlights_v1.json"), "utf-8"));
  const bullets = JSON.parse(fs.readFileSync(path.join(dataDir, "voting_aid_vote_bullets_v1.json"), "utf-8"));
  const questions = m.attachHighlights(m.buildQuestions(snap, pool), highlights, bullets);
  for (const q of questions) {
    for (const opts of [{}, { mode: "explain" }, { partyId: "pp" }]) {
      const p = m.linkPrompt(q, snap.parties, opts);
      assert.ok(encodeURIComponent(p).length <= m.MAX_LINK_PROMPT_CHARS, `${q.statement_id} ${JSON.stringify(opts)}`);
      assert.ok(p.includes(q.source === "pool" ? q.text.slice(0, 40) : q.text.slice(0, 40)));
    }
  }
});

test("«Qué se votaba» bullets attach per vote, reach prompts and never reveal votes before answering", async () => {
  const m = await import("../ui/site/app/citizen/vota/votingAidModel.mjs");
  const snap = JSON.parse(fs.readFileSync(publishedPath, "utf-8"));
  const dataDir = path.join(here, "..", "ui", "site", "public", "citizen", "data");
  const pool = JSON.parse(fs.readFileSync(path.join(dataDir, "voting_aid_pool_v1.json"), "utf-8"));
  const highlights = JSON.parse(fs.readFileSync(path.join(dataDir, "voting_aid_highlights_v1.json"), "utf-8"));
  const bullets = JSON.parse(fs.readFileSync(path.join(dataDir, "voting_aid_vote_bullets_v1.json"), "utf-8"));
  const questions = m.attachHighlights(m.buildQuestions(snap, pool), highlights, bullets);
  const withBullets = questions.filter((q) => q.whatVoted.some((w) => w.status === "ok"));
  assert.ok(withBullets.length >= 250, `questions with bullets: ${withBullets.length}`);
  for (const q of questions) {
    assert.ok(q.whatVoted.length >= 1);
    for (const w of q.whatVoted) {
      assert.ok(["ok", "sin_texto_oficial"].includes(w.status), `${q.statement_id} ${w.status}`);
      if (w.status !== "ok") continue;
      assert.ok(w.bullets.length >= 1 && w.bullets.length <= 6);
      for (const b of w.bullets) assert.ok(b.text && b.locator);
      assert.match(w.url, /^https:\/\/www\.(boe|congreso)\.es\//u);
    }
  }
  // Motions (PNL) now carry their official text too.
  assert.ok(questions.filter((q) => q.kind === "pnl" && q.whatVoted[0].status === "ok").length >= 60);

  const q = withBullets.find((x) => x.source === "pool");
  const explain = m.buildAiPrompt(q, snap.parties, { mode: "explain" });
  const first = q.whatVoted.find((w) => w.status === "ok").bullets[0];
  assert.ok(explain.includes(first.text) && explain.includes(`[${first.locator}]`));
  assert.ok(!snap.parties.some((p) => explain.includes(`${p.label}:`)));
  assert.ok(!explain.includes(q.proposer || "\u0000"), "explain prompt must not name the proposer");
  const compact = m.buildAiPrompt(q, snap.parties, { mode: "explain", compact: true });
  assert.ok(compact.includes(first.text) && compact.length <= explain.length);

  // Votes without official text are marked, never invented.
  const bare = questions.find((x) => x.whatVoted.every((w) => w.status === "sin_texto_oficial"));
  if (bare) assert.ok(!m.buildAiPrompt(bare, snap.parties).includes("Qué se votaba (resumen"));
});

test("«Ramificaciones» attach official figures and both-sided effects, and reach the AI prompts", async () => {
  const m = await import("../ui/site/app/citizen/vota/votingAidModel.mjs");
  const dataDir = path.join(here, "..", "ui", "site", "public", "citizen", "data");
  const read = (f) => JSON.parse(fs.readFileSync(path.join(dataDir, f), "utf-8"));
  const pool = read("voting_aid_pool_v1.json");
  const highlights = read("voting_aid_highlights_v1.json");
  const bullets = read("voting_aid_vote_bullets_v1.json");
  const index = read("voting_aid_vote_impacts_v1.json");
  const shardFiles = fs.readdirSync(path.join(dataDir, index.meta.shards.dir));
  assert.ok(shardFiles.length > 1 && shardFiles.length <= m.IMPACT_SHARDS);
  const impacts = m.mergeImpacts(index, shardFiles.map((f) => read(`${index.meta.shards.dir}/${f}`)));
  // Every vote sits in the shard the browser will ask for.
  for (const f of shardFiles) for (const vid of Object.keys(read(`${index.meta.shards.dir}/${f}`).by_vote)) assert.equal(`${m.impactShardKey(vid)}.json`, f);
  for (const version of ["v1", "v2"]) {
    const snap = read(`voting_aid_generales_${version}.json`);
    const questions = m.attachHighlights(m.buildQuestions(snap, pool), highlights, bullets, impacts);
    const withRamif = questions.filter((q) => q.ramifications);
    assert.ok(withRamif.length >= 3, `${version}: ${withRamif.length}`);
    for (const q of withRamif) {
      const r = q.ramifications;
      assert.ok(r.facts.length >= 1 && r.facts.length <= 3, q.statement_id);
      for (const f of r.facts) assert.ok(f.text && f.period && f.source && /^https:\/\//u.test(f.url));
      for (const v of r.votes) {
        if (v.indirect.length) assert.deepEqual([...new Set(v.indirect.map((e) => e.kind))].sort(), ["beneficio_esperado", "riesgo_senalado"]);
      }
      // Shown before answering: the explain prompt carries the figures and the ask, never a party's vote.
      const explain = m.buildAiPrompt(q, snap.parties, { mode: "explain" });
      assert.ok(explain.includes(m.RAMIFICATIONS_ASK) && explain.includes(r.facts[0].text), q.statement_id);
      assert.ok(!snap.parties.some((p) => explain.includes(`${p.label}:`)));
      const effect = r.votes.find((v) => v.indirect.length)?.indirect[0];
      if (effect) assert.ok(explain.includes(effect.text));
      // Even a clipped link keeps the figures (they go before the vote details in the compact prompt).
      assert.ok(m.linkPrompt(q, snap.parties, { mode: "explain" }).includes(r.facts[0].text.slice(0, 60)), q.statement_id);
    }
    // Every question, key or concrete vote, says who it affects.
    assert.equal(withRamif.length, questions.length, version);
    // Without impacts data questions still work and do not invent figures.
    const [bare] = m.attachHighlights(m.buildQuestions(snap, pool), highlights, bullets, null);
    assert.ok(!bare.ramifications && !m.buildAiPrompt(bare, snap.parties).includes("A quién afecta (cifras oficiales)"));
  }
});

test("topic navigation: one topic list for key questions and votes, next open question inside a topic", async () => {
  const m = await import("../ui/site/app/citizen/vota/votingAidModel.mjs");
  const read = (name) => JSON.parse(fs.readFileSync(path.join(here, "..", "ui", "site", "public", "citizen", "data", name), "utf-8"));
  const questions = m.buildQuestions(read("voting_aid_generales_v2.json"), read("voting_aid_pool_v1.json"));
  const byId = Object.fromEntries(questions.map((q) => [q.statement_id, q]));
  const order = m.playOrder(questions, 7);
  const groups = m.topicGroups(order, byId);

  // Every played question sits in exactly one topic; older pool themes fold into the map's topics.
  assert.equal(groups.reduce((n, g) => n + g.ids.length, 0), order.length);
  const names = groups.map((g) => g.topic);
  for (const old of ["Empleo y pensiones", "Transporte", "Política exterior", "Defensa", "Igualdad", "Instituciones"]) {
    assert.ok(!names.includes(old), old);
  }
  assert.equal(m.questionTopic({ theme: "Transporte" }), "Energía, clima y transporte");
  assert.equal(m.questionTopic({ theme: "Vivienda" }), "Vivienda");
  assert.equal(m.questionTopic({}), "Otros");
  assert.equal(names[0], "Vivienda");
  assert.equal(names[names.length - 1], "Otros");

  // Inside a topic: key questions first, then votes, in play order; answered and skipped ones are passed over.
  const vivienda = groups.find((g) => g.topic === "Vivienda").ids;
  assert.ok(vivienda.length > 2);
  assert.equal(byId[vivienda[0]].source, "curated");
  assert.equal(m.nextInTopic(vivienda, byId), vivienda[0]);
  assert.equal(m.nextInTopic(vivienda, byId, { [vivienda[0]]: "agree" }, { [vivienda[1]]: true }), vivienda[2]);
  const all = Object.fromEntries(vivienda.map((id) => [id, "neutral"]));
  assert.equal(m.nextInTopic(vivienda, byId, all), null);

  // A split key question is replaced by its concrete votes, listed after it.
  const parent = vivienda.find((id) => byId[id].subIds?.length);
  const split = { [parent]: true };
  const withSubs = m.topicGroups(order, byId, split).find((g) => g.topic === "Vivienda").ids;
  for (const sid of byId[parent].subIds) assert.ok(withSubs.includes(sid), sid);

  // ← → step through all key questions across topics, and separately through all votes: never from one to the other.
  const lists = m.stepLists(m.topicGroups(order, byId, split), byId);
  const curatedIds = questions.filter((q) => q.source === "curated").map((q) => q.statement_id);
  assert.deepEqual([...lists.keys].sort(), [...curatedIds].sort());
  assert.ok(lists.votes.every((id) => byId[id].source !== "curated"));
  for (const sid of byId[parent].subIds) assert.ok(lists.votes.includes(sid), sid);
  const lastKeyOfTopic = lists.keys.findIndex((id, i) => i < lists.keys.length - 1 && m.questionTopic(byId[id]) !== m.questionTopic(byId[lists.keys[i + 1]]));
  const crossing = m.stepNeighbors(lists, byId, lists.keys[lastKeyOfTopic]);
  assert.equal(crossing.isKey, true);
  assert.equal(byId[crossing.next].source, "curated"); // the next topic's first key, not this topic's votes
  assert.notEqual(m.questionTopic(byId[crossing.next]), m.questionTopic(byId[lists.keys[lastKeyOfTopic]]));
  assert.equal(m.stepNeighbors(lists, byId, lists.keys[0]).prev, null);
  const firstSub = m.stepNeighbors(lists, byId, byId[parent].subIds[0]);
  assert.equal(firstSub.isKey, false);
  assert.ok(!firstSub.next || byId[firstSub.next].source !== "curated");
  assert.equal(m.nextInTopic(withSubs, byId, {}, {}, split), byId[parent].subIds[0]);
});

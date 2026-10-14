import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  axisInSentence,
  factLine,
  formatSigned,
  generateRounds,
  lanes,
  mapAxes,
  mapHash,
  nearestParty,
  parseMapHash,
  partyPoint,
  placeLabels,
  planeX,
  planeY,
  rankByDistance,
  roundPoints,
  storedAnswers,
  streakOf,
  togglePick,
  userAxisValues,
  verdict,
} from "../ui/site/app/citizen/vota/mapModel.mjs";

const atlas = {
  topics: [
    { topic_id: "t1", label: "Uno" },
    { topic_id: "t2", label: "Dos" },
  ],
  axes: [
    { axis_id: "b", topic_id: "t2", label: "Israel y Palestina", neg_short: "No", pos_short: "Sí", votes: 20 },
    { axis_id: "a", topic_id: "t1", label: "Impuestos", neg_short: "Bajar", pos_short: "Subir", votes: 30 },
    { axis_id: "c", topic_id: "t1", label: "Poco", neg_short: "-", pos_short: "+", votes: 3 },
  ],
  parties: [
    { party_id: "p1", label: "Uno" },
    { party_id: "p2", label: "Dos" },
    { party_id: "p3", label: "Tres" },
  ],
  party_axes: {
    p1: { a: { score: 0.646, votes: 30 }, b: { score: 0.1, votes: 20 }, c: { score: 1, votes: 3 } },
    p2: { a: { score: -0.67, votes: 30 }, b: { score: -0.9, votes: 20 } },
    p3: { a: { score: 0.2, votes: 30 } },
  },
};

test("axes: topic order, ≥10 votes unless all", () => {
  assert.deepEqual(mapAxes(atlas).map((a) => a.axis_id), ["a", "b"]);
  assert.deepEqual(mapAxes(atlas, { all: true }).map((a) => a.axis_id), ["a", "c", "b"]);
  assert.equal(partyPoint(atlas, "p1", "a"), 65);
  assert.equal(partyPoint(atlas, "p3", "b"), null);
  assert.equal(formatSigned(-77), "−77");
  assert.equal(formatSigned(0), "0");
  assert.equal(axisInSentence("Impuestos"), "impuestos");
  assert.equal(axisInSentence("Israel y Palestina"), "Israel y Palestina");
});

test("lanes: greedy by x, gap or widths", () => {
  const items = [{ x: 50 }, { x: 10 }, { x: 52 }, { x: 55 }, { x: 90 }];
  assert.equal(lanes(items, 4), 2);
  const byX = Object.fromEntries(items.map((t) => [t.x, t.lane]));
  assert.deepEqual(byX, { 10: 0, 50: 0, 52: 1, 55: 0, 90: 0 });
  const wide = [{ x: 10, w: 10 }, { x: 18, w: 10 }, { x: 30, w: 4 }];
  assert.equal(lanes(wide, 1), 2);
  assert.equal(lanes([], 4), 1);
});

test("user axis values: answer × pole, averaged; pool answers ignored", () => {
  const snapshot = {
    statements: [
      { statement_id: "s1", axis_id: "a", pole: "+" },
      { statement_id: "s2", axis_id: "a", pole: "-" },
      { statement_id: "s3", axis_id: "b", pole: "-" },
    ],
  };
  const answers = storedAnswers({ answers: { s1: "agree", s2: "neutral", s3: "agree", pool9: "agree", bad: "maybe" } });
  assert.deepEqual(answers, { s1: "agree", s2: "neutral", s3: "agree", pool9: "agree" });
  assert.deepEqual(userAxisValues(snapshot, answers), { a: 0.5, b: -1 });
  assert.deepEqual(userAxisValues(snapshot, {}), {});
  assert.equal(nearestParty(atlas, "a", 0.5).party.party_id, "p1");
  assert.equal(nearestParty(atlas, "b", -1).party.party_id, "p2");
  const ranked = rankByDistance(atlas, "a", "b", 0.6, 0);
  assert.deepEqual(ranked.map((r) => r.party.party_id), ["p1", "p2"]);
  assert.equal(ranked[0].d, 11);
});

test("picks and hash round-trip", () => {
  assert.deepEqual(togglePick(["a", "b", "c", "d"], "e"), ["b", "c", "d", "e"]);
  assert.deepEqual(togglePick(["a", "b", "c"], "d", 3), ["b", "c", "d"]);
  assert.deepEqual(togglePick(["a", "b"], "a"), ["b"]);
  const opts = { partyIds: ["psoe", "pp", "vox"], axisIds: ["a", "b"] };
  assert.deepEqual(parseMapHash("#vista=mapa&p=psoe,zzz,pp,psoe", opts), { view: "mapa", picks: ["psoe", "pp"] });
  assert.deepEqual(parseMapHash("#vista=mapa&p=", opts), { view: "mapa", picks: [] });
  assert.deepEqual(parseMapHash("#vista=brujula&x=a&y=nope", opts), { view: "brujula", x: "a" });
  assert.deepEqual(parseMapHash("#vista=raro", opts), { view: "mapa" });
  assert.equal(mapHash({ view: "mapa", picks: ["psoe", "pp"], x: "a" }), "#vista=mapa&p=psoe,pp");
  assert.equal(mapHash({ view: "brujula", picks: ["psoe"], x: "a", y: "b" }), "#vista=brujula&x=a&y=b");
  assert.equal(parseMapHash(mapHash({ view: "adivina", game: 42 }), opts).game, 42);
});

test("compass labels: flip near the right edge, push down on clash", () => {
  const pts = placeLabels([{ x: 100, y: 100 }, { x: 105, y: 104 }, { x: 560, y: 300 }], 600);
  const right = pts.find((p) => p.x === 560);
  assert.equal(right.align, "right");
  const [a, b] = pts.filter((p) => p.x < 200);
  assert.equal(a.ty, 100);
  assert.equal(b.ty, 116);
  assert.equal(b.lead, true);
});

test("compass labels terminate at every plane width (fractional positions once looped forever)", () => {
  const real = JSON.parse(readFileSync(new URL("../ui/site/public/citizen/data/vote_atlas_v1.json", import.meta.url)));
  const ids = real.axes.map((a) => a.axis_id);
  for (let size = 280; size <= 640; size += 1) {
    const small = size < 480;
    const pad = small ? 20 : 28;
    for (const [x, y] of [["fiscalidad", "territorial_autogobierno"], [ids[0], ids[ids.length - 1]], ["seguridad_penal", "inmigracion"]]) {
      const pts = real.parties
        .map((p) => ({ sx: partyPoint(real, p.party_id, x), sy: partyPoint(real, p.party_id, y) }))
        .filter((p) => p.sx !== null && p.sy !== null)
        .map((p) => ({ x: planeX(p.sx, size, pad), y: planeY(p.sy, size, pad) }));
      const out = placeLabels(pts, size, { labelW: small ? 84 : 120, lineH: small ? 15 : 16 });
      assert.equal(out.length, pts.length);
    }
  }
});

test("rounds: deterministic per seed, no repeats, mix of surprising and clear", () => {
  const real = JSON.parse(readFileSync(new URL("../ui/site/public/citizen/data/vote_atlas_v1.json", import.meta.url)));
  const r1 = generateRounds(real, 12345);
  const r2 = generateRounds(real, 12345);
  const r3 = generateRounds(real, 999);
  assert.equal(r1.length, 10);
  assert.deepEqual(r1, r2);
  assert.notDeepEqual(r1, r3);
  for (const rounds of [r1, r3, generateRounds(real, 7)]) {
    const keys = rounds.map((r) => `${r.party_id}|${r.axis_id}`);
    assert.equal(new Set(keys).size, keys.length);
    const surprising = rounds.filter((r) => Math.abs(r.real) < 35).length;
    assert.ok(surprising >= 3 && surprising <= 5, `surprising ${surprising}`);
    for (const r of rounds) assert.ok(real.axes.find((a) => a.axis_id === r.axis_id).votes >= 10);
  }
  // Sanity of the data the map shows.
  assert.equal(partyPoint(real, "psoe", "fiscalidad"), 65);
  assert.equal(partyPoint(real, "vox", "inmigracion"), -77);
  assert.equal(partyPoint(real, "junts", "fiscalidad"), -1);
  assert.equal(mapAxes(real).length, mapAxes(real, { all: true }).filter((a) => a.votes >= 10).length);
});

test("scoring", () => {
  assert.equal(roundPoints(60, 65), 95);
  assert.equal(roundPoints(-100, 100), 0);
  assert.equal(verdict(10), "¡Diana!");
  assert.equal(verdict(25), "Muy cerca");
  assert.equal(verdict(50), "Te has quedado lejos");
  assert.equal(verdict(51), "Ni de lejos");
  assert.equal(streakOf([95, 40, 90, 100]), 2);
  assert.equal(streakOf([95, 40]), 0);
  const axis = { neg_short: "Bajar", pos_short: "Subir" };
  assert.match(factLine(5, axis), /centro/u);
  assert.equal(factLine(80, axis), "Muy constante hacia «Subir».");
  assert.equal(factLine(-40, axis), "Inclinado hacia «Bajar», con excepciones.");
});

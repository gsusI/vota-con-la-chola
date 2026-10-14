import test from "node:test";
import assert from "node:assert/strict";

import {
  barGeometry,
  initials,
  latestVotes,
  organicMajority,
  partyAxisGroups,
  partyVoteCount,
  percent1,
  personDissents,
  personLegSummary,
  relatedVotes,
  sameVoteShares,
  searchExplore,
  seatBlocks,
  shortLabel,
  totalsFromPeople,
  voteDissenters,
  votesWord,
} from "../ui/site/app/citizen/vota/exploreModel.mjs";

const atlas = {
  parties: [
    { party_id: "a", label: "Alfa" },
    { party_id: "b", label: "Beta" },
    { party_id: "c", label: "Gamma" },
  ],
  topics: [{ topic_id: "t1", label: "Vivienda" }],
  axes: [
    { axis_id: "x", topic_id: "t1", label: "Alquiler", pos_short: "Más", neg_short: "Menos" },
    { axis_id: "y", topic_id: "t1", label: "Okupación", pos_short: "Más", neg_short: "Menos" },
  ],
  party_axes: { a: { x: { score: 0.5, votes: 12 }, y: { score: -0.2, votes: 3 } } },
  titles: ["Proyecto de Ley Orgánica de amnistía", "Ley de vivienda"],
  votes: [
    { id: "old", leg: "14", date: "2022-10-04", t: 1, parties: "SSS", axes: [] },
    { id: "v1", date: "2024-01-10", kind: "totalidad", t: 0, summary_yes: "Devolver la amnistía", parties: "NSS", totals: [33, 309, 0], axes: [] },
    { id: "v2", date: "2024-03-14", kind: "final", t: 0, summary_yes: "Aprobar la amnistía", parties: "S?N", totals: [178, 172, 0], axes: [["x", "+", "alta"]] },
    { id: "v3", date: "2024-05-01", kind: "pnl", t: 1, summary_yes: "Bajar el alquiler", parties: "SSA", totals: [200, 100, 40], axes: [["x", "+", "alta"]] },
    { id: "v4", date: "2024-06-01", kind: "convenio", t: 1, summary_yes: "Ratificar un tratado", parties: "SS=", totals: [300, 0, 0], axes: [] },
  ],
};

test("party counts and same-vote shares use XV votes, skipping '?' and ties", () => {
  assert.equal(partyVoteCount(atlas, "a"), 4);
  assert.equal(partyVoteCount(atlas, "b"), 3);
  const shares = sameVoteShares(atlas, "a");
  const beta = shares.find((r) => r.party_id === "b");
  assert.deepEqual([beta.same, beta.n], [2, 3]);
  const gamma = shares.find((r) => r.party_id === "c");
  assert.deepEqual([gamma.same, gamma.n], [0, 3]);
  assert.equal(shares[0].party_id, "b");
});

test("axis groups hide thin axes and bars grow from the centre", () => {
  const g = partyAxisGroups(atlas, "a");
  assert.equal(g.total, 2);
  assert.equal(g.shown, 1);
  assert.equal(g.groups[0].rows[0].axis.axis_id, "x");
  assert.equal(partyAxisGroups(atlas, "a", { minVotes: 1 }).shown, 2);
  assert.deepEqual(barGeometry(0.5), { left: 50, width: 25, side: "pos" });
  assert.deepEqual(barGeometry(-0.5), { left: 25, width: 25, side: "neg" });
});

test("latest votes, related votes, search and organic majority", () => {
  assert.deepEqual(latestVotes(atlas, 2).map((v) => v.id), ["v4", "v3"]);
  assert.deepEqual(latestVotes(atlas, 2, { onAxes: true }).map((v) => v.id), ["v3", "v2"]);
  assert.deepEqual(relatedVotes(atlas, atlas.votes[2]).map((v) => v.id), ["v1"]);
  const s = searchExplore({ atlas, people: null, query: "amnistia" });
  assert.deepEqual(s.votes.map((v) => v.id), ["v2", "v1"]);
  assert.equal(searchExplore({ atlas, people: null, query: "bet" }).parties[0].party_id, "b");
  assert.deepEqual(organicMajority(atlas.votes[2], atlas.titles[0]), { needed: 176, yes: 178, margin: 2, reached: true });
  assert.equal(organicMajority(atlas.votes[1], atlas.titles[0]), null, "a totalidad vote needs no absolute majority");
  assert.equal(organicMajority(atlas.votes[3], atlas.titles[1]), null);
  assert.equal(votesWord(2), "dos votos");
  assert.equal(votesWord(1), "un voto");
});

// people.votes: [id, path, date, kind, t, subgroup, leg]
const people = {
  parties: atlas.parties,
  votes: [
    ["old", "p", "2022-10-04", "pnl", 1, "", "14"],
    ["v1", "p", "2024-01-10", "totalidad", 0, "", "15"],
    ["v2", "p", "2024-03-14", "final", 0, "", "15"],
  ],
  people: [
    { id: "p1", name: "Ana Pérez", party_id: "a", legislatures: ["14", "15"], groups_by_leg: { 14: ["GS"] }, first: 0, votes: "SNS", rebels: [[1, "S"]], loyalty_by_leg: { 15: [0.5, 2] } },
    { id: "p2", name: "Luis Gómez", party_id: "a", legislatures: ["15"], first: 1, votes: "SS", rebels: [] },
    { id: "p3", name: "Eva Ruiz", party_id: null, legislatures: ["15"], first: 1, votes: "A-", rebels: [] },
    { id: "p4", name: "Old Timer", party_id: null, legislatures: ["14"], groups_by_leg: { 14: ["GP"] }, first: 0, votes: "N", rebels: [] },
  ],
};

test("person summaries read the person's own vote, not the party code in rebels", () => {
  const s = personLegSummary(people, people.people[0], "15");
  assert.deepEqual(s.counts, { S: 1, N: 1, A: 0, "-": 0 });
  assert.equal(s.seated, 2);
  assert.equal(s.participation, 1);
  assert.equal(s.loyalty, 0.5);
  assert.equal(s.rebels, 1);
  assert.deepEqual(personDissents(people.people[0]), [{ index: 1, own: "N", party: "S" }]);
  assert.equal(initials("Isabel Pozueta Fernández"), "IP");
  assert.equal(percent1(0.92867), "92,9 %");
  assert.equal(percent1(0.9996, { floor: true }), "99,9 %");
  assert.equal(shortLabel("corto"), "corto");
});

test("seat blocks group deputies by party (XV) or group (XIV), Otros last on ties", () => {
  const blocks = seatBlocks(people, 2);
  assert.deepEqual(
    blocks.map((b) => [b.key, b.counts.S, b.counts.N, b.counts["-"]]),
    [
      ["a", 2, 0, 0],
      ["otros", 0, 0, 1],
    ],
  );
  const xiv = seatBlocks(people, 0);
  assert.deepEqual(xiv.map((b) => b.label), ["PSOE", "PP"]);
  assert.deepEqual(totalsFromPeople(people, 1), [1, 1, 1]);
  assert.deepEqual(voteDissenters(people, 1).map((d) => [d.person.id, d.own, d.party]), [["p1", "N", "S"]]);
});

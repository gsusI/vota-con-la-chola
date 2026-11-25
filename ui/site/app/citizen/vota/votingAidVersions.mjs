// Every published version of the voting-aid test stays online in parallel: the newest is the default at
// /citizen/vota/, older ones keep their own URL, data file and answers (localStorage key), so anyone who took
// an earlier test can reopen it, review it and compare it with the new one. To publish a new version: add it
// first here with `current: true`, set the previous one's `current` to false and give it its own `path`;
// never rewrite an old version's snapshot file.

export const VOTING_AID_VERSIONS = [
  {
    id: "v3",
    current: true,
    path: "/citizen/vota/",
    snapshot: "citizen/data/voting_aid_generales_v3.json",
    storageKey: "vclc.votingAid.generales.v3",
    // Answers carry over from v2 except for questions whose wording changed (`seedSkip`): those are asked again.
    seedFrom: "v2",
    seedSkip: ["eje-lenguas"],
    // Salts the share codes, so a v2 link (same question ids) is not read as a v3 answer to a reworded question.
    shareSalt: "v3",
    released: "2026-11-25",
    label: "Por temas, revisada",
    summary: "Las mismas 29 preguntas clave; la de lenguas cooficiales incluye ahora la escuela, no solo el Congreso y los juzgados",
  },
  {
    id: "v2",
    current: false,
    path: "/citizen/vota/v2/",
    snapshot: "citizen/data/voting_aid_generales_v2.json",
    storageKey: "vclc.votingAid.generales.v2",
    // On first visit, carry over answers to questions both versions share (the endless-mode votes).
    seedFrom: "v1",
    released: "2026-10-13",
    label: "Por temas",
    summary: "29 preguntas clave que resumen 1.023 votaciones, cada una divisible en votaciones concretas",
  },
  {
    id: "v1",
    current: false,
    path: "/citizen/vota/v1/",
    snapshot: "citizen/data/voting_aid_generales_v1.json",
    storageKey: "vclc.votingAid.generales.v1",
    released: "2026-10-11",
    label: "Primera versión",
    summary: "33 afirmaciones respaldadas por 41 votaciones (1 a 3 por afirmación)",
  },
];

export const CURRENT_VERSION = VOTING_AID_VERSIONS.find((v) => v.current) || VOTING_AID_VERSIONS[0];

export function versionById(id) {
  return VOTING_AID_VERSIONS.find((v) => v.id === id) || CURRENT_VERSION;
}

/** The other versions, newest first, for links and comparisons. */
export function otherVersions(id) {
  return VOTING_AID_VERSIONS.filter((v) => v.id !== id);
}

export function formatReleased(iso) {
  const [y, m, d] = String(iso || "").split("-");
  return d ? `${Number(d)}/${Number(m)}/${y}` : String(iso || "");
}

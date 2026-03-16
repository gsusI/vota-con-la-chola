const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

async function loadHelpers() {
  const filePath = path.join(
    __dirname,
    "..",
    "ui",
    "gh-pages-next",
    "app",
    "political-positions",
    "personTrajectoryLoading.mjs",
  );
  return import(pathToFileURL(filePath).href);
}

test("default person view stays on default_rows mode", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", q: "", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };

  assert.equal(helpers.isDefaultPersonView(state), true);
  assert.equal(helpers.personTrajectoryScanMode(state), "default_rows");
  assert.equal(helpers.personTrajectoryHasActiveFilters(state), false);
});

test("exact topic selection switches person view to topic_preview mode", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", q: "", person: "", method: "all", stance: "all", topic: "Proyecto de Ley", party: "", sort: "person", limit: 180 };

  assert.equal(helpers.personTrajectoryNeedsExactTopicRows(state, 7), true);
  assert.equal(helpers.personTrajectoryNeedsTopicPreviewRows(state, 7), true);
  assert.equal(helpers.personTrajectoryScanMode(state, 7), "topic_preview");
  assert.deepEqual(
    helpers.nextPersonTrajectoryChunkIds({
      state,
      chunks: [{ chunk_id: "chunk-001" }, { chunk_id: "chunk-002" }],
      resolvedTopicId: 7,
      loadedChunks: {},
      currentRowsCount: 0,
      limit: 180,
    }),
    [],
  );
});

test("selective unresolved topic text switches person view to topic_preview mode", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", q: "", person: "", method: "all", stance: "all", topic: "vivienda social", party: "", sort: "person", limit: 180 };
  const searchIndex = {
    topic_tokens: {
      vivienda: [7, 8],
      social: [7],
      rural: [8],
    },
  };

  assert.deepEqual(
    helpers.candidateTopicPreviewTopicIds({ state, searchIndex }),
    [7],
  );
  assert.equal(helpers.personTrajectoryNeedsTopicPreviewRows(state, 0, [7]), true);
  assert.equal(helpers.personTrajectoryScanMode(state, 0, [7]), "topic_preview");
  assert.deepEqual(
    helpers.nextPersonTrajectoryChunkIds({
      state,
      chunks: [{ chunk_id: "chunk-001" }, { chunk_id: "chunk-002" }],
      previewTopicIds: [7],
      loadedChunks: {},
      currentRowsCount: 0,
      limit: 180,
    }),
    [],
  );
});

test("selective thematic q switches person view to topic_preview mode", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", q: "movilidad sostenible", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };
  const searchIndex = {
    topic_tokens: {
      movilidad: [1, 2],
      sostenible: [1],
      rural: [2],
    },
  };

  assert.deepEqual(
    helpers.candidateTopicPreviewTopicIds({ state, searchIndex, personIndex: [] }),
    [1],
  );
  assert.equal(helpers.personTrajectoryNeedsTopicPreviewRows(state, 0, [1]), true);
  assert.equal(helpers.personTrajectoryScanMode(state, 0, [1]), "topic_preview");
});

test("broad thematic q in topic mode switches person view to topic_discovery mode", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", q: "ley", searchMode: "topic", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };

  assert.equal(helpers.personTrajectoryNeedsTopicDiscovery(state, 0, [], [1, 2, 3]), true);
  assert.equal(helpers.personTrajectoryScanMode(state, 0, [], [1, 2, 3]), "topic_discovery");
  assert.deepEqual(
    helpers.nextPersonTrajectoryChunkIds({
      state,
      chunks: [{ chunk_id: "chunk-001" }, { chunk_id: "chunk-002" }],
      discoveryTopicIds: [1, 2, 3],
      loadedChunks: {},
      currentRowsCount: 0,
      limit: 180,
    }),
    [],
  );
});

test("broad unresolved Tema filter switches person view to topic_discovery mode", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", q: "", searchMode: "auto", person: "", method: "all", stance: "all", topic: "ley", party: "", sort: "person", limit: 180 };

  assert.equal(helpers.personTrajectoryNeedsTopicDiscovery(state, 0, [], [1, 2]), true);
  assert.equal(helpers.personTrajectoryScanMode(state, 0, [], [1, 2]), "topic_discovery");
});

test("concern-led discovery switches person view to topic_discovery mode", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", concern: "vivienda", q: "", searchMode: "auto", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };

  assert.equal(helpers.personTrajectoryHasActiveFilters(state), true);
  assert.equal(helpers.personTrajectoryNeedsTopicDiscovery(state, 0, [], [285, 250]), true);
  assert.equal(helpers.personTrajectoryScanMode(state, 0, [], [285, 250]), "topic_discovery");
});

test("pack-led discovery switches person view to topic_discovery mode", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", pack: "servicios_publicos", concern: "", q: "", searchMode: "auto", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };

  assert.equal(helpers.personTrajectoryHasActiveFilters(state), true);
  assert.equal(helpers.personTrajectoryNeedsTopicDiscovery(state, 0, [], [285, 250, 19]), true);
  assert.equal(helpers.personTrajectoryScanMode(state, 0, [], [285, 250, 19]), "topic_discovery");
  assert.deepEqual(
    helpers.nextPersonTrajectoryChunkIds({
      state,
      chunks: [{ chunk_id: "chunk-001" }, { chunk_id: "chunk-002" }],
      discoveryTopicIds: [285, 250, 19],
      loadedChunks: {},
      currentRowsCount: 0,
      limit: 180,
    }),
    [],
  );
});

test("searchMode=person disables thematic q preview", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", q: "movilidad sostenible", searchMode: "person", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };
  const searchIndex = {
    topic_tokens: {
      movilidad: [1, 2],
      sostenible: [1],
    },
  };

  assert.deepEqual(
    helpers.candidateTopicPreviewTopicIds({ state, searchIndex, personIndex: [] }),
    [],
  );
  assert.equal(helpers.personTrajectoryScanMode(state, 0, []), "progressive");
});

test("searchMode=topic overrides the nominal auto-guard", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", q: "movilidad sostenible", searchMode: "topic", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };
  const searchIndex = {
    topic_tokens: {
      movilidad: [1, 2],
      sostenible: [1],
    },
  };
  const personIndex = [
    { full_name: "Movilidad Sostenible", canonical_key: "movilidad-sostenible" },
  ];

  assert.deepEqual(
    helpers.candidateTopicPreviewTopicIds({ state, searchIndex, personIndex }),
    [1],
  );
  assert.equal(helpers.personTrajectoryScanMode(state, 0, [1]), "topic_preview");
});

test("nominal q does not get misrouted into thematic topic preview", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", q: "segura", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };
  const searchIndex = {
    topic_tokens: {
      seguridad: [7],
    },
  };
  const personIndex = [
    { full_name: "Bruno Segura", canonical_key: "bruno-segura" },
  ];

  assert.deepEqual(
    helpers.candidateTopicPreviewTopicIds({ state, searchIndex, personIndex }),
    [],
  );
  assert.equal(helpers.personTrajectoryScanMode(state, 0, []), "progressive");
});

test("filtered person view with default sort is progressive, not exhaustive", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", q: "ada", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };

  assert.equal(helpers.isDefaultPersonView(state), false);
  assert.equal(helpers.personTrajectoryScanMode(state), "progressive");
  assert.equal(helpers.personTrajectoryNeedsExhaustiveScan(state), false);
});

test("unfiltered advanced person sort uses static sort preview instead of chunks", async () => {
  const helpers = await loadHelpers();
  const chunks = [{ chunk_id: "chunk-001" }, { chunk_id: "chunk-002" }];
  const state = { mode: "person", q: "", person: "", method: "all", stance: "all", topic: "", party: "", sort: "confidence_desc", limit: 180 };

  assert.equal(helpers.personTrajectoryNeedsSortPreview(state), true);
  assert.equal(helpers.personTrajectoryScanMode(state), "sort_preview");
  assert.deepEqual(
    helpers.nextPersonTrajectoryChunkIds({
      state,
      chunks,
      loadedChunks: {},
      currentRowsCount: 0,
      limit: 180,
    }),
    [],
  );
});

test("non-default sort still requires exhaustive chunk scan", async () => {
  const helpers = await loadHelpers();
  const state = { mode: "person", q: "ada", person: "", method: "all", stance: "all", topic: "", party: "", sort: "confidence_desc", limit: 180 };

  assert.equal(helpers.personTrajectoryScanMode(state), "exhaustive");
  assert.equal(helpers.personTrajectoryNeedsExhaustiveScan(state), true);
});

test("progressive scan asks for one more chunk until row budget is met", async () => {
  const helpers = await loadHelpers();
  const chunks = [{ chunk_id: "chunk-001" }, { chunk_id: "chunk-002" }, { chunk_id: "chunk-003" }];
  const state = { mode: "person", q: "ada", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };

  assert.deepEqual(
    helpers.nextPersonTrajectoryChunkIds({
      state,
      chunks,
      loadedChunks: {},
      currentRowsCount: 40,
      limit: 180,
    }),
    ["chunk-001"],
  );

  assert.deepEqual(
    helpers.nextPersonTrajectoryChunkIds({
      state,
      chunks,
      loadedChunks: { "chunk-001": true },
      currentRowsCount: 180,
      limit: 180,
    }),
    [],
  );
});

test("structured filters narrow candidate chunks before exhaustive scan", async () => {
  const helpers = await loadHelpers();
  const chunks = [
    {
      chunk_id: "chunk-001",
      topic_tokens: ["vivienda", "energia"],
      party_tokens: ["psoe"],
      methods: ["combined", "votes"],
      stances: ["support", "mixed"],
    },
    {
      chunk_id: "chunk-002",
      topic_tokens: ["seguridad"],
      party_tokens: ["pp"],
      methods: ["declared"],
      stances: ["oppose"],
    },
  ];
  const state = { mode: "person", q: "", person: "", method: "declared", stance: "oppose", topic: "segur", party: "pp", sort: "confidence_desc", limit: 180 };

  assert.deepEqual(
    helpers.candidatePersonTrajectoryChunkIds({ state, chunks, personIndex: [] }),
    ["chunk-002"],
  );
  assert.deepEqual(
    helpers.nextPersonTrajectoryChunkIds({
      state,
      chunks,
      personIndex: [],
      loadedChunks: {},
      currentRowsCount: 0,
      limit: 180,
    }),
    ["chunk-002"],
  );
});

test("structured filters can narrow via search index even without chunk metadata", async () => {
  const helpers = await loadHelpers();
  const chunks = [
    { chunk_id: "chunk-001" },
    { chunk_id: "chunk-002" },
  ];
  const searchIndex = {
    topic_tokens: { seguridad: ["chunk-002"] },
    party_tokens: { pp: ["chunk-002"] },
    methods: { declared: ["chunk-002"] },
    stances: { oppose: ["chunk-002"] },
  };
  const state = { mode: "person", q: "", person: "", method: "declared", stance: "oppose", topic: "segur", party: "pp", sort: "confidence_desc", limit: 180 };

  assert.deepEqual(
    helpers.candidatePersonTrajectoryChunkIds({ state, chunks, personIndex: [], searchIndex }),
    ["chunk-002"],
  );
});

test("resolved exact topic can narrow candidate chunks via topic id search index", async () => {
  const helpers = await loadHelpers();
  const chunks = [
    { chunk_id: "chunk-001" },
    { chunk_id: "chunk-002" },
  ];
  const searchIndex = {
    topic_ids: { 7: ["chunk-002"] },
    topic_tokens: {},
    party_tokens: {},
    methods: {},
    stances: {},
  };
  const state = { mode: "person", q: "", person: "", method: "all", stance: "all", topic: "Vivienda social", party: "", sort: "person", limit: 180 };

  assert.deepEqual(
    helpers.candidatePersonTrajectoryChunkIds({ state, chunks, personIndex: [], searchIndex, resolvedTopicId: 7 }),
    ["chunk-002"],
  );
});

test("missing selective search index tokens do not falsely narrow candidate chunks", async () => {
  const helpers = await loadHelpers();
  const chunks = [{ chunk_id: "chunk-001" }, { chunk_id: "chunk-002" }];
  const searchIndex = {
    topic_tokens: {},
    party_tokens: { pp: ["chunk-002"] },
    methods: {},
    stances: {},
  };
  const state = { mode: "person", q: "", person: "", method: "all", stance: "all", topic: "vivienda", party: "", sort: "person", limit: 180 };

  assert.deepEqual(
    helpers.candidatePersonTrajectoryChunkIds({ state, chunks, personIndex: [], searchIndex }),
    ["chunk-001", "chunk-002"],
  );
});

test("missing exact topic id search index does not falsely narrow candidate chunks", async () => {
  const helpers = await loadHelpers();
  const chunks = [{ chunk_id: "chunk-001" }, { chunk_id: "chunk-002" }];
  const searchIndex = {
    topic_ids: {},
    topic_tokens: {},
    party_tokens: {},
    methods: {},
    stances: {},
  };
  const state = { mode: "person", q: "", person: "", method: "all", stance: "all", topic: "Vivienda social", party: "", sort: "person", limit: 180 };

  assert.deepEqual(
    helpers.candidatePersonTrajectoryChunkIds({ state, chunks, personIndex: [], searchIndex, resolvedTopicId: 7 }),
    ["chunk-001", "chunk-002"],
  );
});

test("missing chunk metadata keeps backward-compatible full scan behavior", async () => {
  const helpers = await loadHelpers();
  const chunks = [{ chunk_id: "chunk-001" }, { chunk_id: "chunk-002" }];
  const state = { mode: "person", q: "", person: "", method: "all", stance: "all", topic: "vivienda", party: "", sort: "confidence_desc", limit: 180 };

  assert.deepEqual(
    helpers.candidatePersonTrajectoryChunkIds({ state, chunks }),
    ["chunk-001", "chunk-002"],
  );
});

test("text query can narrow candidate chunks when person tokens exist", async () => {
  const helpers = await loadHelpers();
  const chunks = [
    {
      chunk_id: "chunk-001",
      topic_tokens: ["vivienda"],
      party_tokens: ["psoe"],
      methods: ["combined"],
      stances: ["support"],
    },
    {
      chunk_id: "chunk-002",
      topic_tokens: ["seguridad"],
      party_tokens: ["pp"],
      methods: ["declared"],
      stances: ["oppose"],
    },
  ];
  const personIndex = [
    { full_name: "Ada Santana", canonical_key: "ada-santana", trajectory_chunk: "chunk-001" },
    { full_name: "Bruno Segura", canonical_key: "bruno-segura", trajectory_chunk: "chunk-002" },
  ];
  const state = { mode: "person", q: "ada sant", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };

  assert.deepEqual(
    helpers.candidatePersonTrajectoryChunkIds({ state, chunks, personIndex }),
    ["chunk-001"],
  );
});

test("text query still narrows by person index when static search index is loaded", async () => {
  const helpers = await loadHelpers();
  const chunks = [
    { chunk_id: "chunk-001" },
    { chunk_id: "chunk-002" },
  ];
  const searchIndex = {
    topic_tokens: {},
    party_tokens: { psoe: ["chunk-001"] },
    methods: {},
    stances: {},
  };
  const personIndex = [
    { full_name: "Ada Santana", canonical_key: "ada-santana", trajectory_chunk: "chunk-001" },
    { full_name: "Bruno Segura", canonical_key: "bruno-segura", trajectory_chunk: "chunk-002" },
  ];
  const state = { mode: "person", q: "ada sant", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };

  assert.deepEqual(
    helpers.candidatePersonTrajectoryChunkIds({ state, chunks, personIndex, searchIndex }),
    ["chunk-001"],
  );
});

test("text query can narrow candidate chunks via static search index", async () => {
  const helpers = await loadHelpers();
  const chunks = [
    { chunk_id: "chunk-001" },
    { chunk_id: "chunk-002" },
  ];
  const searchIndex = {
    topic_tokens: { vivienda: ["chunk-001"] },
    party_tokens: { psoe: ["chunk-001"] },
    methods: {},
    stances: {},
  };
  const state = { mode: "person", q: "vivienda psoe", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };

  assert.deepEqual(
    helpers.candidatePersonTrajectoryChunkIds({ state, chunks, personIndex: [], searchIndex }),
    ["chunk-001"],
  );
});

test("date-like text query does not prefilter chunks", async () => {
  const helpers = await loadHelpers();
  const chunks = [
    { chunk_id: "chunk-001" },
    { chunk_id: "chunk-002" },
  ];
  const personIndex = [
    { full_name: "Ada Santana", canonical_key: "ada-santana", trajectory_chunk: "chunk-001" },
    { full_name: "Bruno Segura", canonical_key: "bruno-segura", trajectory_chunk: "chunk-002" },
  ];
  const state = { mode: "person", q: "2026-02-12", person: "", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };

  assert.deepEqual(
    helpers.candidatePersonTrajectoryChunkIds({ state, chunks, personIndex }),
    ["chunk-001", "chunk-002"],
  );
});

test("exhaustive scan asks for all remaining chunks", async () => {
  const helpers = await loadHelpers();
  const chunks = [{ chunk_id: "chunk-001" }, { chunk_id: "chunk-002" }, { chunk_id: "chunk-003" }];
  const state = { mode: "person", q: "ada", person: "", method: "all", stance: "all", topic: "", party: "", sort: "confidence_desc", limit: 180 };

  assert.deepEqual(
    helpers.nextPersonTrajectoryChunkIds({
      state,
      chunks,
      personIndex: [],
      loadedChunks: { "chunk-001": true },
      currentRowsCount: 20,
      limit: 180,
    }),
    ["chunk-002", "chunk-003"],
  );
});

test("person filter narrows candidate chunks using the person index", async () => {
  const helpers = await loadHelpers();
  const chunks = [
    { chunk_id: "chunk-001" },
    { chunk_id: "chunk-002" },
  ];
  const personIndex = [
    { full_name: "Ada Santana", canonical_key: "ada-santana", trajectory_chunk: "chunk-001" },
    { full_name: "Bruno Segura", canonical_key: "bruno-segura", trajectory_chunk: "chunk-002" },
  ];
  const state = { mode: "person", q: "", person: "bruno segu", method: "all", stance: "all", topic: "", party: "", sort: "person", limit: 180 };

  assert.equal(helpers.personTrajectoryHasActiveFilters(state), true);
  assert.deepEqual(
    helpers.candidatePersonTrajectoryChunkIds({ state, chunks, personIndex }),
    ["chunk-002"],
  );
});

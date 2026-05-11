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
    "topicPreviewSelections.mjs",
  );
  return import(pathToFileURL(filePath).href);
}

test("buildTopicPreviewSelections resolves unique published topics", async () => {
  const helpers = await loadHelpers();
  const topicsById = new Map([
    [1, { label: "Movilidad sostenible", key: "movilidad-sostenible" }],
    [2, { label: "Vivienda social", key: "vivienda-social" }],
  ]);

  assert.deepEqual(
    helpers.buildTopicPreviewSelections({ topicIds: [2, 1, 2, 0], topicsById }),
    [
      { topicId: 2, label: "Vivienda social", key: "vivienda-social" },
      { topicId: 1, label: "Movilidad sostenible", key: "movilidad-sostenible" },
    ],
  );
});

test("buildTopicDiscoverySelections returns ordered thematic matches for broad queries", async () => {
  const helpers = await loadHelpers();
  const topics = [
    { topicId: 1, label: "Ley estatal de vivienda", key: "vivienda" },
    { topicId: 2, label: "Plan de vivienda rural", key: "vivienda-rural" },
    { topicId: 3, label: "Movilidad sostenible", key: "movilidad-sostenible" },
  ];

  assert.deepEqual(
    helpers.buildTopicDiscoverySelections({ topics, rawValue: "vivienda", limit: 3 }),
    [
      { topicId: 1, label: "Ley estatal de vivienda", key: "vivienda" },
      { topicId: 2, label: "Plan de vivienda rural", key: "vivienda-rural" },
    ],
  );
});

test("buildTopicDiscoverySelections ignores too-short queries", async () => {
  const helpers = await loadHelpers();
  const topics = [
    { topicId: 1, label: "Ley estatal de vivienda", key: "vivienda" },
  ];

  assert.deepEqual(
    helpers.buildTopicDiscoverySelections({ topics, rawValue: "le", limit: 5 }),
    [],
  );
});

test("buildConcernEntries counts topics matched by concern keywords", async () => {
  const helpers = await loadHelpers();
  const topics = [
    { topicId: 1, label: "Ley estatal de vivienda", key: "vivienda", evidenceCountTotal: 50 },
    { topicId: 2, label: "Plan nacional de salud pública", key: "salud-publica", evidenceCountTotal: 30 },
    { topicId: 3, label: "Reforma ferroviaria", key: "ferrocarril", evidenceCountTotal: 20 },
  ];
  const concerns = [
    { id: "vivienda", label: "Vivienda", description: "desc", keywords: ["vivienda", "alquiler"] },
    { id: "sanidad", label: "Sanidad", description: "desc", keywords: ["salud", "hospital"] },
  ];

  assert.deepEqual(
    helpers.buildConcernEntries({ topics, concerns }),
    [
      {
        id: "sanidad",
        label: "Sanidad",
        description: "desc",
        keywords: ["salud", "hospital"],
        topicIds: [2],
        topicCount: 1,
      },
      {
        id: "vivienda",
        label: "Vivienda",
        description: "desc",
        keywords: ["vivienda", "alquiler"],
        topicIds: [1],
        topicCount: 1,
      },
    ],
  );
});

test("buildConcernTopicSelections ranks concern matches by score and evidence", async () => {
  const helpers = await loadHelpers();
  const topics = [
    { topicId: 1, label: "Ley estatal de vivienda y alquiler", key: "vivienda", evidenceCountTotal: 40, pointCount: 10 },
    { topicId: 2, label: "Plan de vivienda rural", key: "vivienda-rural", evidenceCountTotal: 90, pointCount: 8 },
    { topicId: 3, label: "Salud pública", key: "salud-publica", evidenceCountTotal: 70, pointCount: 12 },
  ];
  const concern = { id: "vivienda", label: "Vivienda", keywords: ["vivienda", "alquiler"] };

  assert.deepEqual(
    helpers.buildConcernTopicSelections({ topics, concern, limit: 3 }),
    [
      { topicId: 1, label: "Ley estatal de vivienda y alquiler", key: "vivienda" },
      { topicId: 2, label: "Plan de vivienda rural", key: "vivienda-rural" },
    ],
  );
});

test("buildConcernPackEntries preserves curated packs with unique topic coverage", async () => {
  const helpers = await loadHelpers();
  const concernEntries = [
    {
      id: "vivienda",
      label: "Vivienda",
      description: "Acceso a alquiler y estabilidad residencial.",
      topicIds: [1, 2],
      keywords: ["vivienda"],
    },
    {
      id: "sanidad",
      label: "Sanidad",
      description: "Sistema sanitario y listas de espera.",
      topicIds: [2, 3],
      keywords: ["salud"],
    },
  ];
  const packs = [
    {
      id: "servicios_publicos",
      label: "Servicios publicos",
      concern_ids: ["sanidad", "vivienda"],
      tradeoff: "Prioriza bienestar cotidiano.",
    },
  ];

  assert.deepEqual(
    helpers.buildConcernPackEntries({ concernEntries, packs }),
    [
      {
        id: "servicios_publicos",
        label: "Servicios publicos",
        tradeoff: "Prioriza bienestar cotidiano.",
        concernIds: ["sanidad", "vivienda"],
        concernLabels: ["Sanidad", "Vivienda"],
        concerns: [
          {
            id: "sanidad",
            label: "Sanidad",
            description: "Sistema sanitario y listas de espera.",
            topicCount: 0,
          },
          {
            id: "vivienda",
            label: "Vivienda",
            description: "Acceso a alquiler y estabilidad residencial.",
            topicCount: 0,
          },
        ],
        topicIds: [2, 3, 1],
        topicCount: 3,
      },
    ],
  );
});

test("buildConcernPackTopicSelections aggregates concern matches across a pack", async () => {
  const helpers = await loadHelpers();
  const topics = [
    { topicId: 1, label: "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas fiscales para asegurar el derecho a la vivienda.", key: "vivienda", evidenceCountTotal: 40, pointCount: 10 },
    { topicId: 2, label: "Moción consecuencia de interpelación urgente del Grupo Parlamentario VOX, sobre cuál es la política del Gobierno en materia de educación.", key: "educacion", evidenceCountTotal: 70, pointCount: 12 },
    { topicId: 3, label: "Reforma ferroviaria", key: "ferrocarril", evidenceCountTotal: 90, pointCount: 15 },
  ];
  const concernsById = new Map([
    ["vivienda", { id: "vivienda", label: "Vivienda", description: "Acceso a alquiler/compra y estabilidad residencial.", keywords: ["vivienda", "alquiler"] }],
    ["educacion", { id: "educacion", label: "Educacion", description: "Escuela, universidad, becas y formacion a lo largo de la vida.", keywords: ["educacion", "escuela"] }],
  ]);
  const pack = {
    id: "servicios_publicos",
    label: "Servicios publicos",
    concernIds: ["educacion", "vivienda"],
  };

  assert.deepEqual(
    helpers.buildConcernPackTopicSelections({ topics, concernsById, pack, limit: 3 }),
    [
      {
        topicId: 2,
        label: "Moción consecuencia de interpelación urgente del Grupo Parlamentario VOX, sobre cuál es la política del Gobierno en materia de educación.",
        key: "educacion",
        topicHeadline: "Política del Gobierno en materia de educación",
        topicProcedure: "Moción",
        matchedConcernIds: ["educacion"],
        matchedConcernLabels: ["Educacion"],
        matchedConcernDescriptions: [
          "Escuela, universidad, becas y formacion a lo largo de la vida.",
        ],
        editorialSummary: "Encaja por Educacion: Escuela, universidad, becas y formacion a lo largo de la vida.",
        familyKey: "politica de el gobierno en materia de educacion",
        familyTopicIds: [2],
        familyLabels: [
          "Moción consecuencia de interpelación urgente del Grupo Parlamentario VOX, sobre cuál es la política del Gobierno en materia de educación.",
        ],
        familyProcedures: ["Moción"],
        familyCount: 1,
        familyMatchMode: "exact",
      },
      {
        topicId: 1,
        label: "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas fiscales para asegurar el derecho a la vivienda.",
        key: "vivienda",
        topicHeadline: "Medidas fiscales para asegurar el derecho a la vivienda",
        topicProcedure: "PNL",
        matchedConcernIds: ["vivienda"],
        matchedConcernLabels: ["Vivienda"],
        matchedConcernDescriptions: [
          "Acceso a alquiler/compra y estabilidad residencial.",
        ],
        editorialSummary: "Encaja por Vivienda: Acceso a alquiler/compra y estabilidad residencial.",
        familyKey: "medidas fiscales para asegurar el derecho a la vivienda",
        familyTopicIds: [1],
        familyLabels: [
          "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas fiscales para asegurar el derecho a la vivienda.",
        ],
        familyProcedures: ["PNL"],
        familyCount: 1,
        familyMatchMode: "exact",
      },
    ],
  );
});

test("buildConcernPackTopicSelections collapses repeated substantive claims into one family", async () => {
  const helpers = await loadHelpers();
  const topics = [
    { topicId: 1, label: "Proyecto de Ley de Movilidad Sostenible.", key: "movilidad-sostenible", evidenceCountTotal: 60, pointCount: 10 },
    { topicId: 2, label: "Votación del dictamen del Proyecto de Ley de Movilidad Sostenible.", key: "movilidad-sostenible-votacion", evidenceCountTotal: 20, pointCount: 5 },
  ];
  const concernsById = new Map([
    ["transporte", { id: "transporte", label: "Transporte", description: "Movilidad diaria, red ferroviaria y acceso territorial.", keywords: ["movilidad", "transporte"] }],
  ]);
  const pack = {
    id: "servicios_publicos",
    label: "Servicios publicos",
    concernIds: ["transporte"],
  };

  assert.deepEqual(
    helpers.buildConcernPackTopicSelections({ topics, concernsById, pack, limit: 5 }),
    [
      {
        topicId: 1,
        label: "Proyecto de Ley de Movilidad Sostenible.",
        key: "movilidad-sostenible",
        topicHeadline: "Movilidad Sostenible",
        topicProcedure: "Proyecto de ley",
        matchedConcernIds: ["transporte"],
        matchedConcernLabels: ["Transporte"],
        matchedConcernDescriptions: [
          "Movilidad diaria, red ferroviaria y acceso territorial.",
        ],
        editorialSummary: "Encaja por Transporte: Movilidad diaria, red ferroviaria y acceso territorial.",
        familyKey: "movilidad sostenible",
        familyTopicIds: [1, 2],
        familyLabels: [
          "Proyecto de Ley de Movilidad Sostenible.",
          "Votación del dictamen del Proyecto de Ley de Movilidad Sostenible.",
        ],
        familyProcedures: ["Proyecto de ley", "Votación"],
        familyCount: 2,
        familyMatchMode: "exact",
        familyVariants: [
          {
            topicId: 1,
            label: "Proyecto de Ley de Movilidad Sostenible.",
            topicHeadline: "Movilidad Sostenible",
            topicProcedure: "Proyecto de ley",
          },
          {
            topicId: 2,
            label: "Votación del dictamen del Proyecto de Ley de Movilidad Sostenible.",
            topicHeadline: "Movilidad Sostenible",
            topicProcedure: "Votación",
          },
        ],
      },
    ],
  );
});

test("buildConcernPackTopicSelections collapses near-duplicate claims with different headlines", async () => {
  const helpers = await loadHelpers();
  const topics = [
    { topicId: 1, label: "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas fiscales para asegurar el derecho a la vivienda.", key: "vivienda-medidas", evidenceCountTotal: 60, pointCount: 10 },
    { topicId: 2, label: "Moción consecuencia de interpelación urgente del Grupo Parlamentario Popular en el Congreso, sobre la política del Gobierno para garantizar el derecho a la vivienda.", key: "vivienda-garantizar", evidenceCountTotal: 30, pointCount: 8 },
    { topicId: 3, label: "Moción consecuencia de interpelación urgente del Grupo Parlamentario Popular en el Congreso, sobre el fracaso de la política del Gobierno en materia de vivienda.", key: "vivienda-fracaso", evidenceCountTotal: 40, pointCount: 6 },
  ];
  const concernsById = new Map([
    ["vivienda", { id: "vivienda", label: "Vivienda", description: "Acceso a alquiler/compra y estabilidad residencial.", keywords: ["vivienda", "alquiler"] }],
  ]);
  const pack = {
    id: "servicios_publicos",
    label: "Servicios publicos",
    concernIds: ["vivienda"],
  };

  assert.deepEqual(
    helpers.buildConcernPackTopicSelections({ topics, concernsById, pack, limit: 5 }),
    [
      {
        topicId: 1,
        label: "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas fiscales para asegurar el derecho a la vivienda.",
        key: "vivienda-medidas",
        topicHeadline: "Medidas fiscales para asegurar el derecho a la vivienda",
        topicProcedure: "PNL",
        matchedConcernIds: ["vivienda"],
        matchedConcernLabels: ["Vivienda"],
        matchedConcernDescriptions: [
          "Acceso a alquiler/compra y estabilidad residencial.",
        ],
        editorialSummary: "Encaja por Vivienda: Acceso a alquiler/compra y estabilidad residencial.",
        familyKey: "vivienda:asegurar derecho vivienda",
        familyTopicIds: [1, 2],
        familyLabels: [
          "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas fiscales para asegurar el derecho a la vivienda.",
          "Moción consecuencia de interpelación urgente del Grupo Parlamentario Popular en el Congreso, sobre la política del Gobierno para garantizar el derecho a la vivienda.",
        ],
        familyProcedures: ["PNL", "Moción"],
        familyCount: 2,
        familyMatchMode: "near_duplicate",
        familyVariants: [
          {
            topicId: 1,
            label: "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas fiscales para asegurar el derecho a la vivienda.",
            topicHeadline: "Medidas fiscales para asegurar el derecho a la vivienda",
            topicProcedure: "PNL",
          },
          {
            topicId: 2,
            label: "Moción consecuencia de interpelación urgente del Grupo Parlamentario Popular en el Congreso, sobre la política del Gobierno para garantizar el derecho a la vivienda.",
            topicHeadline: "La política del Gobierno para garantizar el derecho a la vivienda",
            topicProcedure: "Moción",
          },
        ],
      },
      {
        topicId: 3,
        label: "Moción consecuencia de interpelación urgente del Grupo Parlamentario Popular en el Congreso, sobre el fracaso de la política del Gobierno en materia de vivienda.",
        key: "vivienda-fracaso",
        topicHeadline: "El fracaso de la política del Gobierno en materia de vivienda",
        topicProcedure: "Moción",
        matchedConcernIds: ["vivienda"],
        matchedConcernLabels: ["Vivienda"],
        matchedConcernDescriptions: [
          "Acceso a alquiler/compra y estabilidad residencial.",
        ],
        editorialSummary: "Encaja por Vivienda: Acceso a alquiler/compra y estabilidad residencial.",
        familyKey: "fracaso de la politica de el gobierno en materia de vivienda",
        familyTopicIds: [3],
        familyLabels: [
          "Moción consecuencia de interpelación urgente del Grupo Parlamentario Popular en el Congreso, sobre el fracaso de la política del Gobierno en materia de vivienda.",
        ],
        familyProcedures: ["Moción"],
        familyCount: 1,
        familyMatchMode: "exact",
      },
    ],
  );
});

test("applyTopicPreviewSelection converts q thematic preview into exact topic state", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.applyTopicPreviewSelection({
      prevState: {
        mode: "person",
        q: "movilidad sostenible",
        searchMode: "topic",
        topic: "",
      },
      selection: {
        topicId: 1,
        label: "Proyecto de Ley de Movilidad Sostenible",
        key: "movilidad-sostenible",
      },
      sourceMode: "q_search",
    }),
    {
      mode: "person",
      q: "",
      originPack: "",
      originConcern: "",
      originTopicId: 0,
      searchMode: "auto",
      topic: "Proyecto de Ley de Movilidad Sostenible",
      topicId: 1,
    },
  );
});

test("applyTopicPreviewSelection clears concern when exact topic comes from concern discovery", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.applyTopicPreviewSelection({
      prevState: {
        mode: "person",
        concern: "vivienda",
        q: "",
        searchMode: "auto",
        topic: "",
      },
      selection: {
        topicId: 1,
        label: "Ley estatal de vivienda",
        key: "vivienda",
      },
      sourceMode: "concern_discovery",
    }),
    {
      mode: "person",
      pack: "",
      concern: "",
      originPack: "",
      originConcern: "vivienda",
      originTopicId: 1,
      q: "",
      searchMode: "auto",
      topic: "Ley estatal de vivienda",
      topicId: 1,
    },
  );
});

test("applyTopicPreviewSelection clears pack when exact topic comes from pack discovery", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.applyTopicPreviewSelection({
      prevState: {
        mode: "person",
        pack: "servicios_publicos",
        concern: "",
        q: "",
        searchMode: "auto",
        topic: "",
      },
      selection: {
        topicId: 1,
        label: "Ley estatal de vivienda",
        key: "vivienda",
      },
      sourceMode: "pack_discovery",
    }),
    {
      mode: "person",
      pack: "",
      concern: "",
      originPack: "servicios_publicos",
      originConcern: "",
      originTopicId: 1,
      q: "",
      searchMode: "auto",
      topic: "Ley estatal de vivienda",
      topicId: 1,
    },
  );
});

test("applyTopicPreviewSelection can pin an exact topic from a grouped pack variant", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.applyTopicPreviewSelection({
      prevState: {
        mode: "person",
        pack: "servicios_publicos",
        concern: "",
        q: "",
        searchMode: "auto",
        topic: "",
      },
      selection: {
        topicId: 327,
        label: "Moción consecuencia de interpelación urgente del Grupo Parlamentario Mixto (Sra. Belarra Urteaga), sobre la política del Gobierno para garantizar el derecho a la vivienda.",
        topicHeadline: "La política del Gobierno para garantizar el derecho a la vivienda",
        topicProcedure: "Mocion",
      },
      sourceMode: "pack_discovery",
    }),
    {
      mode: "person",
      pack: "",
      concern: "",
      originPack: "servicios_publicos",
      originConcern: "",
      originTopicId: 327,
      q: "",
      searchMode: "auto",
      topic: "Moción consecuencia de interpelación urgente del Grupo Parlamentario Mixto (Sra. Belarra Urteaga), sobre la política del Gobierno para garantizar el derecho a la vivienda.",
      topicId: 327,
    },
  );
});

test("applyTopicPreviewSelection also cleans q when broad topic discovery came from Buscar", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.applyTopicPreviewSelection({
      prevState: {
        mode: "person",
        q: "ley",
        searchMode: "topic",
        topic: "",
      },
      selection: {
        topicId: 1,
        label: "Ley estatal de vivienda",
        key: "vivienda",
      },
      sourceMode: "q_discovery",
    }),
    {
      mode: "person",
      q: "",
      pack: "",
      concern: "",
      originPack: "",
      originConcern: "",
      originTopicId: 0,
      searchMode: "auto",
      topic: "Ley estatal de vivienda",
      topicId: 1,
    },
  );
});

test("applyTopicPreviewSelection keeps generic search state when preview came from Tema", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.applyTopicPreviewSelection({
      prevState: {
        mode: "person",
        q: "movilidad",
        searchMode: "auto",
        topic: "movilidad",
      },
      selection: {
        topicId: 1,
        label: "Proyecto de Ley de Movilidad Sostenible",
        key: "movilidad-sostenible",
      },
      sourceMode: "topic_filter",
    }),
    {
      mode: "person",
      q: "movilidad",
      originPack: "",
      originConcern: "",
      originTopicId: 0,
      searchMode: "auto",
      topic: "Proyecto de Ley de Movilidad Sostenible",
      topicId: 1,
    },
  );
});

test("resolveTopicDiscoveryOriginHighlight marks grouped family and exact variant", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.resolveTopicDiscoveryOriginHighlight({
      topic: {
        topicId: 285,
        familyTopicIds: [285, 250, 327],
      },
      originTopicId: 327,
    }),
    {
      isOriginFamily: true,
      isOriginVariant: false,
      representativeTopicId: 285,
      variantTopicIds: [285, 250, 327],
    },
  );

  assert.deepEqual(
    helpers.resolveTopicDiscoveryOriginHighlight({
      topic: {
        topicId: 327,
        familyTopicIds: [285, 250, 327],
      },
      originTopicId: 327,
    }),
    {
      isOriginFamily: true,
      isOriginVariant: true,
      representativeTopicId: 327,
      variantTopicIds: [285, 250, 327],
    },
  );
});

test("resolveTopicDiscoveryOriginTargetTopicId returns the representative family card to refocus", async () => {
  const helpers = await loadHelpers();

  assert.equal(
    helpers.resolveTopicDiscoveryOriginTargetTopicId({
      topics: [
        { topicId: 1, familyTopicIds: [1] },
        { topicId: 285, familyTopicIds: [285, 250, 327] },
        { topicId: 19, familyTopicIds: [19] },
      ],
      originTopicId: 327,
    }),
    285,
  );

  assert.equal(
    helpers.resolveTopicDiscoveryOriginTargetTopicId({
      topics: [
        { topicId: 1, familyTopicIds: [1] },
        { topicId: 19, familyTopicIds: [19] },
      ],
      originTopicId: 327,
    }),
    0,
  );
});

test("resolveTopicDiscoveryOriginResumeNotice returns family and exact variant context", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.resolveTopicDiscoveryOriginResumeNotice({
      topics: [
        {
          topicId: 285,
          label: "Proposición no de Ley sobre asegurar el derecho a la vivienda.",
          topicHeadline: "Asegurar el derecho a la vivienda",
          topicProcedure: "PNL",
          familyCount: 3,
          familyMatchMode: "near_duplicate",
          familyProcedures: ["PNL", "Mocion"],
          familyTopicIds: [285, 250, 327],
          familyVariants: [
            {
              topicId: 285,
              label: "Proposición no de Ley sobre asegurar el derecho a la vivienda.",
              topicHeadline: "Asegurar el derecho a la vivienda",
              topicProcedure: "PNL",
            },
            {
              topicId: 327,
              label: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.",
              topicHeadline: "Garantizar el derecho a la vivienda",
              topicProcedure: "Mocion",
            },
          ],
        },
      ],
      originTopicId: 327,
    }),
    {
      originTopicId: 327,
      representativeTopicId: 285,
      familyHeadline: "Asegurar el derecho a la vivienda",
      familyLabel: "Proposición no de Ley sobre asegurar el derecho a la vivienda.",
      familyCount: 3,
      familyMatchMode: "near_duplicate",
      familyProcedures: ["PNL", "Mocion"],
      variantTopicId: 327,
      variantHeadline: "Garantizar el derecho a la vivienda",
      variantLabel: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.",
      variantProcedure: "Mocion",
      isRepresentativeVariant: false,
    },
  );
});

test("resolveTopicDiscoveryOriginVariantSelection returns the exact resumed variant", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.resolveTopicDiscoveryOriginVariantSelection({
      topics: [
        {
          topicId: 285,
          label: "Proposición no de Ley sobre asegurar el derecho a la vivienda.",
          key: "vivienda-pnl",
          topicHeadline: "Asegurar el derecho a la vivienda",
          topicProcedure: "PNL",
          familyTopicIds: [285, 250, 327],
          familyVariants: [
            {
              topicId: 285,
              label: "Proposición no de Ley sobre asegurar el derecho a la vivienda.",
              key: "vivienda-pnl",
              topicHeadline: "Asegurar el derecho a la vivienda",
              topicProcedure: "PNL",
            },
            {
              topicId: 327,
              label: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.",
              key: "vivienda-mocion",
              topicHeadline: "Garantizar el derecho a la vivienda",
              topicProcedure: "Mocion",
            },
          ],
        },
      ],
      originTopicId: 327,
    }),
    {
      topicId: 327,
      label: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.",
      key: "vivienda-mocion",
      topicHeadline: "Garantizar el derecho a la vivienda",
      topicProcedure: "Mocion",
    },
  );
});

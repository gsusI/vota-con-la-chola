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
    "detailPanelModel.mjs",
  );
  return import(pathToFileURL(filePath).href);
}

test("buildPoliticalPositionsDetailPanelSummary prioritizes the compact route context", async () => {
  const helpers = await loadHelpers();

  assert.equal(
    helpers.buildPoliticalPositionsDetailPanelSummary({
      selectedPoint: { scope: "person", personId: 91 },
      resolvedTopicFilter: { topicId: 327, label: "Mocion de vivienda" },
      detailContinuityBreadcrumb: { mode: "exact" },
    }),
    "La ruta superior resume el contexto editorial. Debajo tienes postura agregada, revisión y detalle reproducible.",
  );
});

test("buildPoliticalPositionsDetailPanelSummary keeps exact topic guidance when no row is selected", async () => {
  const helpers = await loadHelpers();

  assert.equal(
    helpers.buildPoliticalPositionsDetailPanelSummary({
      selectedPoint: null,
      resolvedTopicFilter: { topicId: 327, label: "Mocion de vivienda" },
      detailContinuityBreadcrumb: null,
    }),
    "Tema exacto activo. Selecciona una fila para abrir evidencia puntual, revisión y detalle reproducible.",
  );
});

test("buildPoliticalPositionsDetailOverview returns metrics without repeating route labels", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsDetailOverview({
      scope: "person",
      stance: "support",
      method: "votes",
      asOf: "2026-02-12",
      score: 0.8534,
      confidence: 0.72,
      evidenceCount: 14,
      lastEvidenceDate: "2026-02-10",
      windowDays: 30,
      personName: "Ainhoa Molina",
      topicLabel: "Mocion de vivienda",
    }),
    [
    { label: "Postura", value: "A favor", kind: "stance" },
    { label: "Método", value: "Votos" },
      { label: "Fecha", value: "2026-02-12" },
      { label: "Puntuación", value: "0.85" },
      { label: "Confianza", value: "72.0%" },
      { label: "Evidencias", value: "14" },
      { label: "Última evidencia", value: "2026-02-10" },
      { label: "Ventana", value: "30 días" },
    ],
  );
});

test("buildPoliticalPositionsDetailDrilldownLinks builds person explorer links", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsDetailDrilldownLinks({
      basePath: "/vota-con-la-chola",
      selectedPoint: {
        scope: "person",
        personId: 91,
        topicId: 327,
      },
      topicSetId: 4,
    }),
    [
      {
        label: "Rastro exacto: persona y tema",
        href: "/vota-con-la-chola/explorer/?t=topic_evidence&wc=person_id&wv=91&wc=topic_id&wv=327&wc=topic_set_id&wv=4",
      },
      {
        label: "Votos base del mismo punto",
        hint: "misma persona y tema, solo votos base",
        href: "/vota-con-la-chola/explorer/?t=parl_vote_member_votes&wc=person_id&wv=91&wc=topic_id&wv=327",
      },
    ],
  );
});

test("buildPoliticalPositionsDetailDrilldownLinks builds party explorer links", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsDetailDrilldownLinks({
      basePath: "",
      selectedPoint: {
        scope: "party",
        partyId: 14,
        topicId: 327,
      },
      topicSetId: 1,
    }),
    [
      {
        label: "Rastro exacto: grupo y tema",
        href: "/explorer/?t=topic_positions&wc=party_id&wv=14&wc=topic_id&wv=327&wc=topic_set_id&wv=1",
      },
      {
        label: "Otras posturas del grupo",
        hint: "mismo grupo, otros temas",
        href: "/explorer/?t=topic_positions&wc=party_id&wv=14&wc=topic_set_id&wv=1",
      },
    ],
  );
});

test("buildPoliticalPositionsEvidenceTableHeader promotes review and drill-down next to the audit rows", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsEvidenceTableHeader({
      selectedPoint: {
        scope: "person",
        evidenceCount: 6,
      },
      visibleSampleCount: 6,
      availableSampleCount: 6,
      reviewLabel: "Pendiente 2 · Aprobada 9 · Ignorada 1",
      drilldownLinks: [
        {
          label: "Rastro exacto: persona y tema",
          href: "/explorer/?t=topic_evidence",
        },
      ],
    }),
    {
      title: "Muestras y auditoría",
      subtitle: "Detalle reproducible para la persona y el tema activos.",
      chips: [
        { label: "Revisión", value: "Pendiente 2 · Aprobada 9 · Ignorada 1" },
        { label: "Muestras puntuales", value: "6" },
        { label: "Evidencias agregadas", value: "6" },
      ],
      links: [
        {
          label: "Rastro exacto: persona y tema",
          href: "/explorer/?t=topic_evidence",
          role: "primary",
          hint: "",
        },
      ],
    },
  );
});

test("buildPoliticalPositionsEvidenceTableHeader makes aggregate gap explicit even without visible truncation", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsEvidenceTableHeader({
      selectedPoint: {
        scope: "person",
        evidenceCount: 14,
      },
      visibleSampleCount: 6,
      availableSampleCount: 6,
      reviewLabel: "Pendiente 2 · Aprobada 9 · Ignorada 1",
      drilldownLinks: [
        {
          label: "Rastro exacto: persona y tema",
          href: "/explorer/?t=topic_evidence",
        },
        {
          label: "Votos base del mismo punto",
          hint: "misma persona y tema, solo votos base",
          href: "/explorer/?t=parl_vote_member_votes",
        },
      ],
    }),
    {
      title: "Muestras y auditoría",
      subtitle: "Hay 6 muestras publicadas; la puntuación usa 14 evidencias. Abre el rastro exacto de la persona y el tema activos.",
      chips: [
        { label: "Revisión", value: "Pendiente 2 · Aprobada 9 · Ignorada 1" },
        { label: "Muestras puntuales", value: "6" },
        { label: "Evidencias agregadas", value: "14" },
      ],
      links: [
        {
          label: "Abrir rastro exacto de la persona y el tema",
          href: "/explorer/?t=topic_evidence",
          role: "primary",
          hint: "misma persona y tema, evidencia agregada no listada",
        },
        {
          label: "Votos base del mismo punto",
          hint: "misma persona y tema, solo votos base",
          href: "/explorer/?t=parl_vote_member_votes",
          role: "secondary",
        },
      ],
    },
  );
});

test("buildPoliticalPositionsEvidenceTableHeader makes truncation explicit and points to the full trace", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsEvidenceTableHeader({
      selectedPoint: {
        scope: "person",
        evidenceCount: 14,
      },
      visibleSampleCount: 6,
      availableSampleCount: 12,
      reviewLabel: "Pendiente 2 · Aprobada 9 · Ignorada 1",
      drilldownLinks: [
        {
          label: "Rastro exacto: persona y tema",
          href: "/explorer/?t=topic_evidence",
        },
        {
          label: "Votos base del mismo punto",
          hint: "misma persona y tema, solo votos base",
          href: "/explorer/?t=parl_vote_member_votes",
        },
      ],
    }),
    {
      title: "Muestras y auditoría",
      subtitle: "Ves 6/12 muestras; la puntuación usa 14 evidencias. Abre el rastro exacto de la persona y el tema activos.",
      chips: [
        { label: "Revisión", value: "Pendiente 2 · Aprobada 9 · Ignorada 1" },
        { label: "Mostrando", value: "6 de 12" },
        { label: "Evidencias agregadas", value: "14" },
      ],
      links: [
        {
          label: "Abrir rastro exacto de la persona y el tema",
          href: "/explorer/?t=topic_evidence",
          role: "primary",
          hint: "misma persona y tema, tabla completa + evidencia extra",
        },
        {
          label: "Votos base del mismo punto",
          hint: "misma persona y tema, solo votos base",
          href: "/explorer/?t=parl_vote_member_votes",
          role: "secondary",
        },
      ],
    },
  );
});

test("buildPoliticalPositionsEvidenceTableHeader distinguishes full published samples from aggregate-only gaps", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsEvidenceTableHeader({
      selectedPoint: {
        scope: "person",
        evidenceCount: 12,
      },
      visibleSampleCount: 6,
      availableSampleCount: 12,
      reviewLabel: "Pendiente 2 · Aprobada 9 · Ignorada 1",
      drilldownLinks: [
        {
          label: "Rastro exacto: persona y tema",
          href: "/explorer/?t=topic_evidence",
        },
        {
          label: "Votos base del mismo punto",
          hint: "misma persona y tema, solo votos base",
          href: "/explorer/?t=parl_vote_member_votes",
        },
      ],
    }),
    {
      title: "Muestras y auditoría",
      subtitle: "Ves 6/12 muestras. Abre el rastro exacto de la persona y el tema activos.",
      chips: [
        { label: "Revisión", value: "Pendiente 2 · Aprobada 9 · Ignorada 1" },
        { label: "Mostrando", value: "6 de 12" },
        { label: "Evidencias agregadas", value: "12" },
      ],
      links: [
        {
          label: "Abrir rastro exacto de la persona y el tema",
          href: "/explorer/?t=topic_evidence",
          role: "primary",
          hint: "misma persona y tema, tabla completa",
        },
        {
          label: "Votos base del mismo punto",
          hint: "misma persona y tema, solo votos base",
          href: "/explorer/?t=parl_vote_member_votes",
          role: "secondary",
        },
      ],
    },
  );
});

test("buildPoliticalPositionsEvidenceTableHeader keeps audit actions available even without listed samples", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsEvidenceTableHeader({
      selectedPoint: {
        scope: "party",
        evidenceCount: 0,
      },
      visibleSampleCount: 0,
      availableSampleCount: 0,
      reviewLabel: "",
      drilldownLinks: [
        {
          label: "Otras posturas del grupo",
          href: "/explorer/?t=topic_positions",
        },
      ],
    }),
    {
      title: "Muestras y auditoría",
      subtitle: "No hay muestras puntuales listadas; usa el explorador para abrir el rastro completo del grupo.",
      chips: [
        { label: "Revisión", value: "Sin revisión registrada" },
        { label: "Muestras puntuales", value: "0" },
        { label: "Evidencias agregadas", value: "0" },
      ],
      links: [
        {
          label: "Otras posturas del grupo",
          href: "/explorer/?t=topic_positions",
          role: "primary",
          hint: "",
        },
      ],
    },
  );
});

test("buildPoliticalPositionsEvidenceTableHeader explains aggregate-only evidence when no samples are published", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsEvidenceTableHeader({
      selectedPoint: {
        scope: "party",
        evidenceCount: 8,
      },
      visibleSampleCount: 0,
      availableSampleCount: 0,
      reviewLabel: "",
      drilldownLinks: [
        {
          label: "Rastro exacto: grupo y tema",
          href: "/explorer/?t=topic_positions&wc=party_id&wv=14&wc=topic_id&wv=327",
        },
        {
          label: "Otras posturas del grupo",
          hint: "mismo grupo, otros temas",
          href: "/explorer/?t=topic_positions&wc=party_id&wv=14",
        },
      ],
    }),
    {
      title: "Muestras y auditoría",
      subtitle: "No hay muestra puntual publicada; la puntuación usa 8 evidencias. Abre el rastro exacto del grupo y el tema activos.",
      chips: [
        { label: "Revisión", value: "Sin revisión registrada" },
        { label: "Muestras puntuales", value: "0" },
        { label: "Evidencias agregadas", value: "8" },
      ],
      links: [
        {
          label: "Abrir rastro exacto del grupo y el tema",
          href: "/explorer/?t=topic_positions&wc=party_id&wv=14&wc=topic_id&wv=327",
          role: "primary",
          hint: "mismo grupo y tema, postura sin muestra puntual",
        },
        {
          label: "Otras posturas del grupo",
          hint: "mismo grupo, otros temas",
          href: "/explorer/?t=topic_positions&wc=party_id&wv=14",
          role: "secondary",
        },
      ],
    },
  );
});

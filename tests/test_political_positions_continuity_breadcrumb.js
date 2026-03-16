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
    "continuityBreadcrumb.mjs",
  );
  return import(pathToFileURL(filePath).href);
}

test("buildPoliticalPositionsContinuityBreadcrumb returns compact exact-topic route", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsContinuityBreadcrumb({
      exactTopicOriginContext: { kind: "pack", label: "Servicios publicos" },
      exactTopicLabel: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.",
      resolvedTopicId: 327,
      discoveryOriginContext: null,
      originDiscoveryResumeNotice: null,
      originDiscoveryVariantSelection: null,
    }),
    {
      mode: "exact",
      statusLabel: "Ruta editorial activa",
      items: [
        { kind: "origin", originKind: "pack", label: "Servicios publicos" },
        { kind: "exact", label: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.", topicId: 327 },
      ],
      primaryAction: {
        kind: "restore_discovery",
        label: "Volver al pack",
      },
      dismissible: false,
      meta: null,
    },
  );
});

test("buildPoliticalPositionsContinuityBreadcrumb returns compact resumed discovery route", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsContinuityBreadcrumb({
      exactTopicOriginContext: null,
      exactTopicLabel: "",
      resolvedTopicId: 0,
      discoveryOriginContext: { kind: "pack", label: "Servicios publicos" },
      originDiscoveryResumeNotice: {
        familyHeadline: "Asegurar el derecho a la vivienda",
        variantLabel: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.",
        variantTopicId: 327,
        familyCount: 3,
        familyMatchMode: "near_duplicate",
      },
      originDiscoveryVariantSelection: {
        topicId: 327,
        label: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.",
      },
    }),
    {
      mode: "discovery",
      statusLabel: "Ruta editorial retomada",
      items: [
        { kind: "origin", originKind: "pack", label: "Servicios publicos" },
        { kind: "family", label: "Asegurar el derecho a la vivienda" },
        { kind: "exact", label: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.", topicId: 327 },
      ],
      primaryAction: {
        kind: "open_exact",
        label: "Volver al tema exacto",
      },
      dismissible: true,
      meta: {
        familyCount: 3,
        familyMatchMode: "near_duplicate",
      },
    },
  );
});

test("buildPoliticalPositionsDetailBreadcrumb appends active person to the compact route", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsDetailBreadcrumb({
      continuityBreadcrumb: {
        mode: "exact",
        statusLabel: "Ruta editorial activa",
        items: [
          { kind: "origin", originKind: "pack", label: "Servicios publicos" },
          { kind: "exact", label: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.", topicId: 327 },
        ],
        primaryAction: {
          kind: "restore_discovery",
          label: "Volver al pack",
        },
        dismissible: false,
        meta: null,
      },
      selectedPoint: {
        scope: "person",
        personId: 91,
        personName: "Ainhoa Molina",
      },
      selectedPersonCard: {
        person_id: 91,
        full_name: "Ainhoa Molina Serrano",
      },
      selectedPartyCard: null,
    }),
    {
      mode: "exact",
      statusLabel: "Detalle activo",
      items: [
        { kind: "origin", originKind: "pack", label: "Servicios publicos" },
        { kind: "exact", label: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.", topicId: 327 },
        { kind: "entity", entityKind: "person", label: "Ainhoa Molina Serrano", entityId: 91 },
      ],
      primaryAction: {
        kind: "restore_discovery",
        label: "Volver al pack",
      },
      dismissible: false,
      meta: null,
    },
  );
});

test("buildPoliticalPositionsDetailBreadcrumb appends active party to the compact route", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.buildPoliticalPositionsDetailBreadcrumb({
      continuityBreadcrumb: {
        mode: "discovery",
        statusLabel: "Ruta editorial retomada",
        items: [
          { kind: "origin", originKind: "pack", label: "Servicios publicos" },
          { kind: "family", label: "Asegurar el derecho a la vivienda" },
          { kind: "exact", label: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.", topicId: 327 },
        ],
        primaryAction: {
          kind: "open_exact",
          label: "Volver al tema exacto",
        },
        dismissible: true,
        meta: {
          familyCount: 3,
          familyMatchMode: "near_duplicate",
        },
      },
      selectedPoint: {
        scope: "party",
        partyId: 14,
        partyLabel: "EH Bildu",
      },
      selectedPersonCard: null,
      selectedPartyCard: {
        party_id: 14,
        name: "EH Bildu",
      },
    }),
    {
      mode: "discovery",
      statusLabel: "Detalle activo",
      items: [
        { kind: "origin", originKind: "pack", label: "Servicios publicos" },
        { kind: "family", label: "Asegurar el derecho a la vivienda" },
        { kind: "exact", label: "Moción consecuencia de interpelación urgente sobre garantizar el derecho a la vivienda.", topicId: 327 },
        { kind: "entity", entityKind: "party", label: "EH Bildu", entityId: 14 },
      ],
      primaryAction: {
        kind: "open_exact",
        label: "Volver al tema exacto",
      },
      dismissible: false,
      meta: {
        familyCount: 3,
        familyMatchMode: "near_duplicate",
      },
    },
  );
});

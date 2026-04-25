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
    "parliamentary-accountability",
    "outcomeMeasures.mjs",
  );
  return import(pathToFileURL(filePath).href);
}

test("normalizeOutcomeMeasurePreviews returns sorted compact previews", async () => {
  const helpers = await loadHelpers();

  const previews = helpers.normalizeOutcomeMeasurePreviews(
    {
      initiative_measures: [
        {
          rank: 3,
          title: "Tercera medida",
          summary: "Resumen breve",
          support_side: "mixed",
          status: "pending",
        },
        {
          rank: 1,
          title: "Primera medida con un titulo bastante largo para comprobar el recorte en la vista publica",
          summary:
            "Este resumen tambien es bastante largo y deberia compactarse en la salida para no cargar en exceso la tabla de accountability con demasiado texto repetido.",
          policy_area: "movilidad sostenible",
          support_side: "YES",
          status: "approved",
        },
      ],
    },
    { limit: 2 },
  );

  assert.equal(previews.length, 2);
  assert.deepEqual(previews[0], {
    rank: 1,
    title: "Primera medida con un titulo bastante largo para comprobar el recorte en la vista publica",
    summary:
      "Este resumen tambien es bastante largo y deberia compactarse en la salida para no cargar en exceso la tabla de accountability con demasiado texto repetido.",
    policyArea: "movilidad sostenible",
    supportSide: "yes",
    status: "approved",
  });
  assert.deepEqual(previews[1], {
    rank: 3,
    title: "Tercera medida",
    summary: "Resumen breve",
    policyArea: "",
    supportSide: "mixed",
    status: "pending",
  });
});

test("buildOutcomeInitiativeSearchText includes initiative and measure text", async () => {
  const helpers = await loadHelpers();

  const searchText = helpers.buildOutcomeInitiativeSearchText({
    initiative_id: "congreso:ley:12:2025",
    initiative_expediente: "Ley 12/2025",
    initiative_title: "Servicio de atencion a la clientela",
    initiative_measures: [
      {
        rank: 1,
        title: "Varios canales para reclamar",
        summary: "La empresa tiene que recibir reclamaciones por el mismo canal en el que se contrato.",
        policy_area: "consumo",
        support_side: "yes",
        status: "approved",
      },
    ],
  });

  assert.match(searchText, /Ley 12\/2025/);
  assert.match(searchText, /Varios canales para reclamar/);
  assert.match(searchText, /mismo canal en el que se contrato/);
  assert.match(searchText, /consumo/);
  assert.match(searchText, /approved/);
});

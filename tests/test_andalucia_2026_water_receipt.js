const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.join(__dirname, "..");
const pagePath = path.join(
  root,
  "ui",
  "gh-pages-next",
  "app",
  "elecciones",
  "andalucia-2026",
  "page.js",
);
const dataPath = path.join(
  root,
  "ui",
  "gh-pages-next",
  "public",
  "elecciones",
  "andalucia-2026",
  "data",
  "water-receipt.json",
);

test("water receipt artifact is compact, current, and conservative", () => {
  const bytes = fs.statSync(dataPath).size;
  const receipt = JSON.parse(fs.readFileSync(dataPath, "utf8"));

  assert.ok(bytes <= 250_000, `receipt is ${bytes} bytes`);
  assert.equal(receipt.schema_version, "andalucia_water_commitment_receipt_v1");
  assert.equal(receipt.snapshot_date, "2026-07-25");
  assert.equal(receipt.commitments.length, 3);
  assert.equal(receipt.summary.post_investiture_actions_total, 0);
  assert.equal(receipt.history.status, "first_snapshot");
  assert.equal(receipt.history.previous_snapshot_date, null);
  assert.equal(receipt.history.commitments_changed_total, 0);
  assert.equal(receipt.freshness.last_checked_date, "2026-07-25");
  assert.equal(receipt.freshness.next_check_date, "2026-08-01");
  assert.equal(receipt.freshness.stale_after_date, "2026-08-03");
  assert.deepEqual(
    receipt.commitments.map((item) => item.commitment_id),
    [
      "ley-andaluza-regadios",
      "reglamento-planificacion-agua",
      "actualizacion-ley-aguas",
    ],
  );
  assert.ok(receipt.commitments.every((item) => item.status === "declarado"));
  assert.ok(
    receipt.commitments.every(
      (item) =>
        item.declared_source_id &&
        item.checkpoint &&
        item.unknowns.length > 0 &&
        item.limitations.length > 0,
    ),
  );

  const publicCopy = JSON.stringify(receipt).toLowerCase();
  assert.doesNotMatch(publicCopy, /\bincumplid[oa]s?\b/u);
  assert.doesNotMatch(publicCopy, /\bretrasad[oa]s?\b/u);
});

test("receipt only cites official HTTPS sources", () => {
  const receipt = JSON.parse(fs.readFileSync(dataPath, "utf8"));
  const urls = [
    ...receipt.sources.map((source) => source.url),
    ...receipt.evidence_check.official_scopes.map((source) => source.url),
  ];

  for (const value of urls) {
    const url = new URL(value);
    assert.equal(url.protocol, "https:");
    assert.match(
      url.hostname,
      /(^|\.)((juntadeandalucia|parlamentodeandalucia)\.es)$/u,
    );
  }
});

test("public route renders the focused answer without loading the operational payload", () => {
  const pageSource = fs.readFileSync(pagePath, "utf8");

  assert.match(pageSource, /data\/water-receipt\.json/u);
  assert.doesNotMatch(pageSource, /data\/accountability\.json/u);
  for (const className of [
    "water-receipt-page",
    "water-receipt-answer",
    "water-receipt-change-summary",
    "water-receipt-commitment",
    "water-receipt-checkpoint",
    "water-receipt-unknowns",
    "water-receipt-method",
    "water-receipt-community-review-call",
    "water-receipt-community-review-track-list",
    "water-receipt-community-review-action-link",
  ]) {
    assert.match(pageSource, new RegExp(`"${className}"`, "u"));
  }
  assert.match(pageSource, /data\/water-receipt\/snapshots\//u);
  assert.match(pageSource, /Participar en la revisión comunitaria/u);
  assert.match(pageSource, /vota-con-la-chola\/issues\/20/u);
  assert.match(pageSource, /Diez minutos\. Una comprobación concreta\./u);
  assert.match(pageSource, /Cinco personas distintas deben cubrir las/u);
  for (const track of [
    "declaraciones",
    "ventana-evidencia",
    "clasificacion",
    "responsabilidad",
    "uso-ciudadano",
  ]) {
    assert.match(pageSource, new RegExp(`key: "${track}"`, "u"));
  }
  assert.match(
    pageSource,
    /water-receipt-community-review-track--\$\{track\.key\}/u,
  );
});

test("election index points to the current receipt, not stale election metadata", () => {
  const indexSource = fs.readFileSync(
    path.join(
      root,
      "ui",
      "gh-pages-next",
      "app",
      "elecciones",
      "page.js",
    ),
    "utf8",
  );

  assert.match(indexSource, /data\/water-receipt\.json/u);
  assert.doesNotMatch(indexSource, /data\/accountability\.json/u);
  assert.match(indexSource, /election-hub\.module\.css/u);
  assert.match(indexSource, /"election-hub-page"/u);
  assert.match(indexSource, /Andalucía 2026 · el recibo del agua/u);
});

test("homepage exposes the focused receipt", () => {
  const homeSource = fs.readFileSync(
    path.join(root, "ui", "gh-pages-next", "app", "page.js"),
    "utf8",
  );

  assert.match(homeSource, /href: "\/elecciones\/andalucia-2026\/"/u);
  assert.match(homeSource, /title: "El recibo del agua de Andalucía"/u);
  assert.match(homeSource, /Tres compromisos de investidura, estado verificable y fuentes oficiales/u);
});

test("public route audit checks content and compact artifact, not only HTTP 200", () => {
  const auditSource = fs.readFileSync(
    path.join(root, "scripts", "audit_public_routes.js"),
    "utf8",
  );

  assert.match(auditSource, /"El recibo del agua de Andalucía"/u);
  assert.match(auditSource, /"Primera ley andaluza de regadíos"/u);
  assert.match(auditSource, /"Sin hito público localizado"/u);
  assert.match(
    auditSource,
    /"\/elecciones\/andalucia-2026\/data\/water-receipt\.json"/u,
  );
  assert.match(auditSource, /missing_content_markers/u);
});

test("immutable first snapshot matches current public receipt", () => {
  const receipt = fs.readFileSync(dataPath);
  const archivePath = path.join(
    root,
    "ui",
    "gh-pages-next",
    "public",
    "elecciones",
    "andalucia-2026",
    "data",
    "water-receipt",
    "snapshots",
    "2026-07-25.json",
  );

  assert.ok(fs.existsSync(archivePath));
  assert.deepEqual(fs.readFileSync(archivePath), receipt);
});

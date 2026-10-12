const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.join(__dirname, "..");

function readRepoFile(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), "utf8");
}

test("comparison route renders the complete bounded real slice", () => {
  const page = readRepoFile("ui/site/app/comparisons/page.js");
  const published = readRepoFile(
    "etl/data/published/promise-action-comparisons-v1.json",
  );
  const publicCopy = readRepoFile(
    "ui/site/public/comparisons/data/comparisons.json",
  );
  const snapshot = JSON.parse(publicCopy);

  assert.equal(publicCopy, published);
  assert.equal(snapshot.real_data_only, true);
  assert.equal(snapshot.synthetic_or_mock, false);
  assert.equal(snapshot.items.length, 5);
  assert.equal(snapshot.counts.evidence_total, 18);
  assert.equal(snapshot.counts.action_pairs_total, 4);
  assert.equal(snapshot.counts.bounded_action_search_assessments_total, 1);
  assert.equal(snapshot.counts.strong_pairs_total, 0);
  assert.deepEqual(snapshot.status_counts, {
    ambiguous_mapping: 3,
    insufficient_evidence: 1,
    not_comparable: 1,
  });
  assert.ok(snapshot.items.every((item) => item.directional_countable === false));
  assert.ok(snapshot.items.every((item) => item.claim.actor_label === "BNG"));
  assert.deepEqual(
    new Set(
      snapshot.items
        .filter((item) => item.action)
        .map((item) => item.action.member_name),
    ),
    new Set(["MARÍA CARMEN DA SILVA MÉNDEZ", "Néstor Rego Candamil"]),
  );
  assert.match(page, /snapshot\.items/);
  assert.doesNotMatch(page, /snapshot\.comparisons/);
  assert.doesNotMatch(page, /snapshot\.items[^\n]*\.slice\(/);
});

test("comparison copy makes uncertainty, capacity, and non-causal limits visible", () => {
  const page = readRepoFile("ui/site/app/comparisons/page.js");
  const snapshot = JSON.parse(
    readRepoFile("ui/site/public/comparisons/data/comparisons.json"),
  );

  assert.match(page, /Comparar no es sentenciar/);
  assert.match(page, /cumplimiento total, sinceridad, legalidad, intención, mérito, culpa, causalidad ni corrupción/);
  assert.match(page, /No encontrar una acción en un recorte no demuestra inacción ni incumplimiento/);
  assert.match(page, /Confianza mide calidad de lectura/);
  assert.match(page, /Ranking oculto/);
  assert.match(page, /Evaluaciones revisadas/);
  assert.match(page, /Pares con acción/);
  assert.match(page, /Búsquedas acotadas/);
  assert.match(page, /cuatro pares con acción y una búsqueda acotada/);
  assert.doesNotMatch(page, /Compara cada compromiso con una acción posterior concreta/);
  assert.doesNotMatch(page, /Cinco pares reales revisados/);
  assert.match(page, /actor_capacity\?\.assertion_capacity/);
  assert.match(page, /counterevidence\?\.search_state/);
  assert.ok(snapshot.items.every((item) => item.mapping_review.mapping_state));
  assert.ok(snapshot.items.every((item) => item.confidence.aggregate_value === 0));
  assert.ok(snapshot.items.every((item) => item.coverage.exhaustive === false));
  assert.ok(snapshot.items.every((item) => item.counterevidence.exhaustive === false));
  assert.ok(snapshot.items.every((item) => item.evidence.some((edge) => edge.evidence_side === "claim")));
});

test("comparison route is discoverable, auditable, semantic, and motion-safe", () => {
  const page = readRepoFile("ui/site/app/comparisons/page.js");
  const styles = readRepoFile(
    "ui/site/app/comparisons/comparisons.module.css",
  );
  const home = readRepoFile("ui/site/app/page.js");
  const catalog = readRepoFile("ui/site/app/siteCatalog.mjs");
  const breadcrumbs = readRepoFile("ui/site/app/components/Breadcrumbs.js");
  const routeAudit = readRepoFile("scripts/audit_public_routes.js");

  assert.match(home, /href: "\/comparisons\/"/);
  assert.match(catalog, /path: "\/comparisons\/data\/comparisons\.json"/);
  assert.match(breadcrumbs, /comparisons: "Dicho frente a hecho"/);
  assert.match(routeAudit, /"\/comparisons\/"/);
  assert.match(routeAudit, /"\/comparisons\/data\/comparisons\.json"/);
  assert.match(page, /comparison-evidence-side__quote/);
  assert.match(page, /comparison-card__mapping-fact/);
  assert.match(page, /comparison-card__counterevidence/);
  assert.match(styles, /@keyframes comparisons-page-enter/);
  assert.match(styles, /@keyframes comparison-connector-grow/);
  assert.match(styles, /transition: grid-template-columns 220ms ease/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.join(__dirname, "..");

function readRepoFile(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), "utf8");
}

test("indicator route exposes the complete bounded real Eurostat slice", () => {
  const page = readRepoFile("ui/site/app/indicators/page.js");
  const feed = JSON.parse(
    readRepoFile("ui/site/public/indicators/data/eurostat-gdp-es.json"),
  );

  assert.equal(feed.policy.real_data_only, true);
  assert.equal(feed.policy.synthetic_or_mock, false);
  assert.equal(feed.policy.causal_claim, "none");
  assert.equal(feed.full_corpus.observations, 1755809);
  assert.equal(feed.full_corpus.representative_scope, false);
  assert.equal(feed.coverage.series, 86);
  assert.equal(feed.coverage.observations, 2091);
  assert.equal(feed.coverage.source_status_codes.p, 113);
  assert.equal(feed.series.length, 86);
  assert.match(page, /snapshot\.series/);
  assert.match(page, /series\.observations/);
  assert.match(page, /observation\.raw_cell_index/);
  assert.match(page, /source_status_code/);
});

test("indicator route states revision and causal limits in reader-facing language", () => {
  const page = readRepoFile("ui/site/app/indicators/page.js");
  const home = readRepoFile("ui/site/app/page.js");
  const catalog = readRepoFile("ui/site/app/siteCatalog.mjs");
  const breadcrumbs = readRepoFile("ui/site/app/components/Breadcrumbs.js");
  const routeAudit = readRepoFile("scripts/audit_public_routes.js");

  assert.match(page, /Un indicador no reparte mérito ni culpa/);
  assert.match(page, /Baseline no significa dato definitivo/);
  assert.match(page, /pendiente de segunda captura/);
  assert.match(page, /No demuestra que una política, partido o cargo causara/);
  assert.match(page, /Todos los códigos oficiales|Toda la geografía española/);
  assert.match(home, /href: "\/indicators\/"/);
  assert.match(catalog, /path: "\/indicators\/data\/eurostat-gdp-es\.json"/);
  assert.match(breadcrumbs, /indicators: "Indicadores"/);
  assert.match(routeAudit, /"\/indicators\/"/);
  assert.match(routeAudit, /"\/indicators\/data\/eurostat-gdp-es\.json"/);
});

test("indicator UI has stable semantic classes and motion-safe layout changes", () => {
  const page = readRepoFile("ui/site/app/indicators/page.js");
  const styles = readRepoFile("ui/site/app/indicators/indicators.module.css");

  assert.match(page, /indicators-page/);
  assert.match(page, /indicator-history__item/);
  assert.match(page, /indicator-geography__table-row/);
  assert.match(page, /indicator-provenance__hash/);
  assert.match(styles, /@keyframes indicators-page-enter/);
  assert.match(styles, /@keyframes indicator-bar-grow/);
  assert.match(styles, /transition: grid-template-columns 220ms ease/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

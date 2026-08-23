const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.join(__dirname, "..");

function readRepoFile(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), "utf8");
}

test("geopolitics route renders every real action without truncation", () => {
  const page = readRepoFile("ui/gh-pages-next/app/geopolitics/page.js");
  const feed = JSON.parse(
    readRepoFile(
      "ui/gh-pages-next/public/geopolitics/data/moncloa-sample.json",
    ),
  );

  assert.equal(feed.policy.real_data_only, true);
  assert.equal(feed.policy.synthetic_or_mock, false);
  assert.equal(feed.policy.official_public_domain_information_retained, true);
  assert.equal(feed.policy.inference_level, "fact_only");
  assert.equal(feed.records.length, 2);
  assert.equal(feed.coverage.actions, 2);
  assert.equal(feed.coverage.actors, 11);
  assert.equal(feed.coverage.positions, 0);
  assert.equal(feed.coverage.later_observations, 0);
  assert.match(page, /snapshot\.records \|\| \[\]\)\.map/);
  assert.doesNotMatch(page, /snapshot\.records[^\n]*\.slice\(/);
});

test("geopolitics route exposes actors, source evidence, and legal-stage limits", () => {
  const page = readRepoFile("ui/gh-pages-next/app/geopolitics/page.js");
  const home = readRepoFile("ui/gh-pages-next/app/page.js");
  const catalog = readRepoFile("ui/gh-pages-next/app/siteCatalog.mjs");
  const breadcrumbs = readRepoFile(
    "ui/gh-pages-next/app/components/Breadcrumbs.js",
  );
  const routeAudit = readRepoFile("scripts/audit_public_routes.js");

  assert.match(page, /Autorización no significa tratado en vigor/);
  assert.match(page, /entrada en vigor, implementación, uso ni resultado/);
  assert.match(page, /alineamiento e impacto siguen como no evaluados/);
  assert.match(page, /actor\.source_label/);
  assert.match(page, /evidence\?\.exact_quote/);
  assert.match(page, /Abrir referencia oficial/);
  assert.match(home, /href: "\/geopolitics\/"/);
  assert.match(catalog, /path: "\/geopolitics\/data\/moncloa-sample\.json"/);
  assert.match(breadcrumbs, /geopolitics: "Geopolítica"/);
  assert.match(routeAudit, /"\/geopolitics\/"/);
  assert.match(routeAudit, /"\/geopolitics\/data\/moncloa-sample\.json"/);
});

test("geopolitics UI has semantic selectors and motion-safe feedback", () => {
  const page = readRepoFile("ui/gh-pages-next/app/geopolitics/page.js");
  const styles = readRepoFile(
    "ui/gh-pages-next/app/geopolitics/geopolitics.module.css",
  );

  assert.match(page, /geopolitics-page/);
  assert.match(page, /geopolitics-action-card__actor-name/);
  assert.match(page, /geopolitics-action-card__evidence-quote/);
  assert.match(page, /geopolitics-action-card__state-grid/);
  assert.match(styles, /@keyframes geopolitics-page-enter/);
  assert.match(styles, /transition: transform 180ms ease/);
  assert.match(styles, /transition: grid-template-columns 220ms ease/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

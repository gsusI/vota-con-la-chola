const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.join(__dirname, "..");

function readRepoFile(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), "utf8");
}

test("agreements route renders every real record without truncation", () => {
  const page = readRepoFile("ui/gh-pages-next/app/agreements/page.js");
  const feed = JSON.parse(
    readRepoFile("ui/gh-pages-next/public/agreements/data/moncloa-sample.json"),
  );

  assert.equal(feed.real_data_only, true);
  assert.equal(feed.synthetic_or_mock, false);
  assert.equal(feed.public_domain_information_policy, "retained_exactly");
  assert.equal(feed.records.length, 11);
  assert.equal(feed.counts.attendance_claims, 0);
  assert.equal(feed.counts.influence_assertions, 0);
  assert.deepEqual(feed.influence_assertions, []);
  assert.match(page, /snapshot\.records \|\| \[\]\)\.map/);
  assert.doesNotMatch(page, /snapshot\.records[^\n]*\.slice\(/);
});

test("agreements route exposes actors, exact evidence, and inference limits", () => {
  const page = readRepoFile("ui/gh-pages-next/app/agreements/page.js");
  const home = readRepoFile("ui/gh-pages-next/app/page.js");
  const catalog = readRepoFile("ui/gh-pages-next/app/siteCatalog.mjs");
  const routeAudit = readRepoFile("scripts/audit_public_routes.js");

  assert.match(page, /Reunión no significa influencia/);
  assert.match(page, /no publicados en esta captura/);
  assert.match(page, /no afirmada/);
  assert.match(page, /Abrir referencia oficial/);
  assert.match(page, /party\.source_label/);
  assert.match(home, /href: "\/agreements\/"/);
  assert.match(catalog, /path: "\/agreements\/data\/moncloa-sample\.json"/);
  assert.match(routeAudit, /"\/agreements\/"/);
  assert.match(routeAudit, /"\/agreements\/data\/moncloa-sample\.json"/);
});

test("agreements UI has semantic selectors and motion-safe feedback", () => {
  const page = readRepoFile("ui/gh-pages-next/app/agreements/page.js");
  const styles = readRepoFile(
    "ui/gh-pages-next/app/agreements/agreements.module.css",
  );

  assert.match(page, /agreements-page/);
  assert.match(page, /agreement-evidence-card__actor-name/);
  assert.match(page, /agreement-evidence-card__hash/);
  assert.match(styles, /@keyframes agreements-page-enter/);
  assert.match(styles, /transition: transform 180ms ease/);
  assert.match(styles, /transition: grid-template-columns 220ms ease/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

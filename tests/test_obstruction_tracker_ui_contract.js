const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.join(__dirname, "..");

function readRepoFile(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), "utf8");
}

test("obstruction tracker renders every real blocked source and scale gap", () => {
  const page = readRepoFile("ui/gh-pages-next/app/obstruction-tracker/page.js");
  const feed = JSON.parse(readRepoFile("ui/gh-pages-next/public/obstruction-tracker/data/obstructions.json"));

  assert.ok(feed.blocked_sources.length > 0);
  assert.ok(feed.incidents.length > 0);
  assert.ok(feed.scale_readiness.corpora.length > 0);
  assert.ok(feed.scale_readiness.gaps.length > 0);
  assert.match(page, /snapshot\.blocked_sources \|\| \[\]\)\.map/);
  assert.match(page, /readiness\.corpora \|\| \[\]\)\.map/);
  assert.match(page, /readiness\.gaps \|\| \[\]\)\.map/);
  assert.doesNotMatch(page, /blocked_sources[^\n]*\.slice\(/);
});

test("obstruction tracker exposes source evidence, policy and machine-readable feed", () => {
  const page = readRepoFile("ui/gh-pages-next/app/obstruction-tracker/page.js");
  const home = readRepoFile("ui/gh-pages-next/app/page.js");
  const catalog = readRepoFile("ui/gh-pages-next/app/siteCatalog.mjs");
  const routeAudit = readRepoFile("scripts/audit_public_routes.js");

  assert.match(page, /Solo registros oficiales reales/);
  assert.match(page, /Se conserva para accountability/);
  assert.match(page, /No prueba por sí sola ilegalidad, intención ni corrupción/);
  assert.match(page, /incident\.evidence/);
  assert.match(page, /incident\.tracker_rows_impacted/);
  assert.match(home, /href: "\/obstruction-tracker\/"/);
  assert.match(catalog, /path: "\/obstruction-tracker\/data\/obstructions\.json"/);
  assert.match(routeAudit, /"\/obstruction-tracker\/"/);
  assert.match(routeAudit, /"\/obstruction-tracker\/data\/obstructions\.json"/);
});

test("obstruction tracker has semantic selectors and motion-safe layout feedback", () => {
  const page = readRepoFile("ui/gh-pages-next/app/obstruction-tracker/page.js");
  const styles = readRepoFile("ui/gh-pages-next/app/obstruction-tracker/obstruction-tracker.module.css");

  assert.match(page, /obstruction-tracker-page/);
  assert.match(page, /obstruction-source-card__incidents/);
  assert.match(page, /obstruction-scale-gap__next-action/);
  assert.match(styles, /@keyframes obstruction-page-enter/);
  assert.match(styles, /transition: border-color 180ms ease/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

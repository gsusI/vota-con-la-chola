const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.join(__dirname, "..");

function readRepoFile(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), "utf8");
}

test("transparency dashboard renders all traced metrics and real releases", () => {
  const page = readRepoFile("ui/gh-pages-next/app/transparency/page.js");
  const feed = JSON.parse(readRepoFile("ui/gh-pages-next/public/transparency/data/transparency.json"));

  assert.ok(feed.metrics.length > 0);
  assert.ok(feed.recent_changes.length > 0);
  assert.match(page, /snapshot\.metrics \|\| \[\]\)\.map/);
  assert.match(page, /snapshot\.recent_changes \|\| \[\]\)\.map/);
  assert.doesNotMatch(page, /recent_changes[^\n]*\.slice\(/);
  assert.match(page, /metric\.source_url/);
  assert.match(page, /release\.note\.url/);
});

test("transparency route exposes snapshot, freshness, obstruction and release-note flow", () => {
  const page = readRepoFile("ui/gh-pages-next/app/transparency/page.js");
  const home = readRepoFile("ui/gh-pages-next/app/page.js");
  const catalog = readRepoFile("ui/gh-pages-next/app/siteCatalog.mjs");
  const routeAudit = readRepoFile("scripts/audit_public_routes.js");

  assert.match(page, /Último snapshot público/);
  assert.match(page, /Salud de fuentes/);
  assert.match(page, /Cambios publicados/);
  assert.match(page, /Información personal oficial de dominio público: retenida/);
  assert.match(home, /href: "\/transparency\/"/);
  assert.match(catalog, /path: "\/transparency\/data\/transparency\.json"/);
  assert.match(routeAudit, /"\/transparency\/"/);
  assert.match(routeAudit, /"\/transparency\/data\/transparency\.json"/);
});

test("transparency dashboard has semantic selectors and motion-safe layout feedback", () => {
  const page = readRepoFile("ui/gh-pages-next/app/transparency/page.js");
  const styles = readRepoFile("ui/gh-pages-next/app/transparency/transparency.module.css");

  assert.match(page, /transparency-dashboard-page/);
  assert.match(page, /transparency-metric-card__source/);
  assert.match(page, /transparency-release-card__evidence/);
  assert.match(styles, /@keyframes transparency-page-enter/);
  assert.match(styles, /transition: transform 180ms ease/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

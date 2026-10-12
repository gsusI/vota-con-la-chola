const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.join(__dirname, "..");

function readRepoFile(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), "utf8");
}

test("promises route renders every reviewed real public item", () => {
  const page = readRepoFile("ui/site/app/promises/page.js");
  const feed = JSON.parse(
    readRepoFile("ui/site/public/promises/data/bng-2023.json"),
  );

  assert.equal(feed.real_data_only, true);
  assert.equal(feed.synthetic_or_mock, false);
  assert.equal(feed.items.length, 20);
  assert.ok(feed.items.every((item) => item.review.status === "rule_confirmed"));
  assert.ok(feed.items.every((item) => item.evidence.exact_quote.startsWith("•")));
  assert.match(page, /snapshot\.items \|\| \[\]\)\.map/);
  assert.doesNotMatch(page, /snapshot\.items[^\n]*\.slice\(/);
});

test("promises route exposes official evidence and public machine-readable data", () => {
  const page = readRepoFile("ui/site/app/promises/page.js");
  const home = readRepoFile("ui/site/app/page.js");
  const catalog = readRepoFile("ui/site/app/siteCatalog.mjs");
  const routeAudit = readRepoFile("scripts/audit_public_routes.js");

  assert.match(page, /Abrir PDF oficial/);
  assert.match(page, /Lo dicho no es lo cumplido/);
  assert.match(page, /no afirma si se cumplieron/);
  assert.match(home, /href: "\/promises\/"/);
  assert.match(catalog, /path: "\/promises\/data\/bng-2023\.json"/);
  assert.match(routeAudit, /"\/promises\/"/);
  assert.match(routeAudit, /"\/promises\/data\/bng-2023\.json"/);
});

test("promises UI has semantic selectors and motion-safe physical feedback", () => {
  const page = readRepoFile("ui/site/app/promises/page.js");
  const styles = readRepoFile("ui/site/app/promises/promises.module.css");

  assert.match(page, /promises-page/);
  assert.match(page, /promise-evidence-card__quote/);
  assert.match(page, /promise-evidence-card__hash/);
  assert.match(styles, /@keyframes promises-page-enter/);
  assert.match(styles, /transition: transform 180ms ease/);
  assert.match(styles, /transition: grid-template-columns 220ms ease/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

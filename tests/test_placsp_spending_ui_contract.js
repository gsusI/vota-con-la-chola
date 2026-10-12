const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.join(__dirname, "..");

function readRepoFile(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), "utf8");
}

test("spending route renders every real public award without truncation", () => {
  const page = readRepoFile("ui/site/app/spending/page.js");
  const feed = JSON.parse(
    readRepoFile("ui/site/public/spending/data/placsp-sample.json"),
  );

  assert.equal(feed.real_data_only, true);
  assert.equal(feed.synthetic_or_mock, false);
  assert.equal(feed.public_domain_information_policy, "retained_exactly");
  assert.equal(feed.items.length, 20);
  assert.equal(feed.counts.counterparty_potential_natural_person, 5);
  assert.ok(feed.items.every((item) => item.spending_kind === "procurement_award"));
  assert.ok(feed.items.every((item) => item.dates.paid_on === null));
  assert.match(page, /snapshot\.items \|\| \[\]\)\.map/);
  assert.doesNotMatch(page, /snapshot\.items[^\n]*\.slice\(/);
});

test("spending route exposes exact actors, amounts, and official evidence", () => {
  const page = readRepoFile("ui/site/app/spending/page.js");
  const home = readRepoFile("ui/site/app/page.js");
  const catalog = readRepoFile("ui/site/app/siteCatalog.mjs");
  const routeAudit = readRepoFile("scripts/audit_public_routes.js");

  assert.match(page, /exactActorIdentifier/);
  assert.match(page, /Importe adjudicado sin impuestos/);
  assert.match(page, /Adjudicado no significa pagado/);
  assert.match(page, /Abrir expediente oficial/);
  assert.match(home, /href: "\/spending\/"/);
  assert.match(catalog, /path: "\/spending\/data\/placsp-sample\.json"/);
  assert.match(routeAudit, /"\/spending\/"/);
  assert.match(routeAudit, /"\/spending\/data\/placsp-sample\.json"/);
});

test("spending UI has semantic selectors and motion-safe physical feedback", () => {
  const page = readRepoFile("ui/site/app/spending/page.js");
  const styles = readRepoFile("ui/site/app/spending/spending.module.css");

  assert.match(page, /spending-page/);
  assert.match(page, /spending-award-card__actor-name/);
  assert.match(page, /spending-award-card__hash/);
  assert.match(styles, /@keyframes spending-page-enter/);
  assert.match(styles, /transition: transform 180ms ease/);
  assert.match(styles, /transition: grid-template-columns 220ms ease/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.join(__dirname, "..");

function readRepoFile(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), "utf8");
}

test("actor graph route uses only real public data and exposes bounded samples", () => {
  const page = readRepoFile("ui/gh-pages-next/app/actor-graph/page.js");
  const graph = JSON.parse(
    readRepoFile("ui/gh-pages-next/public/actor-graph/data/graph.json"),
  );

  assert.equal(graph.meta.real_data_only, true);
  assert.equal(graph.meta.synthetic_or_mock, false);
  assert.equal(graph.meta.official_public_domain_information_retained, true);
  assert.equal(graph.sample_contract.bounded, true);
  assert.equal(graph.sample_contract.full_graph_not_embedded_in_browser, true);
  assert.equal(graph.coverage.database_counts.actor_graph_nodes, 133595);
  assert.equal(graph.coverage.database_counts.actor_graph_relationships, 237973);
  assert.equal(graph.coverage.database_counts.actor_graph_relationship_evidence, 237973);
  assert.equal(graph.sample_nodes.length, 32);
  assert.equal(graph.sample_relationships.length, 34);
  assert.match(page, /snapshot\.sample_nodes/);
  assert.match(page, /snapshot\.sample_relationships/);
  assert.match(page, /coverage\.relationships_by_type/);
  assert.match(page, /actor\.source_url/);
  assert.match(page, /relationship\.source_url/);
});

test("actor graph route states identity and causal limits in citizen-facing language", () => {
  const page = readRepoFile("ui/gh-pages-next/app/actor-graph/page.js");
  const home = readRepoFile("ui/gh-pages-next/app/page.js");
  const catalog = readRepoFile("ui/gh-pages-next/app/siteCatalog.mjs");
  const breadcrumbs = readRepoFile("ui/gh-pages-next/app/components/Breadcrumbs.js");
  const routeAudit = readRepoFile("scripts/audit_public_routes.js");

  assert.match(page, /Mismo nombre no significa misma persona/);
  assert.match(page, /nombre por sí solo nunca fusiona actores/);
  assert.match(page, /Una ruta del grafo no prueba corrupción/);
  assert.match(page, /no demuestra causalidad, influencia, mérito, culpa/);
  assert.match(page, /Nombres oficiales ocultados/);
  assert.match(page, /datos reales, cero filas sintéticas/);
  assert.match(home, /href: "\/actor-graph\/"/);
  assert.match(catalog, /path: "\/actor-graph\/data\/graph\.json"/);
  assert.match(breadcrumbs, /"actor-graph": "Grafo de actores"/);
  assert.match(routeAudit, /"\/actor-graph\/"/);
  assert.match(routeAudit, /"\/actor-graph\/data\/graph\.json"/);
  assert.match(routeAudit, /Una ruta del grafo no prueba corrupción/);
});

test("actor graph UI has stable semantic classes and motion-safe layout changes", () => {
  const page = readRepoFile("ui/gh-pages-next/app/actor-graph/page.js");
  const styles = readRepoFile("ui/gh-pages-next/app/actor-graph/actor-graph.module.css");

  assert.match(page, /actor-graph-page/);
  assert.match(page, /actor-sample-card__name/);
  assert.match(page, /relationship-sample-card__path/);
  assert.match(page, /actor-graph-causality-panel__limit/);
  assert.match(page, /actor-graph-provenance__hash-value/);
  assert.match(styles, /@keyframes actor-graph-page-enter/);
  assert.match(styles, /@keyframes actor-graph-edge-grow/);
  assert.match(styles, /transition: grid-template-columns 220ms ease/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

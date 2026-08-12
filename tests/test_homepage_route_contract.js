const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const pageSource = fs.readFileSync(
  path.join(__dirname, "..", "ui", "gh-pages-next", "app", "page.js"),
  "utf8",
);

const expectedRoutes = [
  "/citizen/",
  "/citizen/?mode=audit",
  "/citizen/leaderboards/",
  "/explorer-temas/",
  "/vote-explainer/",
  "/responsibility-explainer/",
  "/explorer-votaciones/",
  "/explorer-politico/",
  "/people/",
  "/explorer-sources/",
  "/parliamentary-accountability/",
  "/initiative-lifecycle/",
  "/elections-behavior/",
  "/calendario-electoral/",
  "/elecciones/andalucia-2026/",
  "/political-positions/",
  "/explorer/",
  "/legal-sanctions/",
  "/policy-outcomes/",
];

test("homepage keeps every public entry route wired", () => {
  for (const route of expectedRoutes) {
    assert.match(pageSource, new RegExp(`href: "${route.replace(/[/?]/g, "\\$&")}"`));
  }
});

test("homepage rendered structure has semantic classes", () => {
  for (const className of [
    "homepage-hero",
    "homepage-primary-link",
    "homepage-signal-panel",
    "homepage-route-group",
    "homepage-route-link",
    "homepage-proof",
  ]) {
    assert.match(pageSource, new RegExp(`className="${className}`));
  }
});

test("homepage routes avoid legacy iframe shells", () => {
  for (const routeFile of [
    "citizen/page.js",
    "citizen/leaderboards/page.js",
    "explorer/page.js",
    "explorer-politico/page.js",
    "explorer-sources/page.js",
    "explorer-temas/page.js",
    "explorer-votaciones/page.js",
    "graph/page.js",
  ]) {
    const source = fs.readFileSync(
      path.join(__dirname, "..", "ui", "gh-pages-next", "app", ...routeFile.split("/")),
      "utf8",
    );
    assert.doesNotMatch(source, /LegacyFrame|legacyPath|<iframe/u);
  }
});

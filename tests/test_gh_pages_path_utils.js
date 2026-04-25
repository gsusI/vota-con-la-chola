const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

async function loadPathUtils() {
  const filePath = path.join(__dirname, "..", "ui", "gh-pages-next", "app", "path-utils.mjs");
  return import(pathToFileURL(filePath).href);
}

function withEnv(value, fn) {
  const previous = process.env.NEXT_PUBLIC_BASE_PATH;
  if (value === null) {
    delete process.env.NEXT_PUBLIC_BASE_PATH;
  } else {
    process.env.NEXT_PUBLIC_BASE_PATH = value;
  }
  try {
    return fn();
  } finally {
    if (previous === undefined) {
      delete process.env.NEXT_PUBLIC_BASE_PATH;
    } else {
      process.env.NEXT_PUBLIC_BASE_PATH = previous;
    }
  }
}

test("GH Pages paths default to custom-domain root", async () => {
  const helpers = await loadPathUtils();

  withEnv(null, () => {
    assert.equal(helpers.resolveBasePath(), "");
    assert.equal(helpers.withBasePath("/citizen/"), "/citizen/");
    assert.equal(helpers.withBasePath("citizen/"), "/citizen/");
    assert.equal(helpers.withBasePath("#section"), "#section");
    assert.equal(helpers.withBasePath("https://example.com/x"), "https://example.com/x");
  });
});

test("GH Pages paths stay idempotent with an explicit repo base path", async () => {
  const helpers = await loadPathUtils();

  withEnv("vota-con-la-chola/", () => {
    const basePath = helpers.resolveBasePath();
    assert.equal(basePath, "/vota-con-la-chola");
    assert.equal(helpers.withBasePath("/citizen/", basePath), "/vota-con-la-chola/citizen/");
    assert.equal(helpers.withBasePath("/vota-con-la-chola/citizen/", basePath), "/vota-con-la-chola/citizen/");
    assert.equal(helpers.stripBasePath("/vota-con-la-chola/citizen/", basePath), "/citizen/");
    assert.equal(
      helpers.withBasePath(helpers.stripBasePath("/vota-con-la-chola/citizen/", basePath), basePath),
      "/vota-con-la-chola/citizen/",
    );
  });
});

test("static route pages read published legacy data without iframe shells", () => {
  const expectedRoutes = {
    "explorer/page.js": "legacy/graph/data/graph.json",
    "explorer-politico/page.js": "legacy/explorer-politico/data/arena-mandates.json",
    "explorer-sources/page.js": "legacy/explorer-sources/data/status.json",
    "explorer-temas/page.js": "legacy/explorer-temas/data/temas-preview.json",
    "explorer-votaciones/page.js": "legacy/explorer-votaciones/data/votes-preview.json",
  };

  for (const [routeFile, expectedDataPath] of Object.entries(expectedRoutes)) {
    const filePath = path.join(__dirname, "..", "ui", "gh-pages-next", "app", routeFile);
    const source = fs.readFileSync(filePath, "utf8");
    assert.match(source, new RegExp(`readPublicJson\\("${expectedDataPath}"`));
    assert.doesNotMatch(source, /LegacyFrame|legacyPath|<iframe/u);
  }
});

test("legacy iframe publish recipe copies route-local data", () => {
  const justfile = fs.readFileSync(path.join(__dirname, "..", "justfile"), "utf8");
  const dataRoutes = [
    "explorer-politico",
    "explorer-sources",
    "explorer-temas",
    "explorer-votaciones",
  ];

  for (const route of dataRoutes) {
    assert.match(justfile, new RegExp(`\\{\\{gh_pages_dir\\}\\}/legacy/${route}/data`));
    assert.match(
      justfile,
      new RegExp(
        `cp -R "\\{\\{gh_pages_dir\\}\\}/${route}/data/\\." "\\{\\{gh_pages_dir\\}\\}/legacy/${route}/data/"`,
      ),
    );
  }
});

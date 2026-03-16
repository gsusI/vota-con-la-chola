const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

async function loadCatalog() {
  const filePath = path.join(
    __dirname,
    "..",
    "ui",
    "gh-pages-next",
    "app",
    "siteCatalog.mjs",
  );
  return import(pathToFileURL(filePath).href);
}

test("site catalog exposes the five canonical public families", async () => {
  const catalog = await loadCatalog();
  const ids = catalog.siteSections.map((section) => section.id);

  assert.deepEqual(ids, ["topics", "actors", "decisions", "outcomes", "methods"]);
  for (const section of catalog.siteSections) {
    assert.match(section.href, /^\/[a-z-]+\/$/u);
    assert.ok(String(section.question || "").trim().length > 0);
    assert.ok(Array.isArray(section.surfaces) && section.surfaces.length >= 3);
    assert.ok(Array.isArray(section.tasks) && section.tasks.length >= 3);
  }
});

test("home question cards map one-to-one to canonical families", async () => {
  const catalog = await loadCatalog();
  const questions = catalog.getHomeQuestionCards();

  assert.equal(questions.length, catalog.siteSections.length);
  assert.deepEqual(
    questions.map((item) => item.sectionId),
    catalog.siteSections.map((section) => section.id),
  );
});

test("dataset catalog only references known families and published data paths", async () => {
  const catalog = await loadCatalog();
  const validIds = new Set(catalog.siteSections.map((section) => section.id));

  assert.ok(catalog.datasetCatalog.length >= 10);
  for (const dataset of catalog.datasetCatalog) {
    assert.ok(validIds.has(dataset.sectionId), `unknown section ${dataset.sectionId}`);
    assert.match(dataset.path, /^\/.+\/data\/.+\.json$/u);
    assert.ok(String(dataset.label || "").trim().length > 0);
    assert.ok(String(dataset.note || "").trim().length > 0);
  }
});

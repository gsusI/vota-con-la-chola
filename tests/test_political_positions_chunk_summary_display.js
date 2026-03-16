const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

async function loadHelper() {
  const filePath = path.join(
    __dirname,
    "..",
    "ui",
    "gh-pages-next",
    "app",
    "political-positions",
    "chunkSummaryDisplay.mjs",
  );
  return import(pathToFileURL(filePath).href);
}

test("chunk summary chip stays hidden when summary is missing", async () => {
  const helper = await loadHelper();
  assert.equal(helper.shouldShowPersonTrajectoryChunkSummary(null), false);
  assert.equal(helper.shouldShowPersonTrajectoryChunkSummary(undefined), false);
});

test("chunk summary chip stays hidden for non-chunk scan modes", async () => {
  const helper = await loadHelper();
  assert.equal(helper.shouldShowPersonTrajectoryChunkSummary({ scanMode: "default_rows" }), false);
  assert.equal(helper.shouldShowPersonTrajectoryChunkSummary({ scanMode: "sort_preview" }), false);
  assert.equal(helper.shouldShowPersonTrajectoryChunkSummary({ scanMode: "topic_preview" }), false);
});

test("chunk summary chip shows for chunk-based scan modes", async () => {
  const helper = await loadHelper();
  assert.equal(helper.shouldShowPersonTrajectoryChunkSummary({ scanMode: "progressive" }), true);
  assert.equal(helper.shouldShowPersonTrajectoryChunkSummary({ scanMode: "exhaustive" }), true);
  assert.equal(helper.shouldShowPersonTrajectoryChunkSummary({ scanMode: "topic_discovery" }), true);
});

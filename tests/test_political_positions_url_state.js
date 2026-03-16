const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

async function loadHelpers() {
  const filePath = path.join(
    __dirname,
    "..",
    "ui",
    "gh-pages-next",
    "app",
    "political-positions",
    "urlState.mjs",
  );
  return import(pathToFileURL(filePath).href);
}

test("readPoliticalPositionsUrlState parses exact topic share state", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.readPoliticalPositionsUrlState("?topic=Moci%C3%B3n+de+vivienda&topic_id=327&origin_pack=servicios_publicos&origin_concern=vivienda&origin_topic_id=327&search_mode=topic&limit=220"),
    {
      ...helpers.defaultPoliticalPositionsState(),
      topic: "Moción de vivienda",
      topicId: 327,
      originPack: "servicios_publicos",
      originConcern: "vivienda",
      originTopicId: 327,
      searchMode: "topic",
      limit: 220,
    },
  );
});

test("buildPoliticalPositionsUrlSearch keeps exact topic id and omits defaults", async () => {
  const helpers = await loadHelpers();

  assert.equal(
    helpers.buildPoliticalPositionsUrlSearch({
      ...helpers.defaultPoliticalPositionsState(),
      topic: "Moción consecuencia de interpelación urgente sobre vivienda",
      topicId: 327,
      originPack: "servicios_publicos",
      originConcern: "vivienda",
      originTopicId: 327,
    }),
    "origin_pack=servicios_publicos&origin_concern=vivienda&origin_topic_id=327&topic=Moci%C3%B3n+consecuencia+de+interpelaci%C3%B3n+urgente+sobre+vivienda&topic_id=327",
  );
});

test("normalizePoliticalPositionsSearchMode clamps unknown values to auto", async () => {
  const helpers = await loadHelpers();

  assert.equal(helpers.normalizePoliticalPositionsSearchMode("topic"), "topic");
  assert.equal(helpers.normalizePoliticalPositionsSearchMode("PERSON"), "person");
  assert.equal(helpers.normalizePoliticalPositionsSearchMode("timeline"), "auto");
});

test("restorePoliticalPositionsDiscoveryState returns to the originating pack route", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.restorePoliticalPositionsDiscoveryState({
      ...helpers.defaultPoliticalPositionsState(),
      topic: "Moción de vivienda",
      topicId: 327,
      originPack: "servicios_publicos",
      originTopicId: 327,
      searchMode: "topic",
      q: "vivienda",
      method: "votes",
    }),
    {
      ...helpers.defaultPoliticalPositionsState(),
      pack: "servicios_publicos",
      originTopicId: 327,
      method: "votes",
    },
  );
});

test("restorePoliticalPositionsDiscoveryState returns to the originating concern route", async () => {
  const helpers = await loadHelpers();

  assert.deepEqual(
    helpers.restorePoliticalPositionsDiscoveryState({
      ...helpers.defaultPoliticalPositionsState(),
      topic: "Ley estatal de vivienda",
      topicId: 1,
      originConcern: "vivienda",
      originTopicId: 1,
      q: "ley",
      searchMode: "topic",
      stance: "support",
    }),
    {
      ...helpers.defaultPoliticalPositionsState(),
      concern: "vivienda",
      originTopicId: 1,
      stance: "support",
    },
  );
});

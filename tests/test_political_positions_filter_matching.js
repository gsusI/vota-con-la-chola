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
    "filterMatching.mjs",
  );
  return import(pathToFileURL(filePath).href);
}

test("resolveExactTopicFilterSelection matches canonical key exactly", async () => {
  const helpers = await loadHelpers();
  const topics = [
    { topic_id: 7, topic_key: "movilidad-sostenible", topic_label: "Proyecto de Ley de Movilidad Sostenible" },
    { topic_id: 8, topic_key: "seguridad-aerea", topic_label: "Seguridad Aérea" },
  ];

  assert.deepEqual(
    helpers.resolveExactTopicFilterSelection(topics, "movilidad-sostenible"),
    { topicId: 7, key: "movilidad-sostenible", label: "Proyecto de Ley de Movilidad Sostenible" },
  );
});

test("resolveExactTopicFilterSelection matches label accent-insensitively", async () => {
  const helpers = await loadHelpers();
  const topics = [
    { topic_id: 8, topic_key: "seguridad-aerea", topic_label: "Seguridad Aérea" },
  ];

  assert.deepEqual(
    helpers.resolveExactTopicFilterSelection(topics, "seguridad aerea"),
    { topicId: 8, key: "seguridad-aerea", label: "Seguridad Aérea" },
  );
});

test("resolveExactTopicFilterSelection accepts the published camelCase topic shape", async () => {
  const helpers = await loadHelpers();
  const topics = [
    { topicId: 12, key: "movilidad-sostenible", label: "Proyecto de Ley de Movilidad Sostenible." },
  ];

  assert.deepEqual(
    helpers.resolveExactTopicFilterSelection(topics, "Proyecto de Ley de Movilidad Sostenible."),
    { topicId: 12, key: "movilidad-sostenible", label: "Proyecto de Ley de Movilidad Sostenible." },
  );
});

test("topicFilterMatches uses exact topic id when a resolved topic exists", async () => {
  const helpers = await loadHelpers();
  const resolvedTopic = { topicId: 8, key: "seguridad-aerea", label: "Seguridad Aérea" };

  assert.equal(
    helpers.topicFilterMatches({
      rawFilter: "seguridad aerea",
      resolvedTopic,
      topicId: 8,
      topicKey: "otro-topic",
      topicLabel: "Otro",
    }),
    true,
  );
  assert.equal(
    helpers.topicFilterMatches({
      rawFilter: "seguridad aerea",
      resolvedTopic,
      topicId: 9,
      topicKey: "seguridad-aerea",
      topicLabel: "Seguridad Aérea",
    }),
    false,
  );
});

test("topicFilterMatches falls back to substring matching when no exact topic is resolved", async () => {
  const helpers = await loadHelpers();

  assert.equal(
    helpers.topicFilterMatches({
      rawFilter: "movilidad",
      resolvedTopic: null,
      topicId: 7,
      topicKey: "movilidad-sostenible",
      topicLabel: "Proyecto de Ley de Movilidad Sostenible",
    }),
    true,
  );
  assert.equal(
    helpers.topicFilterMatches({
      rawFilter: "vivienda",
      resolvedTopic: null,
      topicId: 7,
      topicKey: "movilidad-sostenible",
      topicLabel: "Proyecto de Ley de Movilidad Sostenible",
    }),
    false,
  );
});

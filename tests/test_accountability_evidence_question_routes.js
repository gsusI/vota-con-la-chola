const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const ROOT = path.join(__dirname, "..");
const APP_ROOT = path.join(ROOT, "ui", "gh-pages-next", "app");

test("Evidence API Q&A route helper builds stable shareable paths", async () => {
  const utilsPath = path.join(APP_ROOT, "accountability-evidence", "evidence-utils.mjs");
  const { qaAnswerHref, qaAnswerSlug } = await import(pathToFileURL(utilsPath).href);
  const answer = { answer_id: "qa:issue:issue-1" };

  assert.match(qaAnswerSlug(answer), /^qa-issue-issue-1-[0-9a-z]+$/u);
  assert.match(
    qaAnswerHref(answer),
    /^\/accountability-evidence\/questions\/qa-issue-issue-1-[0-9a-z]+\/$/u,
  );
});

test("Evidence API index links Q&A cards to static detail routes", () => {
  const indexPath = path.join(APP_ROOT, "accountability-evidence", "page.js");
  const questionsIndexPath = path.join(APP_ROOT, "accountability-evidence", "questions", "page.js");
  const detailPath = path.join(APP_ROOT, "accountability-evidence", "questions", "[answerSlug]", "page.js");
  const indexSource = fs.readFileSync(indexPath, "utf8");
  const questionsIndexSource = fs.readFileSync(questionsIndexPath, "utf8");
  const detailSource = fs.readFileSync(detailPath, "utf8");

  assert.match(indexSource, /qaAnswerHref\(answer\)/u);
  assert.match(questionsIndexSource, /qaAnswerHref\(answer\)/u);
  assert.match(questionsIndexSource, /qa_answers_with_self_route_total/u);
  assert.match(detailSource, /export async function generateStaticParams/u);
  assert.match(detailSource, /dynamicParams = false/u);
  assert.match(detailSource, /findQaAnswerBySlug/u);
});

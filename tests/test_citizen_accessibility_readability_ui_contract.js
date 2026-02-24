const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI includes skip link and main landmark focus target", () => {
  const html = readCitizenHtml();
  assert.match(html, /class="skipLink"\s+href="#citizenMain"/i);
  assert.match(html, /id="citizenMain"/i);
  assert.match(html, /id="citizenMain"[^>]*tabindex="-1"/i);
  assert.match(html, /id="citizenMain"[^>]*aria-label="Panel principal de comparacion"/i);
});

test("citizen UI includes accessibility/readability markers for status and sections", () => {
  const html = readCitizenHtml();
  assert.match(html, /id="statusChips"[^>]*role="status"[^>]*aria-live="polite"/i);
  assert.match(html, /id="banner"[^>]*role="status"[^>]*aria-live="polite"/i);
  assert.match(html, /aria-labelledby="concernSectionHeading"/i);
  assert.match(html, /aria-labelledby="itemsSectionHeading"/i);
  assert.match(html, /aria-labelledby="compareSectionHeading"/i);
  assert.match(html, /id="concernSearch"[^>]*aria-label="Buscar preocupaciones"/i);
  assert.match(html, /id="topicSearch"[^>]*aria-label="Buscar items por titulo"/i);
  assert.match(html, /id="compare"[^>]*role="region"[^>]*aria-label="Resultados por partido"/i);
  assert.match(html, /\.row:focus-visible/i);
  assert.match(html, /\.skipLink:focus/i);
});

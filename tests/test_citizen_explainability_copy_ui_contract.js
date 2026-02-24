const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI exposes explainability glossary with tooltip metadata", () => {
  const html = readCitizenHtml();
  assert.match(html, /data-explainability-glossary=["']1["']/i);
  assert.match(html, /data-explainability-term=["']unknown["']/i);
  assert.match(html, /data-explainability-term=["']cobertura["']/i);
  assert.match(html, /data-explainability-term=["']confianza["']/i);
  assert.match(html, /data-explainability-term=["']evidencia["']/i);
  assert.match(html, /data-explainability-tooltip=["']1["']/i);
  assert.match(html, /data-term-definition=/i);

  const termMarkers = html.match(/data-explainability-term=/gi) || [];
  const tooltipMarkers = html.match(/data-explainability-tooltip=["']1["']/gi) || [];
  const definitionMarkers = html.match(/data-term-definition=/gi) || [];
  assert.ok(termMarkers.length >= 4);
  assert.ok(tooltipMarkers.length >= 4);
  assert.ok(definitionMarkers.length >= 4);
});

test("citizen UI includes plain-language explainability copy hints", () => {
  const html = readCitizenHtml();
  assert.match(html, /data-explainability-copy=["']1["']/i);
  assert.match(html, /primero mira cobertura y luego abre evidencia/i);
  assert.match(html, /unknown: incierto mas sin senal/i);
  assert.equal(/embedding|ontologia|bayesiano|vectorizacion/i.test(html), false);
});

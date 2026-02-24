const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readCitizenHtml() {
  const p = path.join(__dirname, "..", "ui", "citizen", "index.html");
  return fs.readFileSync(p, "utf8");
}

test("citizen UI includes generated tailwind+md3 stylesheet and primitive class markers", () => {
  const html = readCitizenHtml();
  assert.match(html, /<link[^>]+href="\.\/*tailwind_md3\.generated\.css"/i);
  assert.match(html, /class="top card fadeIn md3-card"/i);
  assert.match(html, /class="chip md3-chip"/i);
  assert.match(html, /class="btn md3-button"/i);
  assert.match(html, /class="tag tagbtn md3-tab"/i);
  assert.match(html, /class="partyCard md3-card/i);
  assert.match(html, /select class="md3-tab" id="viewMode"/i);
  assert.match(html, /select class="md3-tab" id="methodSelect"/i);
});

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readExplorerTemasHtml() {
  const p = path.join(__dirname, "..", "ui", "graph", "explorer-temas.html");
  return fs.readFileSync(p, "utf8");
}

test("explorer-temas accepts citizen coherence URL params", () => {
  const html = readExplorerTemasHtml();
  assert.match(html, /activePartyId\s*:\s*null/i);
  assert.match(html, /const\s+partyId\s*=\s*paramGet\("party"\)\s*\|\|\s*paramGet\("party_id"\)/i);
  assert.match(html, /const\s+source\s*=\s*norm\(paramGet\("source"\)\)/i);
  assert.match(html, /const\s+view\s*=\s*norm\(paramGet\("view"\)\)/i);
  assert.match(html, /const\s+bucket\s*=\s*norm\(paramGet\("bucket"\)\)/i);
  assert.match(html, /source\s*===\s*"citizen_coherence"\s*\|\|\s*view\s*===\s*"coherence"\s*\|\|\s*bucket/i);
});

test("explorer-temas forwards party filter to coherence APIs", () => {
  const html = readExplorerTemasHtml();
  assert.match(html, /apiCoherence\(\{[^}]*partyId/i);
  assert.match(html, /if\s*\(partyId\)\s*p\.set\("party_id"/i);
  assert.match(html, /apiCoherenceEvidence\(\{[\s\S]*partyId:\s*state\.activePartyId/i);
  assert.match(html, /if\s*\(partyId\)\s*p\.set\("party_id"/i);
});

test("explorer-temas auto-opens coherence evidence mode from URL intent", () => {
  const html = readExplorerTemasHtml();
  assert.match(html, /state\.evidence\.mode\s*===\s*"coherence"/i);
  assert.match(html, /loadCoherenceEvidencePage\(\{\s*reset:\s*true,\s*bucket:/i);
  assert.match(html, /paramSet\("view",\s*"coherence"\)/i);
  assert.match(html, /paramSet\("source",\s*"citizen_coherence"\)/i);
});

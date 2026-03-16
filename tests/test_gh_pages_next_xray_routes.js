const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const ROOT = path.join(__dirname, "..");

async function loadKinds() {
  const filePath = path.join(
    ROOT,
    "ui",
    "gh-pages-next",
    "app",
    "people",
    "xray",
    "xrayKinds.mjs",
  );
  return import(pathToFileURL(filePath).href);
}

test("people xray hub route exists", () => {
  const filePath = path.join(ROOT, "ui", "gh-pages-next", "app", "people", "xray", "page.js");
  assert.equal(fs.existsSync(filePath), true);
});

test("xray kind metadata and links stay aligned", async () => {
  const kinds = await loadKinds();
  assert.deepEqual(kinds.XRAY_KIND_ORDER, [
    "party",
    "institution",
    "ambito",
    "territorio",
    "cargo",
  ]);

  assert.equal(kinds.XRAY_KIND_LINKS.length, kinds.XRAY_KIND_ORDER.length);
  for (const kind of kinds.XRAY_KIND_ORDER) {
    const meta = kinds.XRAY_KIND_META[kind];
    assert.ok(meta, `missing meta for ${kind}`);
    assert.equal(meta.kind, kind);
    assert.equal(meta.href, `/people/xray/${kind}/`);
  }
});

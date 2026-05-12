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

test("people xray public data is split below Cloudflare Pages file limit", async () => {
  const kinds = await loadKinds();
  const dataDir = path.join(ROOT, "ui", "gh-pages-next", "public", "people", "data");
  const maxCloudflarePagesBytes = 25 * 1024 * 1024;
  const manifestPath = path.join(dataDir, "xray.json");

  assert.equal(fs.existsSync(manifestPath), true);
  assert.ok(fs.statSync(manifestPath).size < maxCloudflarePagesBytes, "xray.json exceeds Pages file limit");

  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
  assert.deepEqual(manifest.kinds, kinds.XRAY_KIND_ORDER);

  for (const kind of kinds.XRAY_KIND_ORDER) {
    const fileName = manifest.group_files?.[kind] || `xray-${kind}.json`;
    const filePath = path.join(dataDir, fileName);
    assert.equal(fs.existsSync(filePath), true, `missing ${fileName}`);
    assert.ok(fs.statSync(filePath).size < maxCloudflarePagesBytes, `${fileName} exceeds Pages file limit`);
  }
});

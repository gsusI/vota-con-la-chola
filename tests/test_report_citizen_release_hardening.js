const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_release_hardening.js");
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
  });
}

function parseJsonFile(filePath, label) {
  assert.equal(fs.existsSync(filePath), true, `${label}: missing json output file`);
  const raw = fs.readFileSync(filePath, "utf8");
  assert.ok(String(raw || "").trim().length > 0, `${label}: empty json output file`);
  return JSON.parse(raw);
}

function writeFile(root, relPath, content) {
  const p = path.join(root, relPath);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, content, "utf8");
  return p;
}

function makeCitizenFixture(tmpDir, opts) {
  const sourceRoot = path.join(tmpDir, "src");
  const publishedRoot = path.join(tmpDir, "pub");
  fs.mkdirSync(sourceRoot, { recursive: true });
  fs.mkdirSync(publishedRoot, { recursive: true });

  const assets = [
    "index.html",
    "preset_codec.js",
    "onboarding_funnel.js",
    "first_answer_accelerator.js",
    "unknown_explainability.js",
    "cross_method_stability.js",
    "evidence_trust_panel.js",
    "tailwind_md3.generated.css",
    "tailwind_md3.tokens.json",
  ];

  for (const asset of assets) {
    writeFile(sourceRoot, asset, `// src ${asset}\n`);
    const pubContent = opts && opts.mismatchAsset === asset ? `// pub mismatch ${asset}\n` : `// src ${asset}\n`;
    writeFile(publishedRoot, asset, pubContent);
  }

  const snapshot = {
    meta: { as_of_date: "2026-02-23", quality: { status: "ok" } },
    topics: [{ topic_id: 1, title: "A" }],
    parties: [{ party_id: "p1", party_label: "P1" }],
    party_topic_positions: [{ topic_id: 1, party_id: "p1", stance: "support" }],
    party_concern_programas: [],
  };
  writeFile(publishedRoot, "data/citizen.json", JSON.stringify(snapshot, null, 2));

  const concerns = {
    concerns: [{ id: "vivienda", label: "Vivienda", keywords: ["alquiler"] }],
    packs: [{ id: "pack-1", label: "Pack 1", concern_ids: ["vivienda"] }],
  };
  writeFile(sourceRoot, "concerns_v1.json", JSON.stringify(concerns, null, 2));

  return {
    sourceRoot,
    publishedRoot,
    snapshot: path.join(publishedRoot, "data", "citizen.json"),
    concerns: path.join(sourceRoot, "concerns_v1.json"),
    assetsCsv: assets.join(","),
  };
}

test("release hardening reporter passes strict mode on aligned source/published assets", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "citizen-release-hardening-pass-"));
  const fixture = makeCitizenFixture(tmpDir, {});
  const outFile = path.join(tmpDir, "release_pass.json");

  const proc = runReporter([
    "--source-root",
    fixture.sourceRoot,
    "--published-root",
    fixture.publishedRoot,
    "--snapshot",
    fixture.snapshot,
    "--concerns",
    fixture.concerns,
    "--assets",
    fixture.assetsCsv,
    "--json-out",
    outFile,
    "--strict",
  ]);
  assert.equal(proc.status, 0, `unexpected status=${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseJsonFile(outFile, "release_hardening_pass");
  assert.equal(out.summary.total_fail, 0);
  assert.equal(out.readiness.release_ready, true);
  assert.equal(out.readiness.status, "ok");
  assert.equal(out.readiness.parity_total_assets, 9);
  assert.equal(out.readiness.parity_ok_assets, 9);
});

test("release hardening reporter fails strict mode on parity drift and exposes failed asset id", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "citizen-release-hardening-fail-"));
  const fixture = makeCitizenFixture(tmpDir, {
    mismatchAsset: "preset_codec.js",
  });
  const outFile = path.join(tmpDir, "release_fail.json");

  const proc = runReporter([
    "--source-root",
    fixture.sourceRoot,
    "--published-root",
    fixture.publishedRoot,
    "--snapshot",
    fixture.snapshot,
    "--concerns",
    fixture.concerns,
    "--assets",
    fixture.assetsCsv,
    "--json-out",
    outFile,
    "--strict",
  ]);
  assert.equal(proc.status, 1, `expected strict failure; got status=${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseJsonFile(outFile, "release_hardening_fail");
  assert.ok(out.summary.total_fail > 0);
  assert.equal(out.readiness.release_ready, false);
  assert.equal(out.readiness.status, "failed");
  assert.ok(Array.isArray(out.summary.failed_ids));
  assert.ok(out.summary.failed_ids.includes("asset_parity:preset_codec.js"));
  assert.ok(Array.isArray(out.readiness.parity_failed_assets));
  assert.ok(out.readiness.parity_failed_assets.includes("preset_codec.js"));
});

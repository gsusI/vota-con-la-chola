const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_preset_contract_bundle.js");
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
  });
}

function parseStdoutJson(proc, label) {
  assert.equal(proc.signal, null, `${label}: process signaled`);
  assert.ok(proc.stdout && String(proc.stdout).trim(), `${label}: missing stdout JSON`);
  return JSON.parse(proc.stdout);
}

function writeFile(dir, name, content) {
  const p = path.join(dir, name);
  fs.writeFileSync(p, content, "utf8");
  return p;
}

test("preset contract bundle passes strict mode when all subcontracts pass", () => {
  const fixture = path.join(__dirname, "fixtures", "citizen_preset_hash_matrix.json");
  const sourceCanonical = fs.readFileSync(path.join(__dirname, "..", "ui", "citizen", "preset_codec.js"), "utf8");

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-pass-"));
  const sourcePath = writeFile(tmpDir, "source.js", sourceCanonical);
  const publishedPath = writeFile(tmpDir, "published.js", sourceCanonical);

  const proc = runReporter(["--fixture", fixture, "--source", sourcePath, "--published", publishedPath, "--strict"]);
  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "bundle_pass");
  assert.equal(out.summary.sections_total, 3);
  assert.equal(out.summary.sections_fail, 0);
  assert.equal(out.summary.total_fail, 0);
  assert.equal(Array.isArray(out.summary.failed_sections), true);
  assert.equal(out.summary.failed_sections.length, 0);
  assert.equal(out.contracts.fixture_contract.ok, true);
  assert.equal(out.contracts.codec_parity.ok, true);
  assert.equal(out.contracts.codec_sync_state.ok, true);
});

test("preset contract bundle fails strict mode when published asset is stale", () => {
  const fixture = path.join(__dirname, "fixtures", "citizen_preset_hash_matrix.json");
  const sourceCanonical = fs.readFileSync(path.join(__dirname, "..", "ui", "citizen", "preset_codec.js"), "utf8");

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-fail-"));
  const sourcePath = writeFile(tmpDir, "source.js", sourceCanonical);
  const publishedPath = writeFile(tmpDir, "published.js", `${sourceCanonical}\n// drift`);

  const proc = runReporter(["--fixture", fixture, "--source", sourcePath, "--published", publishedPath, "--strict"]);
  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "bundle_fail");
  assert.equal(out.summary.sections_total, 3);
  assert.ok(out.summary.sections_fail >= 1);
  assert.ok(out.summary.total_fail >= 1);
  assert.ok(Array.isArray(out.summary.failed_sections));
  assert.ok(out.summary.failed_sections.includes("codec_parity"));
  assert.ok(out.summary.failed_sections.includes("codec_sync_state"));
  assert.equal(out.contracts.fixture_contract.ok, true);
  assert.equal(out.contracts.codec_parity.ok, false);
  assert.equal(out.contracts.codec_sync_state.ok, false);
  assert.ok(Array.isArray(out.summary.failed_ids));
  assert.ok(out.summary.failed_ids.some((x) => String(x || "").includes("codec_parity:")));
  assert.ok(out.summary.failed_ids.some((x) => String(x || "").includes("codec_sync_state:")));
});

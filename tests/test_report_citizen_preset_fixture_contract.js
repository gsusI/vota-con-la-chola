const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_preset_fixture_contract.js");
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
  });
}

function parseStdoutJson(proc, label) {
  assert.equal(proc.signal, null, `${label}: process signaled`);
  assert.ok(proc.stdout && String(proc.stdout).trim(), `${label}: missing stdout JSON`);
  return JSON.parse(proc.stdout);
}

test("preset fixture reporter passes strict mode for canonical fixture", () => {
  const fixture = path.join(__dirname, "fixtures", "citizen_preset_hash_matrix.json");
  const proc = runReporter(["--fixture", fixture, "--strict"]);

  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "canonical_fixture");

  assert.equal(out.schema_version, "v2");
  assert.equal(out.summary.total_fail, 0);
  assert.ok(out.summary.hash_cases_total > 0);
  assert.ok(out.summary.share_cases_total > 0);
  assert.equal(Array.isArray(out.summary.failed_ids), true);
  assert.equal(out.summary.failed_ids.length, 0);
});

test("preset fixture reporter surfaces failed ids in strict drift run", () => {
  const fixture = path.join(__dirname, "fixtures", "citizen_preset_hash_matrix.json");
  const base = JSON.parse(fs.readFileSync(fixture, "utf8"));
  const bad = JSON.parse(JSON.stringify(base));

  bad.hash_cases = Array.isArray(bad.hash_cases) ? bad.hash_cases : [];
  assert.ok(bad.hash_cases.length > 0, "expected at least one hash_case");
  bad.hash_cases[0].expect = bad.hash_cases[0].expect || {};
  bad.hash_cases[0].expect.error_code = "forced_mismatch_for_test";

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-fixture-drift-"));
  const badPath = path.join(tmpDir, "bad_fixture.json");
  fs.writeFileSync(badPath, JSON.stringify(bad, null, 2), "utf8");

  const proc = runReporter(["--fixture", badPath, "--strict"]);
  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "drift_fixture");
  assert.ok(out.summary.total_fail > 0);
  assert.ok(Array.isArray(out.summary.failed_ids));
  assert.ok(out.summary.failed_ids.some((x) => String(x || "").includes("hash_cases:hash_missing_preset_prefix")));
});

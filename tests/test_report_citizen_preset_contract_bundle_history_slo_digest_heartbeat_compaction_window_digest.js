const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(
    __dirname,
    "..",
    "scripts",
    "report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest.js"
  );
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
  });
}

function parseStdoutJson(proc, label) {
  assert.equal(proc.signal, null, `${label}: process signaled`);
  assert.ok(proc.stdout && String(proc.stdout).trim(), `${label}: missing stdout JSON`);
  return JSON.parse(proc.stdout);
}

function writeJson(absPath, obj) {
  fs.writeFileSync(absPath, `${JSON.stringify(obj, null, 2)}\n`, "utf8");
}

function parityReport(overrides = {}) {
  const base = {
    generated_at: "2026-02-22T00:00:00.000Z",
    heartbeat_path: "/tmp/hb.raw.jsonl",
    compacted_path: "/tmp/hb.compacted.jsonl",
    entries_total_raw: 20,
    entries_total_compacted: 20,
    window_raw_entries: 20,
    raw_window_incidents: 2,
    present_in_compacted_in_window: 20,
    missing_in_compacted_in_window: 0,
    incident_missing_in_compacted: 0,
    raw_window_coverage_pct: 100,
    incident_coverage_pct: 100,
    checks: {
      window_nonempty_ok: true,
      raw_window_malformed_ok: true,
      compacted_malformed_ok: true,
      latest_present_ok: true,
      incident_parity_ok: true,
      failed_parity_ok: true,
      red_parity_ok: true,
    },
    strict_fail_reasons: [],
  };
  return {
    ...base,
    ...overrides,
  };
}

test("compaction-window digest reporter emits ok status in strict mode when parity is complete", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-hb-compact-window-digest-ok-"));
  const parityPath = path.join(tmpDir, "parity.json");

  writeJson(parityPath, parityReport());

  const proc = runReporter(["--compaction-window-json", parityPath, "--strict"]);
  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "digest_ok");
  assert.equal(Array.isArray(out.validation_errors), true);
  assert.equal(out.validation_errors.length, 0);
  assert.equal(out.digest.status, "ok");
  assert.equal(out.digest.risk_level, "green");
  assert.equal(out.digest.risk_reasons.length, 0);
  assert.equal(out.digest.strict_fail_reasons.length, 0);
});

test("compaction-window digest reporter emits degraded status when non-incident rows are missing", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-hb-compact-window-digest-degraded-"));
  const parityPath = path.join(tmpDir, "parity.json");

  writeJson(
    parityPath,
    parityReport({
      entries_total_compacted: 19,
      present_in_compacted_in_window: 19,
      missing_in_compacted_in_window: 1,
      raw_window_coverage_pct: 95,
    })
  );

  const proc = runReporter(["--compaction-window-json", parityPath, "--strict"]);
  assert.equal(proc.status, 0, `unexpected strict exit status: ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "digest_degraded");
  assert.equal(Array.isArray(out.validation_errors), true);
  assert.equal(out.validation_errors.length, 0);
  assert.equal(out.digest.status, "degraded");
  assert.equal(out.digest.risk_level, "amber");
  assert.ok(out.digest.risk_reasons.includes("non_incident_rows_missing_in_compacted_window"));
  assert.ok(out.digest.risk_reasons.includes("raw_window_coverage_below_100"));
  assert.equal(out.digest.strict_fail_reasons.length, 0);
});

test("compaction-window digest reporter fails strict mode when parity report has strict failures", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-hb-compact-window-digest-failed-"));
  const parityPath = path.join(tmpDir, "parity.json");

  writeJson(
    parityPath,
    parityReport({
      present_in_compacted_in_window: 19,
      missing_in_compacted_in_window: 1,
      incident_missing_in_compacted: 1,
      raw_window_coverage_pct: 95,
      incident_coverage_pct: 50,
      checks: {
        window_nonempty_ok: true,
        raw_window_malformed_ok: true,
        compacted_malformed_ok: true,
        latest_present_ok: false,
        incident_parity_ok: false,
        failed_parity_ok: false,
        red_parity_ok: false,
      },
      strict_fail_reasons: [
        "latest_raw_missing_in_compacted",
        "incident_rows_missing_in_compacted",
      ],
    })
  );

  const proc = runReporter(["--compaction-window-json", parityPath, "--strict"]);
  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "digest_failed");
  assert.equal(Array.isArray(out.validation_errors), true);
  assert.equal(out.validation_errors.length, 0);
  assert.equal(out.digest.status, "failed");
  assert.equal(out.digest.risk_level, "red");
  assert.ok(out.digest.strict_fail_reasons.includes("latest_raw_missing_in_compacted"));
  assert.ok(out.digest.strict_fail_reasons.includes("incident_rows_missing_in_compacted"));
});

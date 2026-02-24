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
    "report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.js"
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

function digestReportFixture(overrides = {}) {
  const base = {
    generated_at: "2026-02-22T00:00:05.000Z",
    strict: true,
    input_path: "/tmp/parity.json",
    digest: {
      generated_at: "2026-02-22T00:00:10.000Z",
      strict: true,
      input: {
        compaction_window_json_path: "/tmp/parity.json",
        compaction_window_generated_at: "2026-02-22T00:00:00.000Z",
      },
      status: "ok",
      risk_level: "green",
      risk_reasons: [],
      strict_fail_reasons: [],
      strict_fail_count: 0,
      risk_reason_count: 0,
      key_metrics: {
        entries_total_raw: 20,
        entries_total_compacted: 20,
        window_raw_entries: 20,
        raw_window_incidents: 2,
        present_in_compacted_in_window: 20,
        missing_in_compacted_in_window: 0,
        incident_missing_in_compacted: 0,
        raw_window_coverage_pct: 100,
        incident_coverage_pct: 100,
      },
      key_checks: {
        window_nonempty_ok: true,
        raw_window_malformed_ok: true,
        compacted_malformed_ok: true,
        latest_present_ok: true,
        incident_parity_ok: true,
        failed_parity_ok: true,
        red_parity_ok: true,
      },
      thresholds: {
        max_missing_in_compacted_window_for_ok: 0,
        min_raw_window_coverage_pct_for_ok: 100,
        min_incident_coverage_pct_for_ok: 100,
      },
    },
    validation_errors: [],
  };

  return {
    ...base,
    ...overrides,
    digest: {
      ...base.digest,
      ...(overrides.digest || {}),
      input: {
        ...base.digest.input,
        ...((overrides.digest && overrides.digest.input) || {}),
      },
      key_metrics: {
        ...base.digest.key_metrics,
        ...((overrides.digest && overrides.digest.key_metrics) || {}),
      },
    },
  };
}

test("compact-window digest heartbeat reporter appends one heartbeat in strict pass mode", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-compact-window-digest-hb-pass-"));
  const digestPath = path.join(tmpDir, "digest.json");
  const heartbeatPath = path.join(tmpDir, "heartbeat.jsonl");

  writeJson(digestPath, digestReportFixture());

  const proc = runReporter([
    "--digest-json",
    digestPath,
    "--heartbeat-jsonl",
    heartbeatPath,
    "--strict",
  ]);

  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "compact_window_digest_hb_pass");
  assert.equal(out.validation_errors.length, 0);
  assert.equal(out.appended, true);
  assert.equal(out.duplicate_detected, false);
  assert.equal(out.history_size_before, 0);
  assert.equal(out.history_size_after, 1);
  assert.equal(out.heartbeat.status, "ok");
  assert.equal(out.heartbeat.risk_level, "green");

  const lines = fs.readFileSync(heartbeatPath, "utf8").trim().split(/\r?\n/);
  assert.equal(lines.length, 1);
});

test("compact-window digest heartbeat reporter deduplicates identical heartbeat ids", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-compact-window-digest-hb-dedupe-"));
  const digestPath = path.join(tmpDir, "digest.json");
  const heartbeatPath = path.join(tmpDir, "heartbeat.jsonl");

  writeJson(digestPath, digestReportFixture());

  const proc1 = runReporter([
    "--digest-json",
    digestPath,
    "--heartbeat-jsonl",
    heartbeatPath,
    "--strict",
  ]);
  assert.equal(proc1.status, 0, `first run failed: ${proc1.status}; stderr=${proc1.stderr || ""}`);

  const proc2 = runReporter([
    "--digest-json",
    digestPath,
    "--heartbeat-jsonl",
    heartbeatPath,
    "--strict",
  ]);
  assert.equal(proc2.status, 0, `second run failed: ${proc2.status}; stderr=${proc2.stderr || ""}`);

  const out2 = parseStdoutJson(proc2, "compact_window_digest_hb_dedupe");
  assert.equal(out2.validation_errors.length, 0);
  assert.equal(out2.appended, false);
  assert.equal(out2.duplicate_detected, true);
  assert.equal(out2.history_size_before, 1);
  assert.equal(out2.history_size_after, 1);

  const lines = fs.readFileSync(heartbeatPath, "utf8").trim().split(/\r?\n/);
  assert.equal(lines.length, 1);
});

test("compact-window digest heartbeat reporter fails strict when status is failed but still appends row", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-compact-window-digest-hb-fail-"));
  const digestPath = path.join(tmpDir, "digest.json");
  const heartbeatPath = path.join(tmpDir, "heartbeat.jsonl");

  writeJson(
    digestPath,
    digestReportFixture({
      digest: {
        status: "failed",
        risk_level: "red",
        risk_reasons: ["incident_coverage_below_100"],
        strict_fail_reasons: ["incident_rows_missing_in_compacted"],
        key_metrics: {
          missing_in_compacted_in_window: 2,
          incident_missing_in_compacted: 1,
          raw_window_coverage_pct: 90,
          incident_coverage_pct: 50,
        },
      },
    })
  );

  const proc = runReporter([
    "--digest-json",
    digestPath,
    "--heartbeat-jsonl",
    heartbeatPath,
    "--strict",
  ]);

  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "compact_window_digest_hb_fail");
  assert.equal(out.validation_errors.length, 0);
  assert.equal(out.appended, true);
  assert.equal(out.history_size_before, 0);
  assert.equal(out.history_size_after, 1);
  assert.equal(out.heartbeat.status, "failed");
  assert.equal(out.heartbeat.risk_level, "red");

  const lines = fs.readFileSync(heartbeatPath, "utf8").trim().split(/\r?\n/);
  assert.equal(lines.length, 1);
});

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_preset_contract_bundle_history_slo_digest_heartbeat.js");
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
    input_path: "/tmp/slo.json",
    digest: {
      generated_at: "2026-02-22T00:00:10.000Z",
      strict: true,
      input: {
        slo_json_path: "/tmp/slo.json",
        slo_generated_at: "2026-02-22T00:00:00.000Z",
      },
      status: "ok",
      risk_level: "green",
      risk_reasons: [],
      strict_fail_reasons: [],
      key_metrics: {
        entries_in_window: 6,
        regressions_in_window: 0,
        regression_rate_pct: 0,
        green_streak_latest: 6,
        latest_entry_clean: true,
      },
      key_checks: {
        max_regressions_ok: true,
        max_regression_rate_ok: true,
        min_green_streak_ok: true,
        latest_entry_clean_ok: true,
      },
      thresholds: {
        max_regressions: 0,
        max_regression_rate_pct: 0,
        min_green_streak: 1,
      },
      previous_window: {
        available: false,
        regressions_in_window: 0,
        regression_rate_pct: 0,
        green_streak_latest: 0,
      },
      deltas: {
        regressions_in_window_delta: null,
        regression_rate_pct_delta: null,
        green_streak_latest_delta: null,
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
    },
  };
}

test("SLO digest heartbeat reporter appends one heartbeat in strict pass mode", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-slo-hb-pass-"));
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
  const out = parseStdoutJson(proc, "heartbeat_pass");
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

test("SLO digest heartbeat reporter deduplicates identical heartbeat ids", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-slo-hb-dedupe-"));
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

  const out2 = parseStdoutJson(proc2, "heartbeat_dedupe");
  assert.equal(out2.validation_errors.length, 0);
  assert.equal(out2.appended, false);
  assert.equal(out2.duplicate_detected, true);
  assert.equal(out2.history_size_before, 1);
  assert.equal(out2.history_size_after, 1);

  const lines = fs.readFileSync(heartbeatPath, "utf8").trim().split(/\r?\n/);
  assert.equal(lines.length, 1);
});

test("SLO digest heartbeat reporter fails strict when status is failed but still appends row", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-slo-hb-fail-"));
  const digestPath = path.join(tmpDir, "digest.json");
  const heartbeatPath = path.join(tmpDir, "heartbeat.jsonl");

  writeJson(
    digestPath,
    digestReportFixture({
      digest: {
        status: "failed",
        risk_level: "red",
        risk_reasons: ["latest_entry_not_clean"],
        strict_fail_reasons: ["latest_entry_not_clean"],
        key_metrics: {
          entries_in_window: 3,
          regressions_in_window: 1,
          regression_rate_pct: 50,
          green_streak_latest: 0,
          latest_entry_clean: false,
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
  const out = parseStdoutJson(proc, "heartbeat_fail");
  assert.equal(out.validation_errors.length, 0);
  assert.equal(out.appended, true);
  assert.equal(out.history_size_before, 0);
  assert.equal(out.history_size_after, 1);
  assert.equal(out.heartbeat.status, "failed");
  assert.equal(out.heartbeat.risk_level, "red");

  const lines = fs.readFileSync(heartbeatPath, "utf8").trim().split(/\r?\n/);
  assert.equal(lines.length, 1);
});

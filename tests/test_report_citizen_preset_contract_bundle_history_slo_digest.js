const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_preset_contract_bundle_history_slo_digest.js");
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

test("SLO digest reporter emits compact ok digest in strict mode", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-slo-digest-pass-"));
  const sloPath = path.join(tmpDir, "slo.json");

  writeJson(sloPath, {
    generated_at: "2026-02-22T00:00:00.000Z",
    risk_level: "green",
    risk_reasons: [],
    strict_fail_reasons: [],
    entries_in_window: 5,
    regressions_in_window: 0,
    regression_rate_pct: 0,
    green_streak_latest: 5,
    latest_entry_clean: true,
    thresholds: {
      max_regressions: 0,
      max_regression_rate_pct: 0,
      min_green_streak: 1,
    },
    checks: {
      max_regressions_ok: true,
      max_regression_rate_ok: true,
      min_green_streak_ok: true,
      latest_entry_clean_ok: true,
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
  });

  const proc = runReporter(["--slo-json", sloPath, "--strict"]);
  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "digest_pass");
  assert.equal(Array.isArray(out.validation_errors), true);
  assert.equal(out.validation_errors.length, 0);
  assert.equal(out.digest.status, "ok");
  assert.equal(out.digest.risk_level, "green");
  assert.equal(out.digest.key_metrics.regressions_in_window, 0);
  assert.equal(out.digest.key_metrics.latest_entry_clean, true);
});

test("SLO digest reporter fails strict mode when digest is failed", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-slo-digest-fail-"));
  const sloPath = path.join(tmpDir, "slo.json");

  writeJson(sloPath, {
    generated_at: "2026-02-22T00:10:00.000Z",
    risk_level: "red",
    risk_reasons: ["latest_entry_not_clean"],
    strict_fail_reasons: ["latest_entry_not_clean"],
    entries_in_window: 3,
    regressions_in_window: 1,
    regression_rate_pct: 50,
    green_streak_latest: 0,
    latest_entry_clean: false,
    thresholds: {
      max_regressions: 0,
      max_regression_rate_pct: 0,
      min_green_streak: 1,
    },
    checks: {
      max_regressions_ok: false,
      max_regression_rate_ok: false,
      min_green_streak_ok: false,
      latest_entry_clean_ok: false,
    },
    previous_window: {
      available: true,
      regressions_in_window: 0,
      regression_rate_pct: 0,
      green_streak_latest: 2,
    },
    deltas: {
      regressions_in_window_delta: 1,
      regression_rate_pct_delta: 50,
      green_streak_latest_delta: -2,
    },
  });

  const proc = runReporter(["--slo-json", sloPath, "--strict"]);
  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "digest_fail");
  assert.equal(Array.isArray(out.validation_errors), true);
  assert.equal(out.validation_errors.length, 0);
  assert.equal(out.digest.status, "failed");
  assert.equal(out.digest.risk_level, "red");
  assert.ok(out.digest.risk_reasons.includes("latest_entry_not_clean"));
});

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_preset_contract_bundle_history_slo.js");
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
  });
}

function parseStdoutJson(proc, label) {
  assert.equal(proc.signal, null, `${label}: process signaled`);
  assert.ok(proc.stdout && String(proc.stdout).trim(), `${label}: missing stdout JSON`);
  return JSON.parse(proc.stdout);
}

function writeHistory(absPath, entries) {
  const lines = entries.map((e) => JSON.stringify(e));
  fs.writeFileSync(absPath, `${lines.join("\n")}\n`, "utf8");
}

function cleanEntry(minuteOffset) {
  const mm = String(minuteOffset).padStart(2, "0");
  return {
    run_at: `2026-02-22T00:${mm}:00.000Z`,
    summary: { sections_fail: 0, total_fail: 0, failed_sections: [] },
    contracts: { fixture_contract_ok: true, codec_parity_ok: true, codec_sync_state_ok: true },
    sync_state: { would_change: false },
  };
}

test("history SLO reporter passes strict on clean streak with zero regressions", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-slo-pass-"));
  const historyPath = path.join(tmpDir, "history.jsonl");

  writeHistory(historyPath, [cleanEntry(0), cleanEntry(1), cleanEntry(2), cleanEntry(3)]);

  const proc = runReporter([
    "--history-jsonl",
    historyPath,
    "--last",
    "20",
    "--max-regressions",
    "0",
    "--max-regression-rate-pct",
    "0",
    "--min-green-streak",
    "3",
    "--strict",
  ]);

  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "slo_pass");

  assert.equal(out.entries_total, 4);
  assert.equal(out.regressions_in_window, 0);
  assert.equal(out.regression_rate_pct, 0);
  assert.equal(out.latest_entry_clean, true);
  assert.equal(out.green_streak_latest, 4);
  assert.equal(out.previous_window.available, false);
  assert.equal(out.deltas.regressions_in_window_delta, null);
  assert.equal(out.risk_level, "green");
  assert.equal(Array.isArray(out.risk_reasons), true);
  assert.equal(out.risk_reasons.length, 0);
  assert.equal(Array.isArray(out.strict_fail_reasons), true);
  assert.equal(out.strict_fail_reasons.length, 0);
  assert.equal(out.checks.max_regressions_ok, true);
  assert.equal(out.checks.max_regression_rate_ok, true);
  assert.equal(out.checks.min_green_streak_ok, true);
  assert.equal(out.checks.latest_entry_clean_ok, true);
});

test("history SLO reporter emits amber when current window worsens vs previous but stays under thresholds", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-slo-amber-"));
  const historyPath = path.join(tmpDir, "history.jsonl");

  writeHistory(historyPath, [
    cleanEntry(0),
    cleanEntry(1),
    cleanEntry(2),
    cleanEntry(3),
    {
      run_at: "2026-02-22T00:04:00.000Z",
      summary: { sections_fail: 1, total_fail: 1, failed_sections: ["codec_parity"] },
      contracts: { fixture_contract_ok: true, codec_parity_ok: false, codec_sync_state_ok: true },
      sync_state: { would_change: true },
    },
    cleanEntry(5),
  ]);

  const proc = runReporter([
    "--history-jsonl",
    historyPath,
    "--last",
    "3",
    "--max-regressions",
    "1",
    "--max-regression-rate-pct",
    "100",
    "--min-green-streak",
    "1",
    "--strict",
  ]);

  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "slo_amber");

  assert.equal(out.entries_in_window, 3);
  assert.equal(out.previous_window.available, true);
  assert.equal(out.previous_window.regressions_in_window, 0);
  assert.equal(out.regressions_in_window, 1);
  assert.equal(out.deltas.regressions_in_window_delta, 1);
  assert.equal(out.latest_entry_clean, true);
  assert.equal(out.green_streak_latest, 1);
  assert.equal(out.risk_level, "amber");
  assert.ok(Array.isArray(out.risk_reasons));
  assert.ok(out.risk_reasons.includes("regressions_worsened_vs_previous_window"));
  assert.equal(Array.isArray(out.strict_fail_reasons), true);
  assert.equal(out.strict_fail_reasons.length, 0);
});

test("history SLO reporter fails strict when regression and latest dirty break thresholds", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-slo-fail-"));
  const historyPath = path.join(tmpDir, "history.jsonl");

  writeHistory(historyPath, [
    cleanEntry(0),
    cleanEntry(1),
    {
      run_at: "2026-02-22T00:02:00.000Z",
      summary: { sections_fail: 2, total_fail: 2, failed_sections: ["codec_parity", "codec_sync_state"] },
      contracts: { fixture_contract_ok: true, codec_parity_ok: false, codec_sync_state_ok: false },
      sync_state: { would_change: true },
    },
  ]);

  const proc = runReporter([
    "--history-jsonl",
    historyPath,
    "--last",
    "20",
    "--max-regressions",
    "0",
    "--max-regression-rate-pct",
    "0",
    "--min-green-streak",
    "2",
    "--strict",
  ]);

  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "slo_fail");

  assert.ok(out.regressions_in_window > 0);
  assert.ok(out.regression_rate_pct > 0);
  assert.equal(out.latest_entry_clean, false);
  assert.equal(out.green_streak_latest, 0);
  assert.ok(Array.isArray(out.strict_fail_reasons));
  assert.ok(out.strict_fail_reasons.includes("max_regressions_exceeded"));
  assert.ok(out.strict_fail_reasons.includes("max_regression_rate_exceeded"));
  assert.ok(out.strict_fail_reasons.includes("min_green_streak_not_met"));
  assert.ok(out.strict_fail_reasons.includes("latest_entry_not_clean"));
  assert.equal(out.risk_level, "red");
  assert.ok(out.risk_reasons.includes("latest_entry_not_clean"));
});

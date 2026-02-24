const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_window.js");
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
  });
}

function parseStdoutJson(proc, label) {
  assert.equal(proc.signal, null, `${label}: process signaled`);
  assert.ok(proc.stdout && String(proc.stdout).trim(), `${label}: missing stdout JSON`);
  return JSON.parse(proc.stdout);
}

function writeJsonl(absPath, rows) {
  const lines = rows.map((r) => JSON.stringify(r));
  fs.writeFileSync(absPath, `${lines.join("\n")}\n`, "utf8");
}

function heartbeat(minuteOffset, overrides = {}) {
  const mm = String(minuteOffset).padStart(2, "0");
  const base = {
    run_at: `2026-02-22T00:${mm}:00.000Z`,
    heartbeat_id: `hb-${mm}`,
    status: "ok",
    risk_level: "green",
    entries_in_window: 20,
    regressions_in_window: 0,
    regression_rate_pct: 0,
    green_streak_latest: 20,
    latest_entry_clean: true,
    strict_fail_count: 0,
    risk_reason_count: 0,
    strict_fail_reasons: [],
    risk_reasons: [],
  };
  return {
    ...base,
    ...overrides,
  };
}

test("heartbeat window reporter passes strict on non-failed latest with thresholds satisfied", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-hb-window-pass-"));
  const heartbeatPath = path.join(tmpDir, "heartbeat.jsonl");

  writeJsonl(heartbeatPath, [
    heartbeat(0, { status: "ok", risk_level: "green" }),
    heartbeat(1, { status: "degraded", risk_level: "amber", risk_reason_count: 1, risk_reasons: ["trend_worsened"] }),
    heartbeat(2, { status: "ok", risk_level: "green" }),
  ]);

  const proc = runReporter([
    "--heartbeat-jsonl",
    heartbeatPath,
    "--last",
    "20",
    "--max-failed",
    "0",
    "--max-failed-rate-pct",
    "0",
    "--strict",
  ]);

  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "hb_window_pass");
  assert.equal(out.entries_total, 3);
  assert.equal(out.entries_in_window, 3);
  assert.equal(out.status_counts.ok, 2);
  assert.equal(out.status_counts.degraded, 1);
  assert.equal(out.status_counts.failed, 0);
  assert.equal(out.failed_in_window, 0);
  assert.equal(out.failed_rate_pct, 0);
  assert.equal(out.latest.status, "ok");
  assert.equal(out.strict_fail_reasons.length, 0);
  assert.equal(out.checks.latest_not_failed_ok, true);
});

test("heartbeat window reporter fails strict when failed rows exceed threshold and latest is failed", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-hb-window-fail-"));
  const heartbeatPath = path.join(tmpDir, "heartbeat.jsonl");

  writeJsonl(heartbeatPath, [
    heartbeat(0, { status: "ok", risk_level: "green" }),
    heartbeat(1, {
      status: "failed",
      risk_level: "red",
      strict_fail_count: 1,
      strict_fail_reasons: ["latest_entry_not_clean"],
      risk_reason_count: 1,
      risk_reasons: ["latest_entry_not_clean"],
    }),
    heartbeat(2, {
      status: "failed",
      risk_level: "red",
      strict_fail_count: 1,
      strict_fail_reasons: ["max_regressions_exceeded"],
      risk_reason_count: 1,
      risk_reasons: ["max_regressions_exceeded"],
    }),
  ]);

  const proc = runReporter([
    "--heartbeat-jsonl",
    heartbeatPath,
    "--last",
    "20",
    "--max-failed",
    "0",
    "--max-failed-rate-pct",
    "0",
    "--strict",
  ]);

  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "hb_window_fail");
  assert.equal(out.entries_in_window, 3);
  assert.equal(out.status_counts.failed, 2);
  assert.equal(out.failed_in_window, 2);
  assert.ok(out.failed_rate_pct > 0);
  assert.equal(out.first_failed_run_at, "2026-02-22T00:01:00.000Z");
  assert.equal(out.last_failed_run_at, "2026-02-22T00:02:00.000Z");
  assert.equal(out.first_red_risk_run_at, "2026-02-22T00:01:00.000Z");
  assert.equal(out.last_red_risk_run_at, "2026-02-22T00:02:00.000Z");
  assert.equal(out.latest.status, "failed");
  assert.equal(out.failed_streak_latest, 2);
  assert.ok(out.strict_fail_reasons.includes("max_failed_exceeded"));
  assert.ok(out.strict_fail_reasons.includes("max_failed_rate_exceeded"));
  assert.ok(out.strict_fail_reasons.includes("latest_status_failed"));
});

test("heartbeat window reporter fails strict on malformed entries", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-hb-window-malformed-"));
  const heartbeatPath = path.join(tmpDir, "heartbeat.jsonl");

  fs.writeFileSync(
    heartbeatPath,
    `${JSON.stringify(heartbeat(0))}\n{"broken_json":\n`,
    "utf8"
  );

  const proc = runReporter([
    "--heartbeat-jsonl",
    heartbeatPath,
    "--last",
    "20",
    "--max-failed",
    "1",
    "--max-failed-rate-pct",
    "100",
    "--strict",
  ]);

  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "hb_window_malformed");
  assert.equal(out.entries_total, 2);
  assert.equal(out.malformed_entries_in_window, 1);
  assert.ok(out.strict_fail_reasons.includes("malformed_entries_present"));
});

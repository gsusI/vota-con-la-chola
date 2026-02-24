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
    "report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_window.js"
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
    window_raw_entries: 20,
    raw_window_incidents: 2,
    missing_in_compacted_in_window: 0,
    incident_missing_in_compacted: 0,
    raw_window_coverage_pct: 100,
    incident_coverage_pct: 100,
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

test("compact-window digest heartbeat window reporter passes strict on all-ok/latest-ok with thresholds satisfied", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-compact-window-digest-hb-window-pass-"));
  const heartbeatPath = path.join(tmpDir, "heartbeat.jsonl");

  writeJsonl(heartbeatPath, [
    heartbeat(0, { status: "ok", risk_level: "green" }),
    heartbeat(1, { status: "ok", risk_level: "green" }),
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
    "--max-degraded",
    "0",
    "--max-degraded-rate-pct",
    "0",
    "--strict",
  ]);

  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "compact_window_digest_hb_window_pass");
  assert.equal(out.entries_total, 3);
  assert.equal(out.entries_in_window, 3);
  assert.equal(out.status_counts.ok, 3);
  assert.equal(out.status_counts.degraded, 0);
  assert.equal(out.status_counts.failed, 0);
  assert.equal(out.failed_in_window, 0);
  assert.equal(out.degraded_in_window, 0);
  assert.equal(out.latest.status, "ok");
  assert.equal(out.strict_fail_reasons.length, 0);
});

test("compact-window digest heartbeat window reporter fails strict when degraded exceeds thresholds", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-compact-window-digest-hb-window-degraded-fail-"));
  const heartbeatPath = path.join(tmpDir, "heartbeat.jsonl");

  writeJsonl(heartbeatPath, [
    heartbeat(0, { status: "ok", risk_level: "green" }),
    heartbeat(1, {
      status: "degraded",
      risk_level: "amber",
      risk_reason_count: 1,
      risk_reasons: ["non_incident_rows_missing_in_compacted_window"],
      missing_in_compacted_in_window: 1,
      raw_window_coverage_pct: 95,
    }),
    heartbeat(2, {
      status: "degraded",
      risk_level: "amber",
      risk_reason_count: 1,
      risk_reasons: ["raw_window_coverage_below_100"],
      missing_in_compacted_in_window: 1,
      raw_window_coverage_pct: 95,
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
    "--max-degraded",
    "0",
    "--max-degraded-rate-pct",
    "0",
    "--strict",
  ]);

  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "compact_window_digest_hb_window_degraded_fail");
  assert.equal(out.entries_in_window, 3);
  assert.equal(out.status_counts.degraded, 2);
  assert.equal(out.degraded_in_window, 2);
  assert.ok(out.degraded_rate_pct > 0);
  assert.equal(out.first_degraded_run_at, "2026-02-22T00:01:00.000Z");
  assert.equal(out.last_degraded_run_at, "2026-02-22T00:02:00.000Z");
  assert.ok(out.strict_fail_reasons.includes("max_degraded_exceeded"));
  assert.ok(out.strict_fail_reasons.includes("max_degraded_rate_exceeded"));
});

test("compact-window digest heartbeat window reporter fails strict on malformed entries", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-compact-window-digest-hb-window-malformed-"));
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
    "--max-degraded",
    "1",
    "--max-degraded-rate-pct",
    "100",
    "--strict",
  ]);

  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "compact_window_digest_hb_window_malformed");
  assert.equal(out.entries_total, 2);
  assert.equal(out.malformed_entries_in_window, 1);
  assert.ok(out.strict_fail_reasons.includes("malformed_entries_present"));
});

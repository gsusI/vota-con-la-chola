const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runParityReporter(args) {
  const script = path.join(
    __dirname,
    "..",
    "scripts",
    "report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window.js"
  );
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
  });
}

function runCompactionReporter(args) {
  const script = path.join(
    __dirname,
    "..",
    "scripts",
    "report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_compaction.js"
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

function heartbeat(minuteOffset, overrides = {}) {
  const mm = String(minuteOffset).padStart(2, "0");
  const base = {
    run_at: `2026-02-22T00:${mm}:00.000Z`,
    heartbeat_id: `hb-${mm}`,
    status: "ok",
    risk_level: "green",
    window_raw_entries: 20,
    raw_window_incidents: 0,
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

function writeJsonl(absPath, rows) {
  const lines = rows.map((r) => JSON.stringify(r));
  fs.writeFileSync(absPath, `${lines.join("\n")}\n`, "utf8");
}

test("compact-window digest heartbeat compaction-window parity passes strict when compacted preserves raw last-N incidents", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-cwd-hb-compaction-window-pass-"));
  const rawPath = path.join(tmpDir, "heartbeat.raw.jsonl");
  const compactedPath = path.join(tmpDir, "heartbeat.compacted.jsonl");

  writeJsonl(rawPath, [
    heartbeat(0),
    heartbeat(1),
    heartbeat(2),
    heartbeat(3, {
      status: "failed",
      risk_level: "red",
      strict_fail_count: 1,
      strict_fail_reasons: ["incident_rows_missing_in_compacted"],
      risk_reason_count: 1,
      risk_reasons: ["incident_coverage_below_100"],
    }),
    heartbeat(4, { status: "degraded", risk_level: "amber" }),
    heartbeat(5),
    heartbeat(6),
    heartbeat(7),
  ]);

  const compactProc = runCompactionReporter([
    "--heartbeat-jsonl",
    rawPath,
    "--compacted-jsonl",
    compactedPath,
    "--keep-recent",
    "5",
    "--keep-mid-span",
    "10",
    "--keep-mid-every",
    "2",
    "--keep-old-every",
    "10",
    "--strict",
  ]);
  assert.equal(compactProc.status, 0, `compaction run failed: ${compactProc.status}; stderr=${compactProc.stderr || ""}`);

  const proc = runParityReporter([
    "--heartbeat-jsonl",
    rawPath,
    "--compacted-jsonl",
    compactedPath,
    "--last",
    "5",
    "--strict",
  ]);

  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "cwd_hb_compaction_window_parity_pass");

  assert.equal(out.window_raw_entries, 5);
  assert.equal(out.missing_in_compacted_in_window, 0);
  assert.equal(out.incident_missing_in_compacted, 0);
  assert.equal(out.raw_window_failed, 1);
  assert.equal(out.failed_present_in_compacted, 1);
  assert.equal(out.raw_window_degraded, 1);
  assert.equal(out.degraded_present_in_compacted, 1);
  assert.equal(out.raw_window_red, 1);
  assert.equal(out.red_present_in_compacted, 1);
  assert.equal(out.checks.latest_present_ok, true);
  assert.equal(out.strict_fail_reasons.length, 0);
});

test("compact-window digest heartbeat compaction-window parity fails strict when compacted misses degraded incident rows", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-cwd-hb-compaction-window-degraded-fail-"));
  const rawPath = path.join(tmpDir, "heartbeat.raw.jsonl");
  const compactedPath = path.join(tmpDir, "heartbeat.compacted.jsonl");

  const rawRows = [
    heartbeat(0),
    heartbeat(1, {
      status: "degraded",
      risk_level: "amber",
      risk_reason_count: 1,
      risk_reasons: ["raw_window_coverage_below_100"],
    }),
    heartbeat(2),
    heartbeat(3),
  ];
  writeJsonl(rawPath, rawRows);

  writeJsonl(compactedPath, [rawRows[0], rawRows[2], rawRows[3]]);

  const proc = runParityReporter([
    "--heartbeat-jsonl",
    rawPath,
    "--compacted-jsonl",
    compactedPath,
    "--last",
    "4",
    "--strict",
  ]);

  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "cwd_hb_compaction_window_parity_degraded_fail");

  assert.equal(out.window_raw_entries, 4);
  assert.equal(out.incident_missing_in_compacted, 1);
  assert.equal(out.raw_window_degraded, 1);
  assert.equal(out.degraded_present_in_compacted, 0);
  assert.equal(out.checks.latest_present_ok, true);
  assert.ok(out.strict_fail_reasons.includes("incident_rows_missing_in_compacted"));
  assert.ok(out.strict_fail_reasons.includes("degraded_count_underreported_in_compacted_window"));
});

test("compact-window digest heartbeat compaction-window parity fails strict when latest raw entry is missing from compacted", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-cwd-hb-compaction-window-latest-fail-"));
  const rawPath = path.join(tmpDir, "heartbeat.raw.jsonl");
  const compactedPath = path.join(tmpDir, "heartbeat.compacted.jsonl");

  const rawRows = [
    heartbeat(0),
    heartbeat(1),
    heartbeat(2),
    heartbeat(3),
  ];
  writeJsonl(rawPath, rawRows);

  writeJsonl(compactedPath, [rawRows[0], rawRows[1], rawRows[2]]);

  const proc = runParityReporter([
    "--heartbeat-jsonl",
    rawPath,
    "--compacted-jsonl",
    compactedPath,
    "--last",
    "4",
    "--strict",
  ]);

  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "cwd_hb_compaction_window_parity_latest_fail");

  assert.equal(out.window_raw_entries, 4);
  assert.equal(out.raw_window_incidents, 0);
  assert.equal(out.incident_missing_in_compacted, 0);
  assert.equal(out.latest_raw.present_in_compacted, false);
  assert.ok(out.strict_fail_reasons.includes("latest_raw_missing_in_compacted"));
});

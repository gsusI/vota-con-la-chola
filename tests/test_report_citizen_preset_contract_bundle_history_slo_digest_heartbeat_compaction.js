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
    "report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction.js"
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
    strict_fail_count: 0,
    strict_fail_reasons: [],
    risk_reason_count: 0,
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

test("heartbeat compaction reporter keeps failed/red incident entries and writes compacted JSONL", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-hb-compaction-pass-"));
  const heartbeatPath = path.join(tmpDir, "heartbeat.jsonl");
  const compactedPath = path.join(tmpDir, "heartbeat.compacted.jsonl");

  const rows = [];
  for (let i = 0; i < 16; i += 1) {
    rows.push(heartbeat(i));
  }

  rows[3] = heartbeat(3, {
    status: "failed",
    risk_level: "red",
    strict_fail_count: 1,
    strict_fail_reasons: ["latest_entry_not_clean"],
    risk_reason_count: 1,
    risk_reasons: ["latest_entry_not_clean"],
  });

  rows[9] = heartbeat(9, {
    status: "degraded",
    risk_level: "red",
    strict_fail_count: 0,
    strict_fail_reasons: [],
    risk_reason_count: 1,
    risk_reasons: ["trend_worsened"],
  });

  writeJsonl(heartbeatPath, rows);

  const proc = runReporter([
    "--heartbeat-jsonl",
    heartbeatPath,
    "--compacted-jsonl",
    compactedPath,
    "--keep-recent",
    "2",
    "--keep-mid-span",
    "4",
    "--keep-mid-every",
    "2",
    "--keep-old-every",
    "5",
    "--min-raw-for-dropped-check",
    "5",
    "--strict",
  ]);

  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "hb_compaction_pass");

  assert.equal(out.entries_total, 16);
  assert.ok(out.selected_entries > 0);
  assert.ok(out.dropped_entries > 0);
  assert.equal(out.incidents_total, 2);
  assert.equal(out.incidents_selected, 2);
  assert.equal(out.incidents_dropped, 0);
  assert.equal(out.failed_total, 1);
  assert.equal(out.failed_selected, 1);
  assert.equal(out.red_total, 2);
  assert.equal(out.red_selected, 2);
  assert.equal(out.anchors.latest_selected, true);
  assert.equal(Array.isArray(out.strict_fail_reasons), true);
  assert.equal(out.strict_fail_reasons.length, 0);

  const incidentSample = out.selected_reasons_sample.find((x) => x.index === 3);
  assert.ok(incidentSample, "failed incident entry missing from selected sample");
  assert.ok(incidentSample.reasons.includes("incident_entry"));

  const compactedLines = fs.readFileSync(compactedPath, "utf8").trim().split(/\r?\n/);
  assert.equal(compactedLines.length, out.selected_entries);
});

test("heartbeat compaction reporter fails strict when no rows are dropped above threshold", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-hb-compaction-fail-"));
  const heartbeatPath = path.join(tmpDir, "heartbeat.jsonl");

  const rows = [];
  for (let i = 0; i < 30; i += 1) {
    rows.push(heartbeat(i));
  }
  writeJsonl(heartbeatPath, rows);

  const proc = runReporter([
    "--heartbeat-jsonl",
    heartbeatPath,
    "--keep-recent",
    "100",
    "--keep-mid-span",
    "100",
    "--keep-mid-every",
    "5",
    "--keep-old-every",
    "20",
    "--min-raw-for-dropped-check",
    "20",
    "--strict",
  ]);

  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "hb_compaction_fail");

  assert.equal(out.entries_total, 30);
  assert.equal(out.dropped_entries, 0);
  assert.ok(Array.isArray(out.strict_fail_reasons));
  assert.ok(out.strict_fail_reasons.includes("no_entries_dropped_above_threshold"));
});

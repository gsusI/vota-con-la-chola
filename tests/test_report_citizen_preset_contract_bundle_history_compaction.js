const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_preset_contract_bundle_history_compaction.js");
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
  });
}

function parseStdoutJson(proc, label) {
  assert.equal(proc.signal, null, `${label}: process signaled`);
  assert.ok(proc.stdout && String(proc.stdout).trim(), `${label}: missing stdout JSON`);
  return JSON.parse(proc.stdout);
}

function entryAt(minuteOffset, overrides = {}) {
  const minute = String(minuteOffset).padStart(2, "0");
  return {
    run_at: `2026-02-22T00:${minute}:00.000Z`,
    summary: {
      sections_fail: 0,
      total_fail: 0,
      failed_sections: [],
    },
    contracts: {
      fixture_contract_ok: true,
      codec_parity_ok: true,
      codec_sync_state_ok: true,
    },
    sync_state: {
      would_change: false,
    },
    ...overrides,
  };
}

function writeHistory(absPath, entries) {
  const lines = entries.map((e) => JSON.stringify(e));
  fs.writeFileSync(absPath, `${lines.join("\n")}\n`, "utf8");
}

test("history compaction reporter keeps incident entries and writes compacted JSONL", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-compaction-pass-"));
  const historyPath = path.join(tmpDir, "history.jsonl");
  const compactedPath = path.join(tmpDir, "history.compacted.jsonl");

  const entries = [];
  for (let i = 0; i < 12; i += 1) {
    entries.push(entryAt(i));
  }

  entries[2] = entryAt(2, {
    summary: {
      sections_fail: 1,
      total_fail: 1,
      failed_sections: ["codec_parity"],
    },
    contracts: {
      fixture_contract_ok: true,
      codec_parity_ok: false,
      codec_sync_state_ok: true,
    },
    sync_state: {
      would_change: true,
    },
  });

  writeHistory(historyPath, entries);

  const proc = runReporter([
    "--history-jsonl",
    historyPath,
    "--compacted-jsonl",
    compactedPath,
    "--keep-recent",
    "2",
    "--keep-mid-span",
    "2",
    "--keep-mid-every",
    "2",
    "--keep-old-every",
    "5",
    "--min-raw-for-dropped-check",
    "5",
    "--strict",
  ]);

  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "compaction_pass");

  assert.equal(out.entries_total, 12);
  assert.ok(out.selected_entries > 0);
  assert.ok(out.dropped_entries > 0);
  assert.equal(out.incidents_total, 1);
  assert.equal(out.incidents_selected, 1);
  assert.equal(out.incidents_dropped, 0);
  assert.equal(out.anchors.latest_selected, true);
  assert.equal(out.anchors.oldest_selected, true);
  assert.equal(Array.isArray(out.strict_fail_reasons), true);
  assert.equal(out.strict_fail_reasons.length, 0);

  const incidentSample = out.selected_reasons_sample.find((x) => x.index === 2);
  assert.ok(incidentSample, "incident entry missing from selected sample");
  assert.ok(incidentSample.reasons.includes("incident_entry"));

  const compactedLines = fs.readFileSync(compactedPath, "utf8").trim().split(/\r?\n/);
  assert.equal(compactedLines.length, out.selected_entries);
});

test("history compaction reporter fails strict when compaction does not drop rows above threshold", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-compaction-fail-"));
  const historyPath = path.join(tmpDir, "history.jsonl");

  const entries = [];
  for (let i = 0; i < 30; i += 1) {
    entries.push(entryAt(i));
  }
  writeHistory(historyPath, entries);

  const proc = runReporter([
    "--history-jsonl",
    historyPath,
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
  const out = parseStdoutJson(proc, "compaction_fail");

  assert.equal(out.entries_total, 30);
  assert.equal(out.dropped_entries, 0);
  assert.ok(Array.isArray(out.strict_fail_reasons));
  assert.ok(out.strict_fail_reasons.includes("no_entries_dropped_above_threshold"));
});

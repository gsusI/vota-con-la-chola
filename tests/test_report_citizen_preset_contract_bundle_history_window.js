const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_preset_contract_bundle_history_window.js");
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

test("bundle history window reporter passes strict when window has no regressions", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-window-pass-"));
  const historyPath = path.join(tmpDir, "history.jsonl");

  writeHistory(historyPath, [
    {
      run_at: "2026-02-22T00:00:00.000Z",
      summary: { sections_fail: 0, total_fail: 0, failed_sections: [] },
      contracts: { fixture_contract_ok: true, codec_parity_ok: true, codec_sync_state_ok: true },
      sync_state: { would_change: false },
    },
    {
      run_at: "2026-02-22T00:05:00.000Z",
      summary: { sections_fail: 0, total_fail: 0, failed_sections: [] },
      contracts: { fixture_contract_ok: true, codec_parity_ok: true, codec_sync_state_ok: true },
      sync_state: { would_change: false },
    },
  ]);

  const proc = runReporter(["--history-jsonl", historyPath, "--last", "20", "--strict"]);
  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "window_pass");
  assert.equal(out.entries_total, 2);
  assert.equal(out.entries_in_window, 2);
  assert.equal(out.regressions_in_window, 0);
  assert.equal(Array.isArray(out.regression_events), true);
  assert.equal(out.regression_events.length, 0);
  assert.equal(out.latest_entry.sections_fail, 0);
});

test("bundle history window reporter fails strict when window contains regressions", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-window-fail-"));
  const historyPath = path.join(tmpDir, "history.jsonl");

  writeHistory(historyPath, [
    {
      run_at: "2026-02-22T00:00:00.000Z",
      summary: { sections_fail: 0, total_fail: 0, failed_sections: [] },
      contracts: { fixture_contract_ok: true, codec_parity_ok: true, codec_sync_state_ok: true },
      sync_state: { would_change: false },
    },
    {
      run_at: "2026-02-22T00:10:00.000Z",
      summary: { sections_fail: 2, total_fail: 2, failed_sections: ["codec_parity", "codec_sync_state"] },
      contracts: { fixture_contract_ok: true, codec_parity_ok: false, codec_sync_state_ok: false },
      sync_state: { would_change: true },
    },
  ]);

  const proc = runReporter(["--history-jsonl", historyPath, "--last", "20", "--strict"]);
  assert.equal(proc.status, 1, `expected strict failure; got ${proc.status}; stderr=${proc.stderr || ""}`);

  const out = parseStdoutJson(proc, "window_fail");
  assert.equal(out.entries_total, 2);
  assert.equal(out.entries_in_window, 2);
  assert.ok(out.regressions_in_window > 0);
  assert.ok(Array.isArray(out.regression_events));
  assert.ok(out.regression_events[0].reasons.some((x) => String(x || "").includes("sections_fail_increase")));
  assert.ok(out.regression_events[0].reasons.some((x) => String(x || "").includes("sync_would_change_regressed")));
});

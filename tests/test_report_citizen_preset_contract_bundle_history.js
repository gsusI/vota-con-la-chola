const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_preset_contract_bundle_history.js");
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

function buildBundleFixture(overrides = {}) {
  return {
    generated_at: "2026-02-22T00:00:00.000Z",
    summary: {
      sections_total: 3,
      sections_pass: 3,
      sections_fail: 0,
      failed_sections: [],
      total_cases: 14,
      total_pass: 14,
      total_fail: 0,
      failed_ids: [],
    },
    contracts: {
      fixture_contract: { ok: true, summary: { total_fail: 0 } },
      codec_parity: { ok: true, summary: { total_fail: 0 } },
      codec_sync_state: { ok: true, summary: { total_fail: 0 } },
    },
    reports: {
      codec_sync_state: {
        results: [{ would_change: false }],
      },
    },
    ...overrides,
  };
}

test("preset contract bundle history reporter appends baseline without regression", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-history-pass-"));
  const bundlePath = path.join(tmpDir, "bundle.json");
  const historyPath = path.join(tmpDir, "history.jsonl");

  writeJson(bundlePath, buildBundleFixture());
  const proc = runReporter(["--bundle-json", bundlePath, "--history-jsonl", historyPath, "--strict"]);

  assert.equal(proc.status, 0, `unexpected exit status: ${proc.status}; stderr=${proc.stderr || ""}`);
  const out = parseStdoutJson(proc, "history_baseline");
  assert.equal(out.regression_detected, false);
  assert.equal(out.history_size_before, 0);
  assert.equal(out.history_size_after, 1);
  assert.equal(Array.isArray(out.regression_reasons), true);
  assert.equal(out.regression_reasons.length, 0);

  const lines = fs.readFileSync(historyPath, "utf8").trim().split(/\r?\n/);
  assert.equal(lines.length, 1);
});

test("preset contract bundle history reporter fails strict on regression", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "preset-bundle-history-fail-"));
  const historyPath = path.join(tmpDir, "history.jsonl");

  const bundlePath1 = path.join(tmpDir, "bundle1.json");
  writeJson(bundlePath1, buildBundleFixture());
  const proc1 = runReporter(["--bundle-json", bundlePath1, "--history-jsonl", historyPath, "--strict"]);
  assert.equal(proc1.status, 0, `baseline run failed: ${proc1.status}; stderr=${proc1.stderr || ""}`);

  const bundlePath2 = path.join(tmpDir, "bundle2.json");
  writeJson(
    bundlePath2,
    buildBundleFixture({
      generated_at: "2026-02-22T00:10:00.000Z",
      summary: {
        sections_total: 3,
        sections_pass: 1,
        sections_fail: 2,
        failed_sections: ["codec_parity", "codec_sync_state"],
        total_cases: 14,
        total_pass: 12,
        total_fail: 2,
        failed_ids: ["codec_parity:source_vs_published", "codec_sync_state:source_to_published"],
      },
      contracts: {
        fixture_contract: { ok: true, summary: { total_fail: 0 } },
        codec_parity: { ok: false, summary: { total_fail: 1 } },
        codec_sync_state: { ok: false, summary: { total_fail: 1 } },
      },
      reports: {
        codec_sync_state: {
          results: [{ would_change: true }],
        },
      },
    })
  );

  const proc2 = runReporter(["--bundle-json", bundlePath2, "--history-jsonl", historyPath, "--strict"]);
  assert.equal(proc2.status, 1, `expected strict failure; got ${proc2.status}; stderr=${proc2.stderr || ""}`);

  const out = parseStdoutJson(proc2, "history_regression");
  assert.equal(out.regression_detected, true);
  assert.ok(Array.isArray(out.regression_reasons));
  assert.ok(out.regression_reasons.some((x) => String(x || "").includes("sections_fail_increase")));
  assert.ok(out.regression_reasons.some((x) => String(x || "").includes("contract_degraded:codec_parity_ok")));
  assert.ok(out.regression_reasons.some((x) => String(x || "").includes("sync_would_change_regressed")));
  assert.equal(out.history_size_before, 1);
  assert.equal(out.history_size_after, 2);

  const lines = fs.readFileSync(historyPath, "utf8").trim().split(/\r?\n/);
  assert.equal(lines.length, 2);
});

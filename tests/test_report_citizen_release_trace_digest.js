const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runReporter(args) {
  const script = path.join(__dirname, "..", "scripts", "report_citizen_release_trace_digest.js");
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
  });
}

function parseJsonFile(filePath, label) {
  assert.equal(fs.existsSync(filePath), true, `${label}: missing json output file`);
  const raw = fs.readFileSync(filePath, "utf8");
  assert.ok(String(raw || "").trim().length > 0, `${label}: empty json output file`);
  return JSON.parse(raw);
}

function writeJson(filePath, obj) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(obj, null, 2)}\n`, "utf8");
}

function releaseFixture({ generatedAt, ready, totalFail, failedIds }) {
  return {
    generated_at: generatedAt,
    summary: {
      total_checks: 30,
      total_pass: ready && totalFail === 0 ? 30 : 29,
      total_fail: totalFail,
      failed_ids: failedIds || [],
    },
    readiness: {
      status: ready ? "ok" : "failed",
      release_ready: Boolean(ready),
      parity_ok_assets: ready ? 9 : 8,
      parity_total_assets: 9,
      parity_failed_assets: ready ? [] : ["index.html"],
    },
    results: [
      {
        section: "snapshot",
        id: "shape",
        ok: true,
        as_of_date: "2026-02-16",
        topics_total: 111,
        parties_total: 16,
        party_topic_positions_total: 1776,
        has_meta_quality: true,
      },
    ],
  };
}

test("release-trace digest passes strict complete when release hardening is fresh and ready", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "citizen-release-trace-pass-"));
  const source = path.join(tmpDir, "release_hardening.json");
  const out = path.join(tmpDir, "digest.json");
  writeJson(
    source,
    releaseFixture({
      generatedAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      ready: true,
      totalFail: 0,
      failedIds: [],
    }),
  );

  const proc = runReporter([
    "--release-hardening-json",
    source,
    "--max-age-minutes",
    "60",
    "--json-out",
    out,
    "--strict",
    "--strict-require-complete",
  ]);
  assert.equal(proc.status, 0, `unexpected status=${proc.status}; stderr=${proc.stderr || ""}`);

  const digest = parseJsonFile(out, "release_trace_digest_pass");
  assert.equal(digest.status, "ok");
  assert.equal(Boolean(digest.checks.contract_complete), true);
  assert.equal(Boolean(digest.checks.freshness_within_sla), true);
  assert.equal(digest.release_trace.release_total_fail, 0);
  assert.equal(digest.release_trace.parity_ok_assets, 9);
});

test("release-trace digest degrades on stale release and strict-complete fails", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "citizen-release-trace-stale-"));
  const source = path.join(tmpDir, "release_hardening_stale.json");
  const out = path.join(tmpDir, "digest_stale.json");
  writeJson(
    source,
    releaseFixture({
      generatedAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
      ready: true,
      totalFail: 0,
      failedIds: [],
    }),
  );

  const proc = runReporter([
    "--release-hardening-json",
    source,
    "--max-age-minutes",
    "60",
    "--json-out",
    out,
    "--strict",
    "--strict-require-complete",
  ]);
  assert.equal(proc.status, 4, `expected strict complete failure; status=${proc.status}; stderr=${proc.stderr || ""}`);

  const digest = parseJsonFile(out, "release_trace_digest_stale");
  assert.equal(digest.status, "degraded");
  assert.equal(Boolean(digest.checks.release_ready), true);
  assert.equal(Boolean(digest.checks.freshness_within_sla), false);
  assert.ok((digest.degraded_reasons || []).includes("release_trace_stale"));
});

test("release-trace digest fails strict when release hardening is not ready", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "citizen-release-trace-fail-"));
  const source = path.join(tmpDir, "release_hardening_fail.json");
  const out = path.join(tmpDir, "digest_fail.json");
  writeJson(
    source,
    releaseFixture({
      generatedAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      ready: false,
      totalFail: 1,
      failedIds: ["snapshot:shape"],
    }),
  );

  const proc = runReporter([
    "--release-hardening-json",
    source,
    "--max-age-minutes",
    "60",
    "--json-out",
    out,
    "--strict",
  ]);
  assert.equal(proc.status, 4, `expected strict failure; status=${proc.status}; stderr=${proc.stderr || ""}`);

  const digest = parseJsonFile(out, "release_trace_digest_fail");
  assert.equal(digest.status, "failed");
  assert.equal(Boolean(digest.checks.release_ready), false);
  assert.equal(Boolean(digest.checks.release_no_failures), false);
  assert.ok((digest.failure_reasons || []).includes("release_not_ready"));
  assert.ok((digest.failure_reasons || []).includes("release_failures_present"));
});

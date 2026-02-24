#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require("node:fs");
const path = require("node:path");

function nowIsoUtc() {
  return new Date().toISOString();
}

function usage() {
  return [
    "Usage:",
    "  node scripts/report_citizen_release_trace_digest.js [options]",
    "",
    "Options:",
    "  --release-hardening-json <path>  Release hardening JSON source",
    "                                   (default: docs/etl/sprints/AI-OPS-81/evidence/citizen_release_hardening_latest.json)",
    "  --max-age-minutes <int>          Freshness SLA in minutes (default: 360)",
    "  --json-out <path>                Optional JSON output file",
    "  --strict                         Exit 4 when status is failed",
    "  --strict-require-complete        With --strict, also fail when status is degraded",
    "  --help                           Show this help",
  ].join("\n");
}

function parseArgs(argv) {
  const out = {
    releaseHardeningJson: "docs/etl/sprints/AI-OPS-81/evidence/citizen_release_hardening_latest.json",
    maxAgeMinutes: 360,
    jsonOut: "",
    strict: false,
    strictRequireComplete: false,
    help: false,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const a = String(argv[i] || "");
    if (a === "--help" || a === "-h") {
      out.help = true;
      continue;
    }
    if (a === "--strict") {
      out.strict = true;
      continue;
    }
    if (a === "--strict-require-complete") {
      out.strictRequireComplete = true;
      continue;
    }
    if (a === "--release-hardening-json") {
      out.releaseHardeningJson = String(argv[i + 1] || "");
      i += 1;
      continue;
    }
    if (a === "--max-age-minutes") {
      out.maxAgeMinutes = Number(argv[i + 1] || 0);
      i += 1;
      continue;
    }
    if (a === "--json-out") {
      out.jsonOut = String(argv[i + 1] || "");
      i += 1;
      continue;
    }
    throw new Error(`Unknown argument: ${a}`);
  }

  if (!Number.isFinite(out.maxAgeMinutes) || out.maxAgeMinutes <= 0) {
    throw new Error("--max-age-minutes must be > 0");
  }
  return out;
}

function ensureParentDir(filePath) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
}

function parseIsoMs(v) {
  const s = String(v || "").trim();
  if (!s) return null;
  const ms = Date.parse(s);
  if (!Number.isFinite(ms)) return null;
  return ms;
}

function asObject(v) {
  if (!v || typeof v !== "object" || Array.isArray(v)) return {};
  return v;
}

function asArray(v) {
  return Array.isArray(v) ? v : [];
}

function asNum(v, fallback = 0) {
  const n = Number(v);
  if (!Number.isFinite(n)) return Number(fallback);
  return n;
}

function asBool(v) {
  return Boolean(v);
}

function extractSnapshotShape(results) {
  const rows = asArray(results);
  for (const row of rows) {
    const section = String((row || {}).section || "");
    const id = String((row || {}).id || "");
    if (section === "snapshot" && id === "shape") {
      return {
        as_of_date: String((row || {}).as_of_date || ""),
        topics_total: asNum((row || {}).topics_total, 0),
        parties_total: asNum((row || {}).parties_total, 0),
        party_topic_positions_total: asNum((row || {}).party_topic_positions_total, 0),
        has_meta_quality: asBool((row || {}).has_meta_quality),
      };
    }
  }
  return {
    as_of_date: "",
    topics_total: 0,
    parties_total: 0,
    party_topic_positions_total: 0,
    has_meta_quality: false,
  };
}

function buildDigest(input, sourcePath, maxAgeMinutes) {
  const release = asObject(input);
  const summary = asObject(release.summary);
  const readiness = asObject(release.readiness);
  const snapshotShape = extractSnapshotShape(release.results);
  const generatedAt = String(release.generated_at || "").trim();
  const generatedAtMs = parseIsoMs(generatedAt);
  const nowMs = Date.now();
  const ageMinutes = generatedAtMs == null ? null : Number(((nowMs - generatedAtMs) / 60000).toFixed(3));

  const totalChecks = asNum(summary.total_checks, 0);
  const totalFail = asNum(summary.total_fail, 0);
  const releaseReady = asBool(readiness.release_ready);
  const parityOkAssets = asNum(readiness.parity_ok_assets, 0);
  const parityTotalAssets = asNum(readiness.parity_total_assets, 0);
  const failedIds = asArray(summary.failed_ids).map((x) => String(x || ""));
  const parityFailedAssets = asArray(readiness.parity_failed_assets).map((x) => String(x || ""));

  const checks = {
    release_generated_at_present: generatedAtMs != null,
    release_checks_present: totalChecks > 0,
    release_no_failures: totalFail === 0,
    release_ready: releaseReady,
    freshness_within_sla: ageMinutes != null && ageMinutes <= Number(maxAgeMinutes),
    parity_assets_complete: parityTotalAssets > 0 && parityOkAssets === parityTotalAssets,
  };
  checks.contract_complete = Boolean(
    checks.release_generated_at_present &&
      checks.release_checks_present &&
      checks.release_no_failures &&
      checks.release_ready &&
      checks.freshness_within_sla &&
      checks.parity_assets_complete,
  );

  const degradedReasons = [];
  const failureReasons = [];

  if (!checks.release_generated_at_present) failureReasons.push("release_generated_at_missing_or_invalid");
  if (!checks.release_checks_present) failureReasons.push("release_checks_missing");
  if (!checks.release_no_failures) failureReasons.push("release_failures_present");
  if (!checks.release_ready) failureReasons.push("release_not_ready");
  if (!checks.parity_assets_complete) failureReasons.push("release_parity_incomplete");
  if (!checks.freshness_within_sla) degradedReasons.push("release_trace_stale");

  let status = "ok";
  if (failureReasons.length) status = "failed";
  else if (degradedReasons.length) status = "degraded";

  return {
    generated_at: nowIsoUtc(),
    status,
    paths: {
      release_hardening_json: sourcePath,
    },
    release_trace: {
      release_generated_at: generatedAt || null,
      release_age_minutes: ageMinutes,
      release_ready: releaseReady,
      release_readiness_status: String(readiness.status || "").trim() || null,
      release_total_checks: totalChecks,
      release_total_fail: totalFail,
      release_failed_ids_total: failedIds.length,
      parity_ok_assets: parityOkAssets,
      parity_total_assets: parityTotalAssets,
      parity_failed_assets_total: parityFailedAssets.length,
      snapshot_as_of_date: snapshotShape.as_of_date || null,
      snapshot_topics_total: snapshotShape.topics_total,
      snapshot_parties_total: snapshotShape.parties_total,
      snapshot_party_topic_positions_total: snapshotShape.party_topic_positions_total,
      snapshot_has_meta_quality: snapshotShape.has_meta_quality,
    },
    thresholds: {
      max_age_minutes: Number(maxAgeMinutes),
    },
    checks,
    degraded_reasons: Array.from(new Set(degradedReasons)),
    failure_reasons: Array.from(new Set(failureReasons)),
    failed_ids: failedIds,
    parity_failed_assets: parityFailedAssets,
  };
}

function main() {
  let args;
  try {
    args = parseArgs(process.argv);
  } catch (err) {
    console.error(String((err && err.message) || err || "invalid arguments"));
    console.error(usage());
    process.exit(2);
  }

  if (args.help) {
    console.log(usage());
    process.exit(0);
  }

  const sourcePath = path.resolve(String(args.releaseHardeningJson || "").trim());
  if (!fs.existsSync(sourcePath)) {
    console.log(JSON.stringify({ error: `release-hardening-json not found: ${sourcePath}` }, null, 2));
    process.exit(2);
  }

  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(sourcePath, "utf8"));
  } catch (err) {
    console.log(
      JSON.stringify(
        {
          error: "release-hardening-json parse error",
          detail: String((err && err.message) || err || "json_parse_error"),
        },
        null,
        2,
      ),
    );
    process.exit(3);
  }

  let digest;
  try {
    digest = buildDigest(parsed, sourcePath, Number(args.maxAgeMinutes));
  } catch (err) {
    console.log(
      JSON.stringify(
        {
          error: "release-trace digest runtime error",
          detail: String((err && err.message) || err || "runtime_error"),
        },
        null,
        2,
      ),
    );
    process.exit(3);
  }

  const payload = JSON.stringify(digest, null, 2);
  console.log(payload);

  if (args.jsonOut) {
    const outPath = path.resolve(String(args.jsonOut).trim());
    ensureParentDir(outPath);
    fs.writeFileSync(outPath, `${payload}\n`, "utf8");
  }

  if (args.strict) {
    if (digest.status === "failed") process.exit(4);
    if (args.strictRequireComplete && digest.status !== "ok") process.exit(4);
  }
}

main();

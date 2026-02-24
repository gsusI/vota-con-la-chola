#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require("node:fs");
const path = require("node:path");

function isoUtcNow() {
  return new Date().toISOString();
}

function usage() {
  return [
    "Usage:",
    "  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest.js [options]",
    "",
    "Options:",
    "  --compaction-window-json <path>  Input heartbeat compaction-window report JSON path (required)",
    "  --json-out <path>                Optional output file for digest JSON",
    "  --strict                         Exit non-zero when digest status is failed or input is invalid",
    "  --help                           Show this help",
  ].join("\n");
}

function toString(v) {
  return String(v == null ? "" : v);
}

function toBool(v) {
  return Boolean(v);
}

function toInt(v) {
  if (typeof v === "number" && Number.isFinite(v)) return Math.trunc(v);
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}

function toFloat(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function safeObj(v) {
  return v && typeof v === "object" ? v : {};
}

function safeArray(v) {
  return Array.isArray(v) ? v : [];
}

function ensureParentDir(filePath) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
}

function parseArgs(argv) {
  const out = {
    compactionWindowJson: "",
    jsonOut: "",
    strict: false,
    help: false,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const a = toString(argv[i]);
    if (a === "--help" || a === "-h") {
      out.help = true;
      continue;
    }
    if (a === "--strict") {
      out.strict = true;
      continue;
    }
    if (a === "--compaction-window-json") {
      out.compactionWindowJson = toString(argv[i + 1]);
      i += 1;
      continue;
    }
    if (a === "--json-out") {
      out.jsonOut = toString(argv[i + 1]);
      i += 1;
      continue;
    }
    throw new Error(`Unknown argument: ${a}`);
  }

  if (!out.help && !toString(out.compactionWindowJson).trim()) {
    throw new Error("Missing required argument: --compaction-window-json <path>");
  }

  return out;
}

function readJson(absPath) {
  return JSON.parse(fs.readFileSync(absPath, "utf8"));
}

function normalizeRiskLevel(raw) {
  const risk = toString(raw).trim().toLowerCase();
  if (risk === "green" || risk === "amber" || risk === "red") return risk;
  return "red";
}

function determineStatus(parity, strictFails, riskReasons) {
  if (strictFails.length > 0) return "failed";
  if (toInt(parity.missing_in_compacted_in_window) > 0) return "degraded";
  if (riskReasons.length > 0) return "degraded";
  return "ok";
}

function determineRiskLevel(status) {
  if (status === "failed") return "red";
  if (status === "degraded") return "amber";
  return "green";
}

function buildDigest(parity, parityPath, strict) {
  const checks = safeObj(parity.checks);
  const strictFailReasons = safeArray(parity.strict_fail_reasons).map((x) => toString(x)).filter(Boolean);

  const riskReasons = [];
  const missingAny = toInt(parity.missing_in_compacted_in_window) > 0;
  const missingIncident = toInt(parity.incident_missing_in_compacted) > 0;
  const coveragePct = toFloat(parity.raw_window_coverage_pct);
  const incidentCoveragePct = toFloat(parity.incident_coverage_pct);

  if (!missingIncident && missingAny) {
    riskReasons.push("non_incident_rows_missing_in_compacted_window");
  }
  if (!missingIncident && missingAny && coveragePct < 100) {
    riskReasons.push("raw_window_coverage_below_100");
  }
  if (toInt(parity.raw_window_incidents) > 0 && incidentCoveragePct < 100) {
    riskReasons.push("incident_coverage_below_100");
  }

  const status = determineStatus(parity, strictFailReasons, riskReasons);
  const riskLevel = determineRiskLevel(status);

  return {
    generated_at: isoUtcNow(),
    strict: toBool(strict),
    input: {
      compaction_window_json_path: parityPath,
      compaction_window_generated_at: toString(parity.generated_at),
      heartbeat_path: toString(parity.heartbeat_path),
      compacted_path: toString(parity.compacted_path),
    },
    status,
    risk_level: normalizeRiskLevel(riskLevel),
    risk_reasons: riskReasons,
    strict_fail_reasons: strictFailReasons,
    strict_fail_count: strictFailReasons.length,
    risk_reason_count: riskReasons.length,
    key_metrics: {
      entries_total_raw: toInt(parity.entries_total_raw),
      entries_total_compacted: toInt(parity.entries_total_compacted),
      window_raw_entries: toInt(parity.window_raw_entries),
      raw_window_incidents: toInt(parity.raw_window_incidents),
      present_in_compacted_in_window: toInt(parity.present_in_compacted_in_window),
      missing_in_compacted_in_window: toInt(parity.missing_in_compacted_in_window),
      incident_missing_in_compacted: toInt(parity.incident_missing_in_compacted),
      raw_window_coverage_pct: coveragePct,
      incident_coverage_pct: incidentCoveragePct,
    },
    key_checks: {
      window_nonempty_ok: toBool(checks.window_nonempty_ok),
      raw_window_malformed_ok: toBool(checks.raw_window_malformed_ok),
      compacted_malformed_ok: toBool(checks.compacted_malformed_ok),
      latest_present_ok: toBool(checks.latest_present_ok),
      incident_parity_ok: toBool(checks.incident_parity_ok),
      failed_parity_ok: toBool(checks.failed_parity_ok),
      red_parity_ok: toBool(checks.red_parity_ok),
    },
    thresholds: {
      max_missing_in_compacted_window_for_ok: 0,
      min_raw_window_coverage_pct_for_ok: 100,
      min_incident_coverage_pct_for_ok: 100,
    },
  };
}

function validateDigest(digest) {
  const reasons = [];

  if (!toString(safeObj(digest.input).compaction_window_generated_at)) {
    reasons.push("missing_compaction_window_generated_at");
  }

  const status = toString(digest.status);
  if (!["ok", "degraded", "failed"].includes(status)) {
    reasons.push("invalid_status");
  }

  const risk = toString(digest.risk_level);
  if (!["green", "amber", "red"].includes(risk)) {
    reasons.push("invalid_risk_level");
  }

  const metrics = safeObj(digest.key_metrics);
  if (toInt(metrics.entries_total_raw) < 0) reasons.push("invalid_entries_total_raw");
  if (toInt(metrics.entries_total_compacted) < 0) reasons.push("invalid_entries_total_compacted");
  if (toInt(metrics.window_raw_entries) < 0) reasons.push("invalid_window_raw_entries");
  if (toInt(metrics.raw_window_incidents) < 0) reasons.push("invalid_raw_window_incidents");
  if (toInt(metrics.present_in_compacted_in_window) < 0) reasons.push("invalid_present_in_compacted_in_window");
  if (toInt(metrics.missing_in_compacted_in_window) < 0) reasons.push("invalid_missing_in_compacted_in_window");
  if (toInt(metrics.incident_missing_in_compacted) < 0) reasons.push("invalid_incident_missing_in_compacted");
  if (toFloat(metrics.raw_window_coverage_pct) < 0) reasons.push("invalid_raw_window_coverage_pct");
  if (toFloat(metrics.incident_coverage_pct) < 0) reasons.push("invalid_incident_coverage_pct");

  if (toInt(metrics.window_raw_entries) !== toInt(metrics.present_in_compacted_in_window) + toInt(metrics.missing_in_compacted_in_window)) {
    reasons.push("window_presence_count_mismatch");
  }

  if (toInt(digest.strict_fail_count) !== safeArray(digest.strict_fail_reasons).length) {
    reasons.push("strict_fail_count_mismatch");
  }
  if (toInt(digest.risk_reason_count) !== safeArray(digest.risk_reasons).length) {
    reasons.push("risk_reason_count_mismatch");
  }

  return reasons;
}

function main() {
  let args;
  try {
    args = parseArgs(process.argv);
  } catch (err) {
    console.error(toString((err && err.message) || err || "invalid arguments"));
    console.error(usage());
    process.exit(2);
  }

  if (args.help) {
    console.log(usage());
    process.exit(0);
  }

  const parityPath = path.resolve(args.compactionWindowJson);
  const report = {
    generated_at: isoUtcNow(),
    strict: toBool(args.strict),
    input_path: parityPath,
    digest: {},
    validation_errors: [],
  };

  try {
    const parity = readJson(parityPath);
    const digest = buildDigest(parity, parityPath, args.strict);
    report.digest = digest;
    report.validation_errors = validateDigest(digest);
  } catch (err) {
    report.validation_errors = [
      `runtime_error:${toString((err && err.message) || err || "unknown_error")}`,
    ];
  }

  const serialized = JSON.stringify(report, null, 2);
  console.log(serialized);

  if (args.jsonOut) {
    const outPath = path.resolve(args.jsonOut);
    ensureParentDir(outPath);
    fs.writeFileSync(outPath, `${serialized}\n`, "utf8");
  }

  const status = toString(safeObj(report.digest).status);
  if (args.strict && (report.validation_errors.length > 0 || status === "failed")) {
    process.exit(1);
  }
}

main();

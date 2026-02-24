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
    "  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.js [options]",
    "",
    "Options:",
    "  --digest-json <path>      Input compact-window digest report JSON path (required)",
    "  --heartbeat-jsonl <path>  NDJSON heartbeat history path (default: docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.jsonl)",
    "  --json-out <path>         Optional output file for heartbeat append report JSON",
    "  --strict                  Exit non-zero on invalid heartbeat or failed status",
    "  --help                    Show this help",
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
    digestJson: "",
    heartbeatJsonl:
      "docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.jsonl",
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
    if (a === "--digest-json") {
      out.digestJson = toString(argv[i + 1]);
      i += 1;
      continue;
    }
    if (a === "--heartbeat-jsonl") {
      out.heartbeatJsonl = toString(argv[i + 1]);
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

  if (!out.help && !toString(out.digestJson).trim()) {
    throw new Error("Missing required argument: --digest-json <path>");
  }

  return out;
}

function readJson(absPath) {
  return JSON.parse(fs.readFileSync(absPath, "utf8"));
}

function readHistoryEntries(historyPath) {
  if (!fs.existsSync(historyPath)) return [];
  const raw = fs.readFileSync(historyPath, "utf8");
  const lines = raw.split(/\r?\n/).filter((line) => line.trim().length > 0);
  const out = [];

  for (const line of lines) {
    try {
      out.push(JSON.parse(line));
    } catch (_err) {
      out.push({
        malformed_line: true,
      });
    }
  }

  return out;
}

function normalizeStatus(raw) {
  const status = toString(raw).trim().toLowerCase();
  if (status === "ok" || status === "degraded" || status === "failed") return status;
  return "failed";
}

function normalizeRisk(raw) {
  const risk = toString(raw).trim().toLowerCase();
  if (risk === "green" || risk === "amber" || risk === "red") return risk;
  return "red";
}

function buildHeartbeat(digestReport, digestPath) {
  const digest = safeObj(digestReport.digest);
  const input = safeObj(digest.input);
  const keyMetrics = safeObj(digest.key_metrics);

  const riskReasons = safeArray(digest.risk_reasons).map((x) => toString(x)).filter(Boolean);
  const strictFailReasons = safeArray(digest.strict_fail_reasons).map((x) => toString(x)).filter(Boolean);

  const runAt = toString(digest.generated_at) || toString(digestReport.generated_at) || isoUtcNow();
  const status = normalizeStatus(digest.status);
  const riskLevel = normalizeRisk(digest.risk_level);
  const heartbeatId = [
    toString(input.compaction_window_generated_at),
    runAt,
    status,
    riskLevel,
    String(toInt(keyMetrics.missing_in_compacted_in_window)),
    String(toInt(keyMetrics.window_raw_entries)),
  ].join("|");

  return {
    run_at: runAt,
    heartbeat_id: heartbeatId,
    digest_path: digestPath,
    digest_generated_at: toString(digest.generated_at),
    compaction_window_generated_at: toString(input.compaction_window_generated_at),
    status,
    risk_level: riskLevel,
    window_raw_entries: toInt(keyMetrics.window_raw_entries),
    raw_window_incidents: toInt(keyMetrics.raw_window_incidents),
    missing_in_compacted_in_window: toInt(keyMetrics.missing_in_compacted_in_window),
    incident_missing_in_compacted: toInt(keyMetrics.incident_missing_in_compacted),
    raw_window_coverage_pct: toFloat(keyMetrics.raw_window_coverage_pct),
    incident_coverage_pct: toFloat(keyMetrics.incident_coverage_pct),
    strict_fail_count: strictFailReasons.length,
    risk_reason_count: riskReasons.length,
    strict_fail_reasons: strictFailReasons,
    risk_reasons: riskReasons,
  };
}

function validateHeartbeat(heartbeat) {
  const reasons = [];

  if (!toString(heartbeat.run_at)) {
    reasons.push("missing_run_at");
  }
  if (!toString(heartbeat.heartbeat_id)) {
    reasons.push("missing_heartbeat_id");
  }
  if (!toString(heartbeat.compaction_window_generated_at)) {
    reasons.push("missing_compaction_window_generated_at");
  }

  const status = toString(heartbeat.status);
  if (!["ok", "degraded", "failed"].includes(status)) {
    reasons.push("invalid_status");
  }

  const risk = toString(heartbeat.risk_level);
  if (!["green", "amber", "red"].includes(risk)) {
    reasons.push("invalid_risk_level");
  }

  if (toInt(heartbeat.window_raw_entries) < 0) reasons.push("invalid_window_raw_entries");
  if (toInt(heartbeat.raw_window_incidents) < 0) reasons.push("invalid_raw_window_incidents");
  if (toInt(heartbeat.missing_in_compacted_in_window) < 0) reasons.push("invalid_missing_in_compacted_in_window");
  if (toInt(heartbeat.incident_missing_in_compacted) < 0) reasons.push("invalid_incident_missing_in_compacted");
  if (toFloat(heartbeat.raw_window_coverage_pct) < 0) reasons.push("invalid_raw_window_coverage_pct");
  if (toFloat(heartbeat.incident_coverage_pct) < 0) reasons.push("invalid_incident_coverage_pct");

  const strictFailReasons = safeArray(heartbeat.strict_fail_reasons);
  const riskReasons = safeArray(heartbeat.risk_reasons);
  if (strictFailReasons.length !== toInt(heartbeat.strict_fail_count)) {
    reasons.push("strict_fail_count_mismatch");
  }
  if (riskReasons.length !== toInt(heartbeat.risk_reason_count)) {
    reasons.push("risk_reason_count_mismatch");
  }

  return reasons;
}

function historyHasHeartbeat(entries, heartbeatId) {
  for (const row of entries) {
    if (!row || row.malformed_line) continue;
    if (toString(row.heartbeat_id) === toString(heartbeatId)) return true;
  }
  return false;
}

function appendHeartbeat(historyPath, heartbeat) {
  ensureParentDir(historyPath);
  fs.appendFileSync(historyPath, `${JSON.stringify(heartbeat)}\n`, "utf8");
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

  const digestPath = path.resolve(args.digestJson);
  const heartbeatPath = path.resolve(args.heartbeatJsonl);
  const report = {
    generated_at: isoUtcNow(),
    strict: toBool(args.strict),
    input_path: digestPath,
    heartbeat_path: heartbeatPath,
    history_size_before: 0,
    history_size_after: 0,
    appended: false,
    duplicate_detected: false,
    validation_errors: [],
    heartbeat: {},
  };

  try {
    const digestReport = readJson(digestPath);
    const heartbeat = buildHeartbeat(digestReport, digestPath);
    report.heartbeat = heartbeat;
    report.validation_errors = validateHeartbeat(heartbeat);

    const historyBefore = readHistoryEntries(heartbeatPath);
    report.history_size_before = historyBefore.length;

    if (report.validation_errors.length === 0) {
      report.duplicate_detected = historyHasHeartbeat(historyBefore, heartbeat.heartbeat_id);
      if (!report.duplicate_detected) {
        appendHeartbeat(heartbeatPath, heartbeat);
        report.appended = true;
      }
    }

    report.history_size_after = report.history_size_before + (report.appended ? 1 : 0);
  } catch (err) {
    report.validation_errors = [
      `runtime_error:${toString((err && err.message) || err || "unknown_error")}`,
    ];
    report.history_size_after = report.history_size_before;
  }

  const serialized = JSON.stringify(report, null, 2);
  console.log(serialized);

  if (args.jsonOut) {
    const outPath = path.resolve(args.jsonOut);
    ensureParentDir(outPath);
    fs.writeFileSync(outPath, `${serialized}\n`, "utf8");
  }

  const status = toString(safeObj(report.heartbeat).status);
  if (args.strict && (report.validation_errors.length > 0 || status === "failed")) {
    process.exit(1);
  }
}

main();

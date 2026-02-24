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
    "  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat_window.js [options]",
    "",
    "Options:",
    "  --heartbeat-jsonl <path>       Heartbeat JSONL path (default: docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.jsonl)",
    "  --last <n>                     Number of trailing heartbeat rows to inspect (default: 20)",
    "  --max-failed <n>               Max allowed failed rows in window (default: 0)",
    "  --max-failed-rate-pct <n>      Max allowed failed rate pct in window (default: 0)",
    "  --max-degraded <n>             Max allowed degraded rows in window (default: 0)",
    "  --max-degraded-rate-pct <n>    Max allowed degraded rate pct in window (default: 0)",
    "  --json-out <path>              Optional output file for JSON report",
    "  --strict                       Exit non-zero when checks fail",
    "  --help                         Show this help",
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

function round4(n) {
  return Math.round(Number(n || 0) * 10000) / 10000;
}

function safeObj(v) {
  return v && typeof v === "object" ? v : {};
}

function ensureParentDir(filePath) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
}

function parsePositiveInt(raw, name) {
  const n = toInt(raw);
  if (!Number.isFinite(n) || n < 1) {
    throw new Error(`${name} must be >= 1`);
  }
  return n;
}

function parseNonNegativeInt(raw, name) {
  const n = toInt(raw);
  if (!Number.isFinite(n) || n < 0) {
    throw new Error(`${name} must be >= 0`);
  }
  return n;
}

function parseNonNegativeFloat(raw, name) {
  const n = toFloat(raw);
  if (!Number.isFinite(n) || n < 0) {
    throw new Error(`${name} must be >= 0`);
  }
  return n;
}

function parseArgs(argv) {
  const out = {
    heartbeatJsonl:
      "docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window_digest_heartbeat.jsonl",
    last: 20,
    maxFailed: 0,
    maxFailedRatePct: 0,
    maxDegraded: 0,
    maxDegradedRatePct: 0,
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
    if (a === "--heartbeat-jsonl") {
      out.heartbeatJsonl = toString(argv[i + 1]);
      i += 1;
      continue;
    }
    if (a === "--last") {
      out.last = parsePositiveInt(argv[i + 1], "--last");
      i += 1;
      continue;
    }
    if (a === "--max-failed") {
      out.maxFailed = parseNonNegativeInt(argv[i + 1], "--max-failed");
      i += 1;
      continue;
    }
    if (a === "--max-failed-rate-pct") {
      out.maxFailedRatePct = parseNonNegativeFloat(argv[i + 1], "--max-failed-rate-pct");
      i += 1;
      continue;
    }
    if (a === "--max-degraded") {
      out.maxDegraded = parseNonNegativeInt(argv[i + 1], "--max-degraded");
      i += 1;
      continue;
    }
    if (a === "--max-degraded-rate-pct") {
      out.maxDegradedRatePct = parseNonNegativeFloat(argv[i + 1], "--max-degraded-rate-pct");
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

  if (!toString(out.heartbeatJsonl).trim()) {
    throw new Error("--heartbeat-jsonl must not be empty");
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

function readHeartbeatRows(heartbeatPath) {
  if (!fs.existsSync(heartbeatPath)) return [];
  const raw = fs.readFileSync(heartbeatPath, "utf8");
  const lines = raw.split(/\r?\n/).filter((line) => line.trim().length > 0);
  const out = [];

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    try {
      out.push({
        line_no: i + 1,
        malformed_line: false,
        entry: JSON.parse(line),
      });
    } catch (_err) {
      out.push({
        line_no: i + 1,
        malformed_line: true,
        entry: {},
      });
    }
  }

  return out;
}

function computeLatestStatusStreak(rows, statusWanted) {
  let streak = 0;
  const wanted = normalizeStatus(statusWanted);
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const row = rows[i];
    if (!row || row.malformed_line) break;
    if (normalizeStatus(safeObj(row.entry).status) === wanted) {
      streak += 1;
      continue;
    }
    break;
  }
  return streak;
}

function summarizeLatest(row) {
  if (!row || row.malformed_line) {
    return {
      run_at: "",
      heartbeat_id: "",
      status: "failed",
      risk_level: "red",
      line_no: toInt(row && row.line_no),
      malformed_line: true,
    };
  }

  const entry = safeObj(row.entry);
  return {
    run_at: toString(entry.run_at),
    heartbeat_id: toString(entry.heartbeat_id),
    status: normalizeStatus(entry.status),
    risk_level: normalizeRisk(entry.risk_level),
    line_no: toInt(row.line_no),
    malformed_line: false,
  };
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

  const heartbeatPath = path.resolve(args.heartbeatJsonl);
  const report = {
    generated_at: isoUtcNow(),
    strict: toBool(args.strict),
    heartbeat_path: heartbeatPath,
    window_last: toInt(args.last),
    thresholds: {
      max_failed: toInt(args.maxFailed),
      max_failed_rate_pct: toFloat(args.maxFailedRatePct),
      max_degraded: toInt(args.maxDegraded),
      max_degraded_rate_pct: toFloat(args.maxDegradedRatePct),
    },
    entries_total: 0,
    entries_in_window: 0,
    malformed_entries_in_window: 0,
    status_counts: {
      ok: 0,
      degraded: 0,
      failed: 0,
    },
    risk_level_counts: {
      green: 0,
      amber: 0,
      red: 0,
    },
    failed_in_window: 0,
    degraded_in_window: 0,
    failed_rate_pct: 0,
    degraded_rate_pct: 0,
    first_failed_run_at: "",
    last_failed_run_at: "",
    first_degraded_run_at: "",
    last_degraded_run_at: "",
    first_red_risk_run_at: "",
    last_red_risk_run_at: "",
    latest: {},
    failed_streak_latest: 0,
    degraded_streak_latest: 0,
    checks: {
      window_nonempty_ok: false,
      malformed_entries_ok: false,
      max_failed_ok: false,
      max_failed_rate_ok: false,
      max_degraded_ok: false,
      max_degraded_rate_ok: false,
      latest_not_failed_ok: false,
    },
    strict_fail_reasons: [],
  };

  try {
    const rows = readHeartbeatRows(heartbeatPath);
    report.entries_total = rows.length;
    const windowRows = rows.slice(Math.max(0, rows.length - toInt(args.last)));
    report.entries_in_window = windowRows.length;
    report.malformed_entries_in_window = windowRows.filter((r) => r.malformed_line).length;

    for (const row of windowRows) {
      if (row.malformed_line) continue;
      const entry = safeObj(row.entry);
      const status = normalizeStatus(entry.status);
      const risk = normalizeRisk(entry.risk_level);
      const runAt = toString(entry.run_at);

      report.status_counts[status] += 1;
      report.risk_level_counts[risk] += 1;

      if (status === "failed") {
        if (!report.first_failed_run_at) report.first_failed_run_at = runAt;
        report.last_failed_run_at = runAt;
      }
      if (status === "degraded") {
        if (!report.first_degraded_run_at) report.first_degraded_run_at = runAt;
        report.last_degraded_run_at = runAt;
      }
      if (risk === "red") {
        if (!report.first_red_risk_run_at) report.first_red_risk_run_at = runAt;
        report.last_red_risk_run_at = runAt;
      }
    }

    report.failed_in_window = toInt(report.status_counts.failed);
    report.degraded_in_window = toInt(report.status_counts.degraded);

    if (report.entries_in_window > 0) {
      report.failed_rate_pct = round4((report.failed_in_window / report.entries_in_window) * 100);
      report.degraded_rate_pct = round4((report.degraded_in_window / report.entries_in_window) * 100);
      report.latest = summarizeLatest(windowRows[windowRows.length - 1]);
      report.failed_streak_latest = computeLatestStatusStreak(windowRows, "failed");
      report.degraded_streak_latest = computeLatestStatusStreak(windowRows, "degraded");
    }

    report.checks.window_nonempty_ok = report.entries_in_window > 0;
    report.checks.malformed_entries_ok = report.malformed_entries_in_window === 0;
    report.checks.max_failed_ok = report.failed_in_window <= toInt(args.maxFailed);
    report.checks.max_failed_rate_ok = report.failed_rate_pct <= toFloat(args.maxFailedRatePct);
    report.checks.max_degraded_ok = report.degraded_in_window <= toInt(args.maxDegraded);
    report.checks.max_degraded_rate_ok = report.degraded_rate_pct <= toFloat(args.maxDegradedRatePct);
    report.checks.latest_not_failed_ok =
      report.entries_in_window > 0 && !toBool(safeObj(report.latest).malformed_line) && toString(safeObj(report.latest).status) !== "failed";
  } catch (err) {
    report.strict_fail_reasons.push(`runtime_error:${toString((err && err.message) || err || "unknown_error")}`);
  }

  if (!toBool(report.checks.window_nonempty_ok)) {
    report.strict_fail_reasons.push("empty_window");
  }
  if (!toBool(report.checks.malformed_entries_ok)) {
    report.strict_fail_reasons.push("malformed_entries_present");
  }
  if (!toBool(report.checks.max_failed_ok)) {
    report.strict_fail_reasons.push("max_failed_exceeded");
  }
  if (!toBool(report.checks.max_failed_rate_ok)) {
    report.strict_fail_reasons.push("max_failed_rate_exceeded");
  }
  if (!toBool(report.checks.max_degraded_ok)) {
    report.strict_fail_reasons.push("max_degraded_exceeded");
  }
  if (!toBool(report.checks.max_degraded_rate_ok)) {
    report.strict_fail_reasons.push("max_degraded_rate_exceeded");
  }
  if (!toBool(report.checks.latest_not_failed_ok)) {
    report.strict_fail_reasons.push("latest_status_failed");
  }

  const serialized = JSON.stringify(report, null, 2);
  console.log(serialized);

  if (args.jsonOut) {
    const outPath = path.resolve(args.jsonOut);
    ensureParentDir(outPath);
    fs.writeFileSync(outPath, `${serialized}\n`, "utf8");
  }

  if (args.strict && report.strict_fail_reasons.length > 0) {
    process.exit(1);
  }
}

main();

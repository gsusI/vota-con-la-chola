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
    "  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction_window.js [options]",
    "",
    "Options:",
    "  --heartbeat-jsonl <path>   Raw heartbeat JSONL path (default: docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat.jsonl)",
    "  --compacted-jsonl <path>   Compacted heartbeat JSONL path (default: docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat.compacted.jsonl)",
    "  --last <n>                 Number of trailing raw heartbeat rows to compare (default: 20)",
    "  --json-out <path>          Optional output file for JSON report",
    "  --strict                   Exit non-zero when parity checks fail",
    "  --help                     Show this help",
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

function parseArgs(argv) {
  const out = {
    heartbeatJsonl: "docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat.jsonl",
    compactedJsonl: "docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat.compacted.jsonl",
    last: 20,
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
    if (a === "--compacted-jsonl") {
      out.compactedJsonl = toString(argv[i + 1]);
      i += 1;
      continue;
    }
    if (a === "--last") {
      out.last = parsePositiveInt(argv[i + 1], "--last");
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
  if (!toString(out.compactedJsonl).trim()) {
    throw new Error("--compacted-jsonl must not be empty");
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

function safeArray(v) {
  return Array.isArray(v) ? v : [];
}

function readHeartbeatRows(heartbeatPath) {
  if (!fs.existsSync(heartbeatPath)) return [];
  const raw = fs.readFileSync(heartbeatPath, "utf8");
  const lines = raw.split(/\r?\n/).filter((line) => line.trim().length > 0);
  const rows = [];

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    try {
      rows.push({
        line_no: i + 1,
        malformed_line: false,
        entry: JSON.parse(line),
      });
    } catch (_err) {
      rows.push({
        line_no: i + 1,
        malformed_line: true,
        entry: {},
      });
    }
  }

  return rows;
}

function toRef(row) {
  const entry = safeObj(row.entry);
  const heartbeatId = toString(entry.heartbeat_id).trim();
  const runAt = toString(entry.run_at).trim();
  const lineNo = toInt(row.line_no);

  return {
    line_no: lineNo,
    malformed_line: toBool(row.malformed_line),
    heartbeat_id: heartbeatId,
    run_at: runAt,
    status: normalizeStatus(entry.status),
    risk_level: normalizeRisk(entry.risk_level),
    strict_fail_count: toInt(entry.strict_fail_count),
    strict_fail_reasons: safeArray(entry.strict_fail_reasons).map((x) => toString(x)).filter(Boolean),
    id: heartbeatId || runAt || `line:${lineNo}`,
  };
}

function hasIncident(ref) {
  if (ref.malformed_line) return true;
  if (ref.status === "failed") return true;
  if (ref.risk_level === "red") return true;
  if (toInt(ref.strict_fail_count) > 0) return true;
  if (safeArray(ref.strict_fail_reasons).length > 0) return true;
  return false;
}

function buildCompactedIndex(refs) {
  const heartbeatIds = new Set();
  const runAts = new Set();

  for (const ref of refs) {
    if (toString(ref.heartbeat_id)) heartbeatIds.add(toString(ref.heartbeat_id));
    if (toString(ref.run_at)) runAts.add(toString(ref.run_at));
  }

  return {
    heartbeatIds,
    runAts,
  };
}

function presentInCompacted(ref, idx) {
  if (toString(ref.heartbeat_id)) {
    return idx.heartbeatIds.has(toString(ref.heartbeat_id));
  }
  if (toString(ref.run_at)) {
    return idx.runAts.has(toString(ref.run_at));
  }
  return false;
}

function sampleRef(ref, present) {
  return {
    id: toString(ref.id),
    heartbeat_id: toString(ref.heartbeat_id),
    run_at: toString(ref.run_at),
    line_no: toInt(ref.line_no),
    status: toString(ref.status),
    risk_level: toString(ref.risk_level),
    malformed_line: toBool(ref.malformed_line),
    present_in_compacted: toBool(present),
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

  const rawPath = path.resolve(args.heartbeatJsonl);
  const compactedPath = path.resolve(args.compactedJsonl);

  const report = {
    generated_at: isoUtcNow(),
    strict: toBool(args.strict),
    heartbeat_path: rawPath,
    compacted_path: compactedPath,
    window_last: toInt(args.last),
    entries_total_raw: 0,
    entries_total_compacted: 0,
    window_raw_entries: 0,
    window_raw_malformed_entries: 0,
    compacted_malformed_entries: 0,
    raw_window_status_counts: {
      ok: 0,
      degraded: 0,
      failed: 0,
    },
    raw_window_risk_level_counts: {
      green: 0,
      amber: 0,
      red: 0,
    },
    raw_window_incidents: 0,
    raw_window_failed: 0,
    raw_window_red: 0,
    present_in_compacted_in_window: 0,
    missing_in_compacted_in_window: 0,
    incident_present_in_compacted: 0,
    incident_missing_in_compacted: 0,
    failed_present_in_compacted: 0,
    red_present_in_compacted: 0,
    raw_window_coverage_pct: 0,
    incident_coverage_pct: 0,
    latest_raw: {},
    missing_raw_ids_sample: [],
    missing_incident_ids_sample: [],
    checks: {
      window_nonempty_ok: false,
      raw_window_malformed_ok: false,
      compacted_malformed_ok: false,
      latest_present_ok: false,
      incident_parity_ok: false,
      failed_parity_ok: false,
      red_parity_ok: false,
    },
    strict_fail_reasons: [],
  };

  try {
    const rawRows = readHeartbeatRows(rawPath);
    const compactedRows = readHeartbeatRows(compactedPath);

    report.entries_total_raw = rawRows.length;
    report.entries_total_compacted = compactedRows.length;
    report.compacted_malformed_entries = compactedRows.filter((r) => r.malformed_line).length;

    const rawWindowRows = rawRows.slice(Math.max(0, rawRows.length - toInt(args.last)));
    const rawWindowRefs = rawWindowRows.map(toRef);
    const compactedRefs = compactedRows.map(toRef);
    const compactedIdx = buildCompactedIndex(compactedRefs);

    report.window_raw_entries = rawWindowRefs.length;
    report.window_raw_malformed_entries = rawWindowRefs.filter((ref) => ref.malformed_line).length;

    for (const ref of rawWindowRefs) {
      const incident = hasIncident(ref);
      const present = presentInCompacted(ref, compactedIdx);

      report.raw_window_status_counts[ref.status] += 1;
      report.raw_window_risk_level_counts[ref.risk_level] += 1;

      if (incident) report.raw_window_incidents += 1;
      if (ref.status === "failed") report.raw_window_failed += 1;
      if (ref.risk_level === "red") report.raw_window_red += 1;

      if (present) {
        report.present_in_compacted_in_window += 1;
        if (incident) report.incident_present_in_compacted += 1;
        if (ref.status === "failed") report.failed_present_in_compacted += 1;
        if (ref.risk_level === "red") report.red_present_in_compacted += 1;
      } else {
        report.missing_in_compacted_in_window += 1;
        if (report.missing_raw_ids_sample.length < 20) {
          report.missing_raw_ids_sample.push(sampleRef(ref, false));
        }
        if (incident) {
          report.incident_missing_in_compacted += 1;
          if (report.missing_incident_ids_sample.length < 20) {
            report.missing_incident_ids_sample.push(sampleRef(ref, false));
          }
        }
      }
    }

    if (report.window_raw_entries > 0) {
      report.raw_window_coverage_pct = round4((report.present_in_compacted_in_window / report.window_raw_entries) * 100);
    }
    if (report.raw_window_incidents > 0) {
      report.incident_coverage_pct = round4((report.incident_present_in_compacted / report.raw_window_incidents) * 100);
    }

    const latestRawRef = rawWindowRefs.length > 0 ? rawWindowRefs[rawWindowRefs.length - 1] : null;
    const latestPresent = latestRawRef ? presentInCompacted(latestRawRef, compactedIdx) : false;
    report.latest_raw = latestRawRef
      ? {
          ...sampleRef(latestRawRef, latestPresent),
        }
      : {
          id: "",
          heartbeat_id: "",
          run_at: "",
          line_no: 0,
          status: "failed",
          risk_level: "red",
          malformed_line: false,
          present_in_compacted: false,
        };

    report.checks.window_nonempty_ok = report.window_raw_entries > 0;
    report.checks.raw_window_malformed_ok = report.window_raw_malformed_entries === 0;
    report.checks.compacted_malformed_ok = report.compacted_malformed_entries === 0;
    report.checks.latest_present_ok = latestRawRef ? latestPresent : false;
    report.checks.incident_parity_ok = report.incident_missing_in_compacted === 0;
    report.checks.failed_parity_ok = report.failed_present_in_compacted === report.raw_window_failed;
    report.checks.red_parity_ok = report.red_present_in_compacted === report.raw_window_red;
  } catch (err) {
    report.strict_fail_reasons.push(`runtime_error:${toString((err && err.message) || err || "unknown_error")}`);
  }

  if (!toBool(report.checks.window_nonempty_ok)) {
    report.strict_fail_reasons.push("empty_raw_window");
  }
  if (!toBool(report.checks.raw_window_malformed_ok)) {
    report.strict_fail_reasons.push("raw_window_malformed_entries_present");
  }
  if (!toBool(report.checks.compacted_malformed_ok)) {
    report.strict_fail_reasons.push("compacted_malformed_entries_present");
  }
  if (!toBool(report.checks.latest_present_ok)) {
    report.strict_fail_reasons.push("latest_raw_missing_in_compacted");
  }
  if (!toBool(report.checks.incident_parity_ok)) {
    report.strict_fail_reasons.push("incident_rows_missing_in_compacted");
  }
  if (!toBool(report.checks.failed_parity_ok)) {
    report.strict_fail_reasons.push("failed_count_underreported_in_compacted_window");
  }
  if (!toBool(report.checks.red_parity_ok)) {
    report.strict_fail_reasons.push("red_count_underreported_in_compacted_window");
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

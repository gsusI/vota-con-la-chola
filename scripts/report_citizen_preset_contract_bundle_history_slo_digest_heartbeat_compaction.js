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
    "  node scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat_compaction.js [options]",
    "",
    "Options:",
    "  --heartbeat-jsonl <path>         Heartbeat JSONL path (default: docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat.jsonl)",
    "  --compacted-jsonl <path>         Optional output path for compacted heartbeat JSONL",
    "  --keep-recent <n>                Keep every entry for most recent window (default: 20)",
    "  --keep-mid-span <n>              Width of mid window after recent window (default: 100)",
    "  --keep-mid-every <n>             Keep every Nth entry in mid window (default: 5)",
    "  --keep-old-every <n>             Keep every Nth entry in old window (default: 20)",
    "  --min-raw-for-dropped-check <n>  Strict check: require at least one dropped entry when raw >= N (default: 25)",
    "  --json-out <path>                Optional output path for JSON report",
    "  --strict                         Exit non-zero when strict checks fail",
    "  --help                           Show this help",
  ].join("\n");
}

function toInt(v) {
  if (typeof v === "number" && Number.isFinite(v)) return Math.trunc(v);
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}

function toString(v) {
  return String(v == null ? "" : v);
}

function toBool(v) {
  return Boolean(v);
}

function safeObj(v) {
  return v && typeof v === "object" ? v : {};
}

function round4(n) {
  return Math.round(Number(n || 0) * 10000) / 10000;
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

function parseArgs(argv) {
  const out = {
    heartbeatJsonl: "docs/etl/runs/citizen_preset_contract_bundle_history_slo_digest_heartbeat.jsonl",
    compactedJsonl: "",
    keepRecent: 20,
    keepMidSpan: 100,
    keepMidEvery: 5,
    keepOldEvery: 20,
    minRawForDroppedCheck: 25,
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
    if (a === "--keep-recent") {
      out.keepRecent = parsePositiveInt(argv[i + 1], "--keep-recent");
      i += 1;
      continue;
    }
    if (a === "--keep-mid-span") {
      out.keepMidSpan = parseNonNegativeInt(argv[i + 1], "--keep-mid-span");
      i += 1;
      continue;
    }
    if (a === "--keep-mid-every") {
      out.keepMidEvery = parsePositiveInt(argv[i + 1], "--keep-mid-every");
      i += 1;
      continue;
    }
    if (a === "--keep-old-every") {
      out.keepOldEvery = parsePositiveInt(argv[i + 1], "--keep-old-every");
      i += 1;
      continue;
    }
    if (a === "--min-raw-for-dropped-check") {
      out.minRawForDroppedCheck = parseNonNegativeInt(argv[i + 1], "--min-raw-for-dropped-check");
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
        raw_line: line,
        malformed_line: false,
        entry: JSON.parse(line),
      });
    } catch (_err) {
      rows.push({
        line_no: i + 1,
        raw_line: line,
        malformed_line: true,
        entry: {},
      });
    }
  }

  return rows;
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

function tierForAge(age, args) {
  if (age < args.keepRecent) return "recent";
  if (age < args.keepRecent + args.keepMidSpan) return "mid";
  return "old";
}

function cadenceMatches(age, args) {
  const tier = tierForAge(age, args);
  if (tier === "recent") return true;
  if (tier === "mid") return age % args.keepMidEvery === 0;
  return age % args.keepOldEvery === 0;
}

function hasIncident(row) {
  if (!row || row.malformed_line) return true;
  const entry = safeObj(row.entry);

  if (normalizeStatus(entry.status) === "failed") return true;
  if (normalizeRisk(entry.risk_level) === "red") return true;

  if (toInt(entry.strict_fail_count) > 0) return true;
  if (Array.isArray(entry.strict_fail_reasons) && entry.strict_fail_reasons.length > 0) return true;

  return false;
}

function buildSelection(rows, args) {
  const n = rows.length;
  const selected = new Set();
  const reasonsByIndex = new Map();

  for (let i = 0; i < n; i += 1) {
    const row = rows[i];
    const age = n - 1 - i;
    const reasons = [];

    if (i === 0) reasons.push("anchor_oldest");
    if (i === n - 1) reasons.push("anchor_latest");
    if (row.malformed_line) reasons.push("malformed_line");
    if (hasIncident(row)) reasons.push("incident_entry");

    if (cadenceMatches(age, args)) {
      reasons.push(`cadence_${tierForAge(age, args)}`);
    }

    if (reasons.length > 0) {
      selected.add(i);
      reasonsByIndex.set(i, reasons);
    }
  }

  return {
    selected,
    reasonsByIndex,
  };
}

function summarizeRows(rows, selection, args) {
  const n = rows.length;
  const tiers = {
    recent: { raw_entries: 0, selected_entries: 0, cadence_every: 1 },
    mid: { raw_entries: 0, selected_entries: 0, cadence_every: args.keepMidEvery },
    old: { raw_entries: 0, selected_entries: 0, cadence_every: args.keepOldEvery },
  };

  let malformedTotal = 0;
  let malformedSelected = 0;
  let incidentsTotal = 0;
  let incidentsSelected = 0;
  let failedTotal = 0;
  let failedSelected = 0;
  let redTotal = 0;
  let redSelected = 0;

  const selectedRows = [];

  for (let i = 0; i < n; i += 1) {
    const row = rows[i];
    const entry = safeObj(row.entry);
    const status = normalizeStatus(entry.status);
    const risk = normalizeRisk(entry.risk_level);
    const age = n - 1 - i;
    const tier = tierForAge(age, args);
    const selected = selection.selected.has(i);
    const incident = hasIncident(row);

    tiers[tier].raw_entries += 1;
    if (selected) {
      tiers[tier].selected_entries += 1;
      selectedRows.push({ index: i, row });
    }

    if (row.malformed_line) {
      malformedTotal += 1;
      if (selected) malformedSelected += 1;
    }

    if (status === "failed") {
      failedTotal += 1;
      if (selected) failedSelected += 1;
    }

    if (risk === "red") {
      redTotal += 1;
      if (selected) redSelected += 1;
    }

    if (incident) {
      incidentsTotal += 1;
      if (selected) incidentsSelected += 1;
    }
  }

  const selectedIndicesSample = selectedRows.slice(0, 20).map((x) => x.index);
  const selectedReasonsSample = selectedRows.slice(0, 20).map((x) => {
    const reasons = selection.reasonsByIndex.get(x.index) || [];
    return {
      index: x.index,
      line_no: toInt(safeObj(x.row).line_no),
      run_at: toString(safeObj(safeObj(x.row).entry).run_at),
      status: normalizeStatus(safeObj(safeObj(x.row).entry).status),
      risk_level: normalizeRisk(safeObj(safeObj(x.row).entry).risk_level),
      reasons,
    };
  });

  const firstRunAt = n > 0 ? toString(safeObj(rows[0]).entry.run_at) : "";
  const lastRunAt = n > 0 ? toString(safeObj(rows[n - 1]).entry.run_at) : "";
  const selectedFirstRunAt = selectedRows.length > 0 ? toString(safeObj(selectedRows[0].row.entry).run_at) : "";
  const selectedLastRunAt = selectedRows.length > 0 ? toString(safeObj(selectedRows[selectedRows.length - 1].row.entry).run_at) : "";

  return {
    tiers,
    malformedTotal,
    malformedSelected,
    incidentsTotal,
    incidentsSelected,
    failedTotal,
    failedSelected,
    redTotal,
    redSelected,
    selectedRows,
    selectedIndicesSample,
    selectedReasonsSample,
    firstRunAt,
    lastRunAt,
    selectedFirstRunAt,
    selectedLastRunAt,
  };
}

function strictChecks(report, args) {
  const reasons = [];

  if (toInt(report.entries_total) === 0) {
    reasons.push("empty_history");
  }
  if (toInt(report.selected_entries) === 0) {
    reasons.push("empty_selection");
  }
  if (!toBool(safeObj(report.anchors).latest_selected)) {
    reasons.push("latest_not_selected");
  }
  if (toInt(report.incidents_dropped) > 0) {
    reasons.push("incident_entries_dropped");
  }
  if (
    toInt(report.entries_total) >= args.minRawForDroppedCheck &&
    toInt(report.dropped_entries) === 0
  ) {
    reasons.push("no_entries_dropped_above_threshold");
  }

  return reasons;
}

function writeCompactedJsonl(absPath, selectedRows) {
  ensureParentDir(absPath);
  const lines = selectedRows.map((x) => x.row.raw_line);
  const body = lines.length > 0 ? `${lines.join("\n")}\n` : "";
  fs.writeFileSync(absPath, body, "utf8");
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
  const compactedPath = args.compactedJsonl ? path.resolve(args.compactedJsonl) : "";

  const report = {
    generated_at: isoUtcNow(),
    strict: toBool(args.strict),
    heartbeat_path: heartbeatPath,
    compacted_path: compactedPath,
    policy: {
      keep_recent: toInt(args.keepRecent),
      keep_mid_span: toInt(args.keepMidSpan),
      keep_mid_every: toInt(args.keepMidEvery),
      keep_old_every: toInt(args.keepOldEvery),
      min_raw_for_dropped_check: toInt(args.minRawForDroppedCheck),
    },
    entries_total: 0,
    selected_entries: 0,
    dropped_entries: 0,
    selected_ratio: 0,
    malformed_total: 0,
    malformed_selected: 0,
    malformed_dropped: 0,
    incidents_total: 0,
    incidents_selected: 0,
    incidents_dropped: 0,
    failed_total: 0,
    failed_selected: 0,
    red_total: 0,
    red_selected: 0,
    tiers: {
      recent: { raw_entries: 0, selected_entries: 0, cadence_every: 1 },
      mid: { raw_entries: 0, selected_entries: 0, cadence_every: toInt(args.keepMidEvery) },
      old: { raw_entries: 0, selected_entries: 0, cadence_every: toInt(args.keepOldEvery) },
    },
    anchors: {
      oldest_selected: false,
      latest_selected: false,
    },
    first_run_at: "",
    last_run_at: "",
    selected_first_run_at: "",
    selected_last_run_at: "",
    selected_indices_sample: [],
    selected_reasons_sample: [],
    strict_fail_reasons: [],
  };

  try {
    const rows = readHeartbeatRows(heartbeatPath);
    const selection = buildSelection(rows, args);
    const summary = summarizeRows(rows, selection, args);

    report.entries_total = rows.length;
    report.selected_entries = summary.selectedRows.length;
    report.dropped_entries = Math.max(0, report.entries_total - report.selected_entries);
    report.selected_ratio = report.entries_total > 0 ? round4(report.selected_entries / report.entries_total) : 0;

    report.malformed_total = summary.malformedTotal;
    report.malformed_selected = summary.malformedSelected;
    report.malformed_dropped = Math.max(0, summary.malformedTotal - summary.malformedSelected);

    report.incidents_total = summary.incidentsTotal;
    report.incidents_selected = summary.incidentsSelected;
    report.incidents_dropped = Math.max(0, summary.incidentsTotal - summary.incidentsSelected);

    report.failed_total = summary.failedTotal;
    report.failed_selected = summary.failedSelected;
    report.red_total = summary.redTotal;
    report.red_selected = summary.redSelected;

    report.tiers = summary.tiers;
    report.anchors.oldest_selected = selection.selected.has(0);
    report.anchors.latest_selected = selection.selected.has(Math.max(0, rows.length - 1));

    report.first_run_at = summary.firstRunAt;
    report.last_run_at = summary.lastRunAt;
    report.selected_first_run_at = summary.selectedFirstRunAt;
    report.selected_last_run_at = summary.selectedLastRunAt;

    report.selected_indices_sample = summary.selectedIndicesSample;
    report.selected_reasons_sample = summary.selectedReasonsSample;

    if (compactedPath) {
      writeCompactedJsonl(compactedPath, summary.selectedRows);
    }
  } catch (err) {
    report.strict_fail_reasons.push(`runtime_error:${toString((err && err.message) || err || "unknown_error")}`);
  }

  report.strict_fail_reasons = [
    ...report.strict_fail_reasons,
    ...strictChecks(report, args),
  ];

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

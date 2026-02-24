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
    "  node scripts/report_citizen_preset_contract_bundle_history_slo.js [options]",
    "",
    "Options:",
    "  --history-jsonl <path>                History JSONL path (default: docs/etl/runs/citizen_preset_contract_bundle_history.jsonl)",
    "  --last <n>                            Number of trailing entries to inspect (default: 20)",
    "  --max-regressions <n>                 SLO threshold for regressions in window (default: 0)",
    "  --max-regression-rate-pct <n>         SLO threshold for regression rate pct (default: 0)",
    "  --min-green-streak <n>                SLO threshold for latest clean streak length (default: 1)",
    "  --json-out <path>                     Optional output file for JSON report",
    "  --strict                              Exit non-zero when SLO checks fail",
    "  --help                                Show this help",
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

function safeArray(v) {
  return Array.isArray(v) ? v : [];
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
    historyJsonl: "docs/etl/runs/citizen_preset_contract_bundle_history.jsonl",
    last: 20,
    maxRegressions: 0,
    maxRegressionRatePct: 0,
    minGreenStreak: 1,
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
    if (a === "--history-jsonl") {
      out.historyJsonl = toString(argv[i + 1]);
      i += 1;
      continue;
    }
    if (a === "--last") {
      out.last = parsePositiveInt(argv[i + 1], "--last");
      i += 1;
      continue;
    }
    if (a === "--max-regressions") {
      out.maxRegressions = parseNonNegativeInt(argv[i + 1], "--max-regressions");
      i += 1;
      continue;
    }
    if (a === "--max-regression-rate-pct") {
      out.maxRegressionRatePct = parseNonNegativeFloat(argv[i + 1], "--max-regression-rate-pct");
      i += 1;
      continue;
    }
    if (a === "--min-green-streak") {
      out.minGreenStreak = parsePositiveInt(argv[i + 1], "--min-green-streak");
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

  if (!toString(out.historyJsonl).trim()) {
    throw new Error("--history-jsonl must not be empty");
  }

  return out;
}

function readHistoryRows(historyPath) {
  if (!fs.existsSync(historyPath)) return [];
  const raw = fs.readFileSync(historyPath, "utf8");
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

function entryClean(row) {
  if (!row || row.malformed_line) return false;

  const entry = safeObj(row.entry);
  const summary = safeObj(entry.summary);
  const contracts = safeObj(entry.contracts);
  const syncState = safeObj(entry.sync_state);

  if (toInt(summary.sections_fail) > 0) return false;
  if (toInt(summary.total_fail) > 0) return false;
  if (toBool(syncState.would_change)) return false;

  if (("fixture_contract_ok" in contracts) && !toBool(contracts.fixture_contract_ok)) return false;
  if (("codec_parity_ok" in contracts) && !toBool(contracts.codec_parity_ok)) return false;
  if (("codec_sync_state_ok" in contracts) && !toBool(contracts.codec_sync_state_ok)) return false;

  return true;
}

function detectRegression(prevRow, curRow) {
  const reasons = [];
  if (!prevRow || !curRow) return reasons;

  if (prevRow.malformed_line || curRow.malformed_line) {
    reasons.push("malformed_history_entry");
    return reasons;
  }

  const prev = safeObj(prevRow.entry);
  const cur = safeObj(curRow.entry);

  const prevSummary = safeObj(prev.summary);
  const curSummary = safeObj(cur.summary);
  const prevContracts = safeObj(prev.contracts);
  const curContracts = safeObj(cur.contracts);
  const prevSync = safeObj(prev.sync_state);
  const curSync = safeObj(cur.sync_state);

  if (toInt(curSummary.sections_fail) > toInt(prevSummary.sections_fail)) {
    reasons.push("sections_fail_increase");
  }
  if (toInt(curSummary.total_fail) > toInt(prevSummary.total_fail)) {
    reasons.push("total_fail_increase");
  }

  const prevFailedSections = new Set(safeArray(prevSummary.failed_sections).map((x) => toString(x)));
  for (const section of safeArray(curSummary.failed_sections).map((x) => toString(x))) {
    if (section && !prevFailedSections.has(section)) {
      reasons.push(`new_failed_section:${section}`);
    }
  }

  const checks = ["fixture_contract_ok", "codec_parity_ok", "codec_sync_state_ok"];
  for (const c of checks) {
    if (toBool(prevContracts[c]) && !toBool(curContracts[c])) {
      reasons.push(`contract_degraded:${c}`);
    }
  }

  if (!toBool(prevSync.would_change) && toBool(curSync.would_change)) {
    reasons.push("sync_would_change_regressed");
  }

  return reasons;
}

function computeGreenStreak(rows) {
  let streak = 0;
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    if (entryClean(rows[i])) {
      streak += 1;
      continue;
    }
    break;
  }
  return streak;
}

function summarizeWindow(windowRows) {
  const summary = {
    entries_in_window: windowRows.length,
    transitions_in_window: Math.max(0, windowRows.length - 1),
    malformed_entries_in_window: windowRows.filter((r) => r.malformed_line).length,
    regressions_in_window: 0,
    regression_rate_pct: 0,
    regression_events: [],
    latest_entry_clean: false,
    latest_run_at: "",
    green_streak_latest: 0,
    first_run_at: "",
  };

  if (windowRows.length > 0) {
    summary.first_run_at = toString(safeObj(windowRows[0].entry).run_at);
  }

  for (let i = 1; i < windowRows.length; i += 1) {
    const prev = windowRows[i - 1];
    const cur = windowRows[i];
    const reasons = detectRegression(prev, cur);
    if (reasons.length > 0) {
      summary.regression_events.push({
        index_in_window: i,
        line_no: toInt(cur.line_no),
        run_at: toString(safeObj(cur.entry).run_at),
        reasons,
      });
    }
  }

  summary.regressions_in_window = summary.regression_events.length;
  if (summary.transitions_in_window > 0) {
    summary.regression_rate_pct = round4((summary.regressions_in_window / summary.transitions_in_window) * 100);
  }

  const latest = windowRows.length > 0 ? windowRows[windowRows.length - 1] : null;
  summary.latest_entry_clean = latest ? entryClean(latest) : false;
  summary.latest_run_at = latest ? toString(safeObj(latest.entry).run_at) : "";
  summary.green_streak_latest = computeGreenStreak(windowRows);

  return summary;
}

function maybeDelta(cur, prevAvailable, prev) {
  if (!prevAvailable) return null;
  return round4(toFloat(cur) - toFloat(prev));
}

function determineRisk(report, previousAvailable) {
  const reasons = [];
  const checks = safeObj(report.checks);
  const deltas = safeObj(report.deltas);

  if (report.entries_in_window === 0) {
    reasons.push("empty_window");
  }
  if (!toBool(checks.latest_entry_clean_ok)) {
    reasons.push("latest_entry_not_clean");
  }
  if (!toBool(checks.max_regressions_ok)) {
    reasons.push("max_regressions_exceeded");
  }
  if (!toBool(checks.max_regression_rate_ok)) {
    reasons.push("max_regression_rate_exceeded");
  }

  if (!toBool(checks.min_green_streak_ok)) {
    reasons.push("min_green_streak_not_met");
  }

  if (previousAvailable) {
    if (toFloat(deltas.regressions_in_window_delta) > 0) {
      reasons.push("regressions_worsened_vs_previous_window");
    }
    if (toFloat(deltas.regression_rate_pct_delta) > 0) {
      reasons.push("regression_rate_worsened_vs_previous_window");
    }
    if (toFloat(deltas.green_streak_latest_delta) < 0) {
      reasons.push("green_streak_worsened_vs_previous_window");
    }
  }

  let risk = "green";
  if (reasons.some((r) => [
    "empty_window",
    "latest_entry_not_clean",
    "max_regressions_exceeded",
    "max_regression_rate_exceeded",
  ].includes(r))) {
    risk = "red";
  } else if (reasons.length > 0) {
    risk = "amber";
  }

  return {
    risk_level: risk,
    risk_reasons: reasons,
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

  const historyPath = path.resolve(args.historyJsonl);
  const report = {
    generated_at: isoUtcNow(),
    strict: toBool(args.strict),
    history_path: historyPath,
    thresholds: {
      max_regressions: args.maxRegressions,
      max_regression_rate_pct: args.maxRegressionRatePct,
      min_green_streak: args.minGreenStreak,
    },
    window_last: args.last,
    entries_total: 0,
    entries_in_window: 0,
    transitions_in_window: 0,
    malformed_entries_in_window: 0,
    regressions_in_window: 0,
    regression_rate_pct: 0,
    regression_events: [],
    latest_entry_clean: false,
    latest_run_at: "",
    green_streak_latest: 0,
    previous_window: {
      available: false,
      entries_in_window: 0,
      transitions_in_window: 0,
      malformed_entries_in_window: 0,
      regressions_in_window: 0,
      regression_rate_pct: 0,
      latest_entry_clean: false,
      latest_run_at: "",
      green_streak_latest: 0,
      first_run_at: "",
    },
    deltas: {
      regressions_in_window_delta: null,
      regression_rate_pct_delta: null,
      green_streak_latest_delta: null,
    },
    checks: {
      max_regressions_ok: false,
      max_regression_rate_ok: false,
      min_green_streak_ok: false,
      latest_entry_clean_ok: false,
    },
    risk_level: "red",
    risk_reasons: [],
    strict_fail_reasons: [],
  };

  try {
    const rows = readHistoryRows(historyPath);
    const windowStart = Math.max(0, rows.length - args.last);
    const windowRows = rows.slice(windowStart);
    const prevStart = Math.max(0, rows.length - (2 * args.last));
    const previousWindowRows = rows.slice(prevStart, windowStart);

    const curSummary = summarizeWindow(windowRows);
    const prevSummary = summarizeWindow(previousWindowRows);
    const prevAvailable = previousWindowRows.length > 0;

    report.entries_total = rows.length;
    report.entries_in_window = curSummary.entries_in_window;
    report.transitions_in_window = curSummary.transitions_in_window;
    report.malformed_entries_in_window = curSummary.malformed_entries_in_window;
    report.regressions_in_window = curSummary.regressions_in_window;
    report.regression_rate_pct = curSummary.regression_rate_pct;
    report.regression_events = curSummary.regression_events;
    report.latest_entry_clean = curSummary.latest_entry_clean;
    report.latest_run_at = curSummary.latest_run_at;
    report.green_streak_latest = curSummary.green_streak_latest;

    report.previous_window = {
      available: prevAvailable,
      entries_in_window: prevSummary.entries_in_window,
      transitions_in_window: prevSummary.transitions_in_window,
      malformed_entries_in_window: prevSummary.malformed_entries_in_window,
      regressions_in_window: prevSummary.regressions_in_window,
      regression_rate_pct: prevSummary.regression_rate_pct,
      latest_entry_clean: prevSummary.latest_entry_clean,
      latest_run_at: prevSummary.latest_run_at,
      green_streak_latest: prevSummary.green_streak_latest,
      first_run_at: prevSummary.first_run_at,
    };

    report.deltas = {
      regressions_in_window_delta: maybeDelta(curSummary.regressions_in_window, prevAvailable, prevSummary.regressions_in_window),
      regression_rate_pct_delta: maybeDelta(curSummary.regression_rate_pct, prevAvailable, prevSummary.regression_rate_pct),
      green_streak_latest_delta: maybeDelta(curSummary.green_streak_latest, prevAvailable, prevSummary.green_streak_latest),
    };

    report.checks.max_regressions_ok = report.regressions_in_window <= args.maxRegressions;
    report.checks.max_regression_rate_ok = report.regression_rate_pct <= args.maxRegressionRatePct;
    report.checks.min_green_streak_ok = report.green_streak_latest >= args.minGreenStreak;
    report.checks.latest_entry_clean_ok = report.latest_entry_clean;

    if (report.entries_in_window === 0) {
      report.strict_fail_reasons.push("empty_window");
    }
    if (!report.checks.max_regressions_ok) {
      report.strict_fail_reasons.push("max_regressions_exceeded");
    }
    if (!report.checks.max_regression_rate_ok) {
      report.strict_fail_reasons.push("max_regression_rate_exceeded");
    }
    if (!report.checks.min_green_streak_ok) {
      report.strict_fail_reasons.push("min_green_streak_not_met");
    }
    if (!report.checks.latest_entry_clean_ok) {
      report.strict_fail_reasons.push("latest_entry_not_clean");
    }

    const risk = determineRisk(report, prevAvailable);
    report.risk_level = risk.risk_level;
    report.risk_reasons = risk.risk_reasons;
  } catch (err) {
    report.strict_fail_reasons.push(`runtime_error:${toString((err && err.message) || err || "unknown_error")}`);
    report.risk_level = "red";
    report.risk_reasons = [`runtime_error:${toString((err && err.message) || err || "unknown_error")}`];
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

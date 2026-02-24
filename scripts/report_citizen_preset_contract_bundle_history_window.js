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
    "  node scripts/report_citizen_preset_contract_bundle_history_window.js [options]",
    "",
    "Options:",
    "  --history-jsonl <path>  History JSONL path (default: docs/etl/runs/citizen_preset_contract_bundle_history.jsonl)",
    "  --last <n>              Number of trailing entries to inspect (default: 20)",
    "  --json-out <path>       Optional output file for JSON report",
    "  --strict                Exit non-zero when regressions are found in window",
    "  --help                  Show this help",
  ].join("\n");
}

function parseArgs(argv) {
  const out = {
    historyJsonl: "docs/etl/runs/citizen_preset_contract_bundle_history.jsonl",
    last: 20,
    jsonOut: "",
    strict: false,
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
    if (a === "--history-jsonl") {
      out.historyJsonl = String(argv[i + 1] || "");
      i += 1;
      continue;
    }
    if (a === "--last") {
      out.last = Number(argv[i + 1] || "20");
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
  return out;
}

function ensureParentDir(filePath) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
}

function safeObj(v) {
  return v && typeof v === "object" ? v : {};
}

function safeArray(v) {
  return Array.isArray(v) ? v : [];
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

function readHistoryEntries(historyPath) {
  if (!fs.existsSync(historyPath)) return [];
  const raw = fs.readFileSync(historyPath, "utf8");
  const lines = raw.split(/\r?\n/).filter((line) => line.trim().length > 0);
  const out = [];
  for (const line of lines) {
    try {
      out.push(JSON.parse(line));
    } catch (_err) {
      // Keep malformed rows visible to summary callers.
      out.push({
        malformed_line: true,
      });
    }
  }
  return out;
}

function detectRegression(prevEntry, curEntry) {
  const reasons = [];
  if (!prevEntry || typeof prevEntry !== "object") return reasons;

  const prevSummary = safeObj(prevEntry.summary);
  const curSummary = safeObj(curEntry.summary);
  const prevContracts = safeObj(prevEntry.contracts);
  const curContracts = safeObj(curEntry.contracts);
  const prevSync = safeObj(prevEntry.sync_state);
  const curSync = safeObj(curEntry.sync_state);

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

function summarizeEntry(entry) {
  return {
    run_at: toString(entry.run_at),
    sections_fail: toInt(safeObj(entry.summary).sections_fail),
    total_fail: toInt(safeObj(entry.summary).total_fail),
    failed_sections: safeArray(safeObj(entry.summary).failed_sections).map((x) => toString(x)),
    would_change: toBool(safeObj(entry.sync_state).would_change),
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

  const historyPath = path.resolve(args.historyJsonl);
  const lastN = Math.max(1, toInt(args.last));
  const report = {
    generated_at: isoUtcNow(),
    strict: Boolean(args.strict),
    history_path: historyPath,
    window_last: lastN,
    entries_total: 0,
    entries_in_window: 0,
    malformed_entries_in_window: 0,
    regressions_in_window: 0,
    regression_events: [],
    first_run_at_in_window: "",
    last_run_at_in_window: "",
    latest_entry: {},
  };

  try {
    const allEntries = readHistoryEntries(historyPath);
    report.entries_total = allEntries.length;
    const windowEntries = allEntries.slice(Math.max(0, allEntries.length - lastN));
    report.entries_in_window = windowEntries.length;

    if (windowEntries.length > 0) {
      report.first_run_at_in_window = toString(windowEntries[0] && windowEntries[0].run_at);
      report.last_run_at_in_window = toString(windowEntries[windowEntries.length - 1] && windowEntries[windowEntries.length - 1].run_at);
      report.latest_entry = summarizeEntry(windowEntries[windowEntries.length - 1]);
    }

    for (let i = 0; i < windowEntries.length; i += 1) {
      const cur = windowEntries[i];
      if (cur && cur.malformed_line) {
        report.malformed_entries_in_window += 1;
        report.regression_events.push({
          run_at: "",
          index_in_window: i,
          reasons: ["malformed_history_entry"],
        });
        continue;
      }

      if (i === 0) continue;
      const prev = windowEntries[i - 1];
      const reasons = detectRegression(prev, cur);
      if (reasons.length > 0) {
        report.regression_events.push({
          run_at: toString(cur && cur.run_at),
          index_in_window: i,
          reasons,
        });
      }
    }

    report.regressions_in_window = report.regression_events.length;
  } catch (err) {
    report.regression_events.push({
      run_at: "",
      index_in_window: 0,
      reasons: [`runtime_error:${String((err && err.message) || err || "unknown_error")}`],
    });
    report.regressions_in_window = report.regression_events.length;
  }

  const serialized = JSON.stringify(report, null, 2);
  console.log(serialized);

  if (args.jsonOut) {
    const outPath = path.resolve(args.jsonOut);
    ensureParentDir(outPath);
    fs.writeFileSync(outPath, `${serialized}\n`, "utf8");
  }

  if (args.strict && report.regressions_in_window > 0) {
    process.exit(1);
  }
}

main();

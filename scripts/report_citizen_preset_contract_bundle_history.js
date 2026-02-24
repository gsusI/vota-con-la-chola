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
    "  node scripts/report_citizen_preset_contract_bundle_history.js [options]",
    "",
    "Options:",
    "  --bundle-json <path>    Bundle report JSON path (required)",
    "  --history-jsonl <path>  History JSONL path (default: docs/etl/runs/citizen_preset_contract_bundle_history.jsonl)",
    "  --json-out <path>       Optional output file for JSON report",
    "  --strict                Exit non-zero when regression is detected",
    "  --help                  Show this help",
  ].join("\n");
}

function parseArgs(argv) {
  const out = {
    bundleJson: "",
    historyJsonl: "docs/etl/runs/citizen_preset_contract_bundle_history.jsonl",
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
    if (a === "--bundle-json") {
      out.bundleJson = String(argv[i + 1] || "");
      i += 1;
      continue;
    }
    if (a === "--history-jsonl") {
      out.historyJsonl = String(argv[i + 1] || "");
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

function readJson(absPath) {
  const raw = fs.readFileSync(absPath, "utf8");
  return JSON.parse(raw);
}

function safeObj(v) {
  return v && typeof v === "object" ? v : {};
}

function safeArray(v) {
  return Array.isArray(v) ? v : [];
}

function toInt(v) {
  if (typeof v === "number" && Number.isFinite(v)) return Math.trunc(v);
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}

function toBool(v) {
  return Boolean(v);
}

function toString(v) {
  return String(v == null ? "" : v);
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
      // Keep bad rows visible but non-fatal for forward progress.
      out.push({
        malformed_line: true,
      });
    }
  }
  return out;
}

function buildEntry(bundle, bundlePath) {
  const summary = safeObj(bundle.summary);
  const contracts = safeObj(bundle.contracts);
  const syncReport = safeObj(safeObj(bundle.reports).codec_sync_state);
  const syncResult = safeObj(safeArray(syncReport.results)[0]);

  return {
    run_at: toString(bundle.generated_at) || isoUtcNow(),
    bundle_path: bundlePath,
    summary: {
      sections_total: toInt(summary.sections_total),
      sections_pass: toInt(summary.sections_pass),
      sections_fail: toInt(summary.sections_fail),
      failed_sections: safeArray(summary.failed_sections).map((x) => toString(x)).filter(Boolean),
      total_cases: toInt(summary.total_cases),
      total_pass: toInt(summary.total_pass),
      total_fail: toInt(summary.total_fail),
      failed_ids: safeArray(summary.failed_ids).map((x) => toString(x)).filter(Boolean),
    },
    contracts: {
      fixture_contract_ok: toBool(safeObj(contracts.fixture_contract).ok),
      codec_parity_ok: toBool(safeObj(contracts.codec_parity).ok),
      codec_sync_state_ok: toBool(safeObj(contracts.codec_sync_state).ok),
    },
    sync_state: {
      would_change: toBool(syncResult.would_change),
    },
  };
}

function summarizeForReport(entry) {
  return {
    run_at: toString(entry.run_at),
    summary: safeObj(entry.summary),
    contracts: safeObj(entry.contracts),
    sync_state: safeObj(entry.sync_state),
  };
}

function detectRegression(prevEntry, curEntry) {
  const reasons = [];
  if (!prevEntry || typeof prevEntry !== "object") {
    return reasons;
  }

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
  const curFailedSections = safeArray(curSummary.failed_sections).map((x) => toString(x));
  for (const section of curFailedSections) {
    if (section && !prevFailedSections.has(section)) {
      reasons.push(`new_failed_section:${section}`);
    }
  }

  const checks = [
    "fixture_contract_ok",
    "codec_parity_ok",
    "codec_sync_state_ok",
  ];
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

function writeHistoryEntry(historyPath, entry) {
  ensureParentDir(historyPath);
  fs.appendFileSync(historyPath, `${JSON.stringify(entry)}\n`, "utf8");
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

  if (!toString(args.bundleJson).trim()) {
    console.error("Missing required argument: --bundle-json <path>");
    console.error(usage());
    process.exit(2);
  }

  const bundlePath = path.resolve(args.bundleJson);
  const historyPath = path.resolve(args.historyJsonl);

  const report = {
    generated_at: isoUtcNow(),
    strict: Boolean(args.strict),
    bundle_path: bundlePath,
    history_path: historyPath,
    history_size_before: 0,
    history_size_after: 0,
    regression_detected: false,
    regression_reasons: [],
    previous_entry: {},
    current_entry: {},
  };

  try {
    const bundle = readJson(bundlePath);
    const entriesBefore = readHistoryEntries(historyPath);
    report.history_size_before = entriesBefore.length;

    const previousEntry = entriesBefore.length > 0 ? entriesBefore[entriesBefore.length - 1] : {};
    const currentEntry = buildEntry(bundle, bundlePath);
    const reasons = detectRegression(previousEntry, currentEntry);

    writeHistoryEntry(historyPath, currentEntry);

    report.history_size_after = report.history_size_before + 1;
    report.regression_reasons = reasons;
    report.regression_detected = reasons.length > 0;
    report.previous_entry = summarizeForReport(previousEntry);
    report.current_entry = summarizeForReport(currentEntry);
  } catch (err) {
    report.regression_detected = true;
    report.regression_reasons = [
      `runtime_error:${String((err && err.message) || err || "unknown_error")}`,
    ];
  }

  const serialized = JSON.stringify(report, null, 2);
  console.log(serialized);

  if (args.jsonOut) {
    const outPath = path.resolve(args.jsonOut);
    ensureParentDir(outPath);
    fs.writeFileSync(outPath, `${serialized}\n`, "utf8");
  }

  if (args.strict && report.regression_detected) {
    process.exit(1);
  }
}

main();

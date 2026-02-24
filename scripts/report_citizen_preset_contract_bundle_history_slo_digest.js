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
    "  node scripts/report_citizen_preset_contract_bundle_history_slo_digest.js [options]",
    "",
    "Options:",
    "  --slo-json <path>      Input SLO report JSON path (required)",
    "  --json-out <path>      Optional output file for digest JSON",
    "  --strict               Exit non-zero when digest status is red or input is invalid",
    "  --help                 Show this help",
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
    sloJson: "",
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
    if (a === "--slo-json") {
      out.sloJson = toString(argv[i + 1]);
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

  if (!toString(out.sloJson).trim()) {
    throw new Error("Missing required argument: --slo-json <path>");
  }

  return out;
}

function readJson(absPath) {
  return JSON.parse(fs.readFileSync(absPath, "utf8"));
}

function determineStatus(riskLevel, strictFails) {
  if (riskLevel === "red") return "failed";
  if (riskLevel === "amber") return "degraded";
  if (strictFails.length > 0) return "failed";
  return "ok";
}

function buildDigest(slo, sloPath, strict) {
  const checks = safeObj(slo.checks);
  const thresholds = safeObj(slo.thresholds);
  const previousWindow = safeObj(slo.previous_window);
  const deltas = safeObj(slo.deltas);
  const strictFails = safeArray(slo.strict_fail_reasons).map((x) => toString(x)).filter(Boolean);
  const riskReasons = safeArray(slo.risk_reasons).map((x) => toString(x)).filter(Boolean);

  const riskLevelRaw = toString(slo.risk_level).trim().toLowerCase();
  const riskLevel = ["green", "amber", "red"].includes(riskLevelRaw) ? riskLevelRaw : "red";

  const digest = {
    generated_at: isoUtcNow(),
    strict: toBool(strict),
    input: {
      slo_json_path: sloPath,
      slo_generated_at: toString(slo.generated_at),
    },
    status: determineStatus(riskLevel, strictFails),
    risk_level: riskLevel,
    risk_reasons: riskReasons,
    strict_fail_reasons: strictFails,
    key_metrics: {
      entries_in_window: toInt(slo.entries_in_window),
      regressions_in_window: toInt(slo.regressions_in_window),
      regression_rate_pct: toFloat(slo.regression_rate_pct),
      green_streak_latest: toInt(slo.green_streak_latest),
      latest_entry_clean: toBool(slo.latest_entry_clean),
    },
    key_checks: {
      max_regressions_ok: toBool(checks.max_regressions_ok),
      max_regression_rate_ok: toBool(checks.max_regression_rate_ok),
      min_green_streak_ok: toBool(checks.min_green_streak_ok),
      latest_entry_clean_ok: toBool(checks.latest_entry_clean_ok),
    },
    thresholds: {
      max_regressions: toInt(thresholds.max_regressions),
      max_regression_rate_pct: toFloat(thresholds.max_regression_rate_pct),
      min_green_streak: toInt(thresholds.min_green_streak),
    },
    previous_window: {
      available: toBool(previousWindow.available),
      regressions_in_window: toInt(previousWindow.regressions_in_window),
      regression_rate_pct: toFloat(previousWindow.regression_rate_pct),
      green_streak_latest: toInt(previousWindow.green_streak_latest),
    },
    deltas: {
      regressions_in_window_delta: deltas.regressions_in_window_delta == null ? null : toFloat(deltas.regressions_in_window_delta),
      regression_rate_pct_delta: deltas.regression_rate_pct_delta == null ? null : toFloat(deltas.regression_rate_pct_delta),
      green_streak_latest_delta: deltas.green_streak_latest_delta == null ? null : toFloat(deltas.green_streak_latest_delta),
    },
  };

  return digest;
}

function validateDigest(digest) {
  const reasons = [];

  if (!toString(safeObj(digest.input).slo_generated_at)) {
    reasons.push("missing_slo_generated_at");
  }

  const status = toString(digest.status);
  if (!["ok", "degraded", "failed"].includes(status)) {
    reasons.push("invalid_status");
  }

  const risk = toString(digest.risk_level);
  if (!["green", "amber", "red"].includes(risk)) {
    reasons.push("invalid_risk_level");
  }

  const keyMetrics = safeObj(digest.key_metrics);
  if (toInt(keyMetrics.entries_in_window) < 0) {
    reasons.push("invalid_entries_in_window");
  }
  if (toInt(keyMetrics.regressions_in_window) < 0) {
    reasons.push("invalid_regressions_in_window");
  }
  if (toFloat(keyMetrics.regression_rate_pct) < 0) {
    reasons.push("invalid_regression_rate_pct");
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

  const sloPath = path.resolve(args.sloJson);
  const report = {
    generated_at: isoUtcNow(),
    strict: toBool(args.strict),
    input_path: sloPath,
    digest: {},
    validation_errors: [],
  };

  try {
    const slo = readJson(sloPath);
    const digest = buildDigest(slo, sloPath, args.strict);
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

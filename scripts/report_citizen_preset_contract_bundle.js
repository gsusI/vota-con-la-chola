#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function isoUtcNow() {
  return new Date().toISOString();
}

function usage() {
  return [
    "Usage:",
    "  node scripts/report_citizen_preset_contract_bundle.js [options]",
    "",
    "Options:",
    "  --fixture <path>    Fixture JSON path (default: tests/fixtures/citizen_preset_hash_matrix.json)",
    "  --source <path>     Source codec path (default: ui/citizen/preset_codec.js)",
    "  --published <path>  Published codec path (default: docs/gh-pages/citizen/preset_codec.js)",
    "  --json-out <path>   Optional output file for JSON report",
    "  --strict            Exit non-zero when any sub-contract fails",
    "  --help              Show this help",
  ].join("\n");
}

function parseArgs(argv) {
  const out = {
    fixture: "tests/fixtures/citizen_preset_hash_matrix.json",
    source: "ui/citizen/preset_codec.js",
    published: "docs/gh-pages/citizen/preset_codec.js",
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
    if (a === "--fixture") {
      out.fixture = String(argv[i + 1] || "");
      i += 1;
      continue;
    }
    if (a === "--source") {
      out.source = String(argv[i + 1] || "");
      i += 1;
      continue;
    }
    if (a === "--published") {
      out.published = String(argv[i + 1] || "");
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

function asArray(v) {
  return Array.isArray(v) ? v : [];
}

function toInt(v) {
  if (typeof v === "number" && Number.isFinite(v)) return Math.trunc(v);
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}

function safeObj(v) {
  return v && typeof v === "object" ? v : {};
}

function runJsonScript(scriptPath, args) {
  const proc = spawnSync(process.execPath, [scriptPath, ...args], {
    encoding: "utf8",
  });

  const out = {
    ok: false,
    report: {},
    error: "",
    status: proc.status == null ? -1 : proc.status,
    signal: proc.signal || "",
  };

  const stdoutText = String(proc.stdout || "").trim();
  if (!stdoutText) {
    out.error = `missing stdout JSON from ${path.basename(scriptPath)}`;
    return out;
  }

  try {
    out.report = JSON.parse(stdoutText);
  } catch (err) {
    out.error = `invalid JSON from ${path.basename(scriptPath)}: ${String((err && err.message) || err || "parse_error")}`;
    return out;
  }

  const summary = safeObj(out.report.summary);
  out.ok = toInt(summary.total_fail) === 0;
  return out;
}

function foldSummary(parts) {
  let sectionsPass = 0;
  let sectionsFail = 0;
  let totalCases = 0;
  let totalPass = 0;
  let totalFail = 0;
  const failedSections = [];
  const failedIds = [];

  for (const p of parts) {
    const sectionName = String(p.section || "");
    const summary = safeObj(p.report && p.report.summary);
    const sectionFail = toInt(summary.total_fail) > 0 || !p.ok;
    if (sectionFail) {
      sectionsFail += 1;
      failedSections.push(sectionName);
    } else {
      sectionsPass += 1;
    }

    totalCases += toInt(summary.total_cases);
    totalPass += toInt(summary.total_pass);
    totalFail += toInt(summary.total_fail);

    const ids = asArray(summary.failed_ids).map((x) => String(x || "").trim()).filter(Boolean);
    if (ids.length > 0) {
      for (const id of ids) {
        failedIds.push(`${sectionName}:${id}`);
      }
    } else if (sectionFail) {
      failedIds.push(`${sectionName}:summary_or_runtime_failure`);
    }
  }

  return {
    sections_total: parts.length,
    sections_pass: sectionsPass,
    sections_fail: sectionsFail,
    failed_sections: failedSections,
    total_cases: totalCases,
    total_pass: totalPass,
    total_fail: totalFail,
    failed_ids: failedIds,
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

  const fixturePath = path.resolve(args.fixture);
  const sourcePath = path.resolve(args.source);
  const publishedPath = path.resolve(args.published);
  const scriptsDir = path.resolve(__dirname);

  const fixtureScript = path.join(scriptsDir, "report_citizen_preset_fixture_contract.js");
  const parityScript = path.join(scriptsDir, "report_citizen_preset_codec_parity.js");
  const syncScript = path.join(scriptsDir, "report_citizen_preset_codec_sync_state.js");

  const fixtureRun = runJsonScript(fixtureScript, ["--fixture", fixturePath, "--codec", sourcePath]);
  const parityRun = runJsonScript(parityScript, ["--source", sourcePath, "--published", publishedPath]);
  const syncRun = runJsonScript(syncScript, ["--source", sourcePath, "--published", publishedPath]);

  const parts = [
    {
      section: "fixture_contract",
      ok: fixtureRun.ok,
      report: fixtureRun.report,
      status: fixtureRun.status,
      signal: fixtureRun.signal,
      error: fixtureRun.error,
    },
    {
      section: "codec_parity",
      ok: parityRun.ok,
      report: parityRun.report,
      status: parityRun.status,
      signal: parityRun.signal,
      error: parityRun.error,
    },
    {
      section: "codec_sync_state",
      ok: syncRun.ok,
      report: syncRun.report,
      status: syncRun.status,
      signal: syncRun.signal,
      error: syncRun.error,
    },
  ];

  const summary = foldSummary(parts);
  const report = {
    generated_at: isoUtcNow(),
    strict: Boolean(args.strict),
    inputs: {
      fixture_path: fixturePath,
      source_path: sourcePath,
      published_path: publishedPath,
    },
    summary,
    contracts: {
      fixture_contract: {
        ok: parts[0].ok,
        status: parts[0].status,
        signal: parts[0].signal,
        error: parts[0].error,
        summary: safeObj(parts[0].report.summary),
      },
      codec_parity: {
        ok: parts[1].ok,
        status: parts[1].status,
        signal: parts[1].signal,
        error: parts[1].error,
        summary: safeObj(parts[1].report.summary),
      },
      codec_sync_state: {
        ok: parts[2].ok,
        status: parts[2].status,
        signal: parts[2].signal,
        error: parts[2].error,
        summary: safeObj(parts[2].report.summary),
      },
    },
    reports: {
      fixture_contract: safeObj(parts[0].report),
      codec_parity: safeObj(parts[1].report),
      codec_sync_state: safeObj(parts[2].report),
    },
  };

  const serialized = JSON.stringify(report, null, 2);
  console.log(serialized);

  if (args.jsonOut) {
    const outPath = path.resolve(args.jsonOut);
    ensureParentDir(outPath);
    fs.writeFileSync(outPath, `${serialized}\n`, "utf8");
  }

  if (args.strict && summary.sections_fail > 0) {
    process.exit(1);
  }
}

main();

#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require("node:fs");
const path = require("node:path");
const util = require("node:util");

function isoUtcNow() {
  return new Date().toISOString();
}

function usage() {
  return [
    "Usage:",
    "  node scripts/report_citizen_preset_fixture_contract.js [options]",
    "",
    "Options:",
    "  --fixture <path>   Fixture JSON path (default: tests/fixtures/citizen_preset_hash_matrix.json)",
    "  --codec <path>     Preset codec module path (default: ui/citizen/preset_codec.js)",
    "  --json-out <path>  Optional output file for JSON report",
    "  --strict           Exit non-zero when any case fails",
    "  --help             Show this help",
  ].join("\n");
}

function parseArgs(argv) {
  const out = {
    fixture: "tests/fixtures/citizen_preset_hash_matrix.json",
    codec: "ui/citizen/preset_codec.js",
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
    if (a === "--codec") {
      out.codec = String(argv[i + 1] || "");
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

function readJson(absPath) {
  const raw = fs.readFileSync(absPath, "utf8");
  return JSON.parse(raw);
}

function safeString(v) {
  return String(v == null ? "" : v);
}

function compareReadResult(got, expected) {
  const exp = expected || {};
  if (safeString(got && got.error_code) !== safeString(exp.error_code)) {
    return `error_code mismatch: got=${safeString(got && got.error_code)} expected=${safeString(exp.error_code)}`;
  }

  if (!util.isDeepStrictEqual(got && got.preset, exp.preset)) {
    return `preset mismatch: got=${JSON.stringify(got && got.preset)} expected=${JSON.stringify(exp.preset)}`;
  }

  const contains = safeString(exp.error_contains).trim();
  if (contains) {
    const rx = new RegExp(contains, "i");
    if (!rx.test(safeString(got && got.error))) {
      return `error text mismatch: got=${safeString(got && got.error)} expected_regex=${contains}`;
    }
    return "";
  }

  if (safeString(got && got.error) !== safeString(exp.error)) {
    return `error mismatch: got=${safeString(got && got.error)} expected=${safeString(exp.error)}`;
  }

  return "";
}

function pushCaseResult(results, section, id, error) {
  const ok = !error;
  results.push({
    section,
    id,
    ok,
    error: ok ? "" : String(error || ""),
  });
}

function summarize(results) {
  const bySection = {
    hash_cases: { total: 0, pass: 0, fail: 0 },
    share_cases: { total: 0, pass: 0, fail: 0 },
  };

  for (const r of results) {
    if (!bySection[r.section]) continue;
    bySection[r.section].total += 1;
    if (r.ok) bySection[r.section].pass += 1;
    else bySection[r.section].fail += 1;
  }

  const total = results.length;
  const fail = results.filter((r) => !r.ok).length;
  const pass = total - fail;
  const failedIds = results.filter((r) => !r.ok).map((r) => `${r.section}:${r.id}`);

  return {
    hash_cases_total: bySection.hash_cases.total,
    hash_cases_pass: bySection.hash_cases.pass,
    hash_cases_fail: bySection.hash_cases.fail,
    share_cases_total: bySection.share_cases.total,
    share_cases_pass: bySection.share_cases.pass,
    share_cases_fail: bySection.share_cases.fail,
    total_cases: total,
    total_pass: pass,
    total_fail: fail,
    failed_ids: failedIds,
  };
}

function ensureParentDir(filePath) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
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
  const codecPath = path.resolve(args.codec);

  const report = {
    generated_at: isoUtcNow(),
    fixture_path: fixturePath,
    codec_path: codecPath,
    schema_version: "",
    strict: Boolean(args.strict),
    summary: {},
    results: [],
  };

  try {
    const fixture = readJson(fixturePath);
    // eslint-disable-next-line import/no-dynamic-require, global-require
    const codec = require(codecPath);

    report.schema_version = safeString(fixture && fixture.schema_version);

    const config = (fixture && fixture.config) || {};
    const hashCases = Array.isArray(fixture && fixture.hash_cases) ? fixture.hash_cases : [];
    const shareCases = Array.isArray(fixture && fixture.share_cases) ? fixture.share_cases : [];

    for (const c of hashCases) {
      const id = safeString(c && c.id) || "unknown_hash_case";
      try {
        const got = codec.readPresetFromHash(safeString(c && c.hash), config);
        const err = compareReadResult(got, c && c.expect);
        pushCaseResult(report.results, "hash_cases", id, err);
      } catch (err) {
        pushCaseResult(report.results, "hash_cases", id, String((err && err.message) || err || "runtime_error"));
      }
    }

    for (const c of shareCases) {
      const id = safeString(c && c.id) || "unknown_share_case";
      try {
        const input = (c && c.input) || {};
        const expected = (c && c.expect) || {};
        const built = codec.buildAlignmentPresetShareUrl(
          input.options || {},
          safeString(input.href),
          safeString(input.origin),
          config
        );

        const parsed = new URL(built);
        let err = "";

        if (typeof expected.search === "string" && parsed.search !== expected.search) {
          err = `search mismatch: got=${parsed.search} expected=${expected.search}`;
        } else if (typeof expected.hash_prefix === "string" && !parsed.hash.startsWith(expected.hash_prefix)) {
          err = `hash_prefix mismatch: got=${parsed.hash} expected_prefix=${expected.hash_prefix}`;
        } else if (typeof expected.hash === "string" && parsed.hash !== expected.hash) {
          err = `hash mismatch: got=${parsed.hash} expected=${expected.hash}`;
        } else {
          const decoded = codec.readPresetFromHash(parsed.hash, config);
          err = compareReadResult(decoded, expected.decoded || {});
        }

        pushCaseResult(report.results, "share_cases", id, err);
      } catch (err) {
        pushCaseResult(report.results, "share_cases", id, String((err && err.message) || err || "runtime_error"));
      }
    }

    report.summary = summarize(report.results);
  } catch (err) {
    report.summary = {
      hash_cases_total: 0,
      hash_cases_pass: 0,
      hash_cases_fail: 0,
      share_cases_total: 0,
      share_cases_pass: 0,
      share_cases_fail: 0,
      total_cases: 0,
      total_pass: 0,
      total_fail: 1,
      failed_ids: ["runtime:report_generation"],
    };
    report.results.push({
      section: "runtime",
      id: "report_generation",
      ok: false,
      error: String((err && err.stack) || (err && err.message) || err || "runtime_error"),
    });
  }

  const serialized = JSON.stringify(report, null, 2);
  console.log(serialized);

  if (args.jsonOut) {
    const outPath = path.resolve(args.jsonOut);
    ensureParentDir(outPath);
    fs.writeFileSync(outPath, `${serialized}\n`, "utf8");
  }

  if (args.strict && report.summary.total_fail > 0) {
    process.exit(1);
  }
}

main();

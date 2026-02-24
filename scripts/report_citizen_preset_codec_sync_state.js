#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

function isoUtcNow() {
  return new Date().toISOString();
}

function usage() {
  return [
    "Usage:",
    "  node scripts/report_citizen_preset_codec_sync_state.js [options]",
    "",
    "Options:",
    "  --source <path>     Source codec path (default: ui/citizen/preset_codec.js)",
    "  --published <path>  Published codec path (default: docs/gh-pages/citizen/preset_codec.js)",
    "  --json-out <path>   Optional output file for JSON report",
    "  --strict            Exit non-zero when published file is stale",
    "  --help              Show this help",
  ].join("\n");
}

function parseArgs(argv) {
  const out = {
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

function sha256Hex(text) {
  return crypto.createHash("sha256").update(text, "utf8").digest("hex");
}

function byteLenUtf8(text) {
  return Buffer.byteLength(text, "utf8");
}

function safeLine(lines, idx) {
  if (idx < 0 || idx >= lines.length) return "";
  return String(lines[idx] || "");
}

function firstLineDiff(aText, bText) {
  const aLines = String(aText).split(/\r?\n/);
  const bLines = String(bText).split(/\r?\n/);
  const maxLen = Math.max(aLines.length, bLines.length);
  for (let i = 0; i < maxLen; i += 1) {
    const aLine = safeLine(aLines, i);
    const bLine = safeLine(bLines, i);
    if (aLine !== bLine) {
      return {
        line: i + 1,
        source_line: aLine,
        published_line: bLine,
      };
    }
  }
  return {
    line: 0,
    source_line: "",
    published_line: "",
  };
}

function summarize(results) {
  const total = results.length;
  const fail = results.filter((r) => !r.ok).length;
  const pass = total - fail;
  const failedIds = results.filter((r) => !r.ok).map((r) => `${r.section}:${r.id}`);
  return {
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

  const sourcePath = path.resolve(args.source);
  const publishedPath = path.resolve(args.published);
  const report = {
    generated_at: isoUtcNow(),
    source_path: sourcePath,
    published_path: publishedPath,
    strict: Boolean(args.strict),
    summary: {},
    results: [],
  };

  try {
    const sourceRaw = fs.readFileSync(sourcePath, "utf8");
    const publishedBeforeRaw = fs.readFileSync(publishedPath, "utf8");

    const sourceSha = sha256Hex(sourceRaw);
    const publishedBeforeSha = sha256Hex(publishedBeforeRaw);
    const sourceBytes = byteLenUtf8(sourceRaw);
    const publishedBeforeBytes = byteLenUtf8(publishedBeforeRaw);
    const wouldChange = sourceRaw !== publishedBeforeRaw;
    const diff = firstLineDiff(sourceRaw, publishedBeforeRaw);

    report.results.push({
      section: "sync_state",
      id: "source_to_published",
      ok: !wouldChange,
      error: wouldChange ? "published preset codec is stale" : "",
      would_change: wouldChange,
      source_sha256: sourceSha,
      published_before_sha256: publishedBeforeSha,
      published_after_sha256: sourceSha,
      source_bytes: sourceBytes,
      published_before_bytes: publishedBeforeBytes,
      published_after_bytes: sourceBytes,
      bytes_delta_after_sync: sourceBytes - publishedBeforeBytes,
      first_diff_line: diff.line,
      first_diff_source_line: diff.source_line,
      first_diff_published_line: diff.published_line,
      recommended_command: wouldChange ? "just explorer-gh-pages-build" : "",
    });
  } catch (err) {
    report.results.push({
      section: "runtime",
      id: "sync_state_generation",
      ok: false,
      error: String((err && err.stack) || (err && err.message) || err || "runtime_error"),
      would_change: false,
      source_sha256: "",
      published_before_sha256: "",
      published_after_sha256: "",
      source_bytes: 0,
      published_before_bytes: 0,
      published_after_bytes: 0,
      bytes_delta_after_sync: 0,
      first_diff_line: 0,
      first_diff_source_line: "",
      first_diff_published_line: "",
      recommended_command: "",
    });
  }

  report.summary = summarize(report.results);
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

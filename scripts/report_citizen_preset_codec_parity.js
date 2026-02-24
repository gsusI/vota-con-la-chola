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
    "  node scripts/report_citizen_preset_codec_parity.js [options]",
    "",
    "Options:",
    "  --source <path>     Source codec path (default: ui/citizen/preset_codec.js)",
    "  --published <path>  Published codec path (default: docs/gh-pages/citizen/preset_codec.js)",
    "  --json-out <path>   Optional output file for JSON report",
    "  --strict            Exit non-zero when parity fails",
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

function ensureParentDir(filePath) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
}

function sha256Hex(text) {
  return crypto.createHash("sha256").update(text, "utf8").digest("hex");
}

function safeLine(lines, idx) {
  if (idx < 0 || idx >= lines.length) return "";
  return String(lines[idx] || "");
}

function firstLineDiff(sourceText, publishedText) {
  const sourceLines = String(sourceText).split(/\r?\n/);
  const publishedLines = String(publishedText).split(/\r?\n/);
  const maxLen = Math.max(sourceLines.length, publishedLines.length);

  for (let i = 0; i < maxLen; i += 1) {
    if (safeLine(sourceLines, i) !== safeLine(publishedLines, i)) {
      return {
        line: i + 1,
        source_line: safeLine(sourceLines, i),
        published_line: safeLine(publishedLines, i),
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
    const publishedRaw = fs.readFileSync(publishedPath, "utf8");

    const sourceHash = sha256Hex(sourceRaw);
    const publishedHash = sha256Hex(publishedRaw);
    const identical = sourceRaw === publishedRaw;

    const diff = firstLineDiff(sourceRaw, publishedRaw);
    report.results.push({
      section: "parity",
      id: "source_vs_published",
      ok: identical,
      error: identical ? "" : "preset codec mismatch",
      source_bytes: Buffer.byteLength(sourceRaw, "utf8"),
      published_bytes: Buffer.byteLength(publishedRaw, "utf8"),
      source_sha256: sourceHash,
      published_sha256: publishedHash,
      first_diff_line: diff.line,
      first_diff_source_line: diff.source_line,
      first_diff_published_line: diff.published_line,
    });
    report.summary = summarize(report.results);
  } catch (err) {
    report.results.push({
      section: "runtime",
      id: "parity_read",
      ok: false,
      error: String((err && err.stack) || (err && err.message) || err || "runtime_error"),
      source_bytes: 0,
      published_bytes: 0,
      source_sha256: "",
      published_sha256: "",
      first_diff_line: 0,
      first_diff_source_line: "",
      first_diff_published_line: "",
    });
    report.summary = summarize(report.results);
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

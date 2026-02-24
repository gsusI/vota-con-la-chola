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
    "  node scripts/report_citizen_release_hardening.js [options]",
    "",
    "Options:",
    "  --source-root <path>         Source citizen dir (default: ui/citizen)",
    "  --published-root <path>      Published citizen dir (default: docs/gh-pages/citizen)",
    "  --snapshot <path>            Published snapshot path (default: docs/gh-pages/citizen/data/citizen.json)",
    "  --concerns <path>            Concerns config path (default: ui/citizen/concerns_v1.json)",
    "  --assets <csv>               Relative asset paths CSV",
    "  --max-snapshot-bytes <int>   Max allowed snapshot bytes (default: 5000000)",
    "  --json-out <path>            Optional JSON output file",
    "  --strict                     Exit non-zero when release checklist fails",
    "  --help                       Show this help",
  ].join("\n");
}

function parseArgs(argv) {
  const out = {
    sourceRoot: "ui/citizen",
    publishedRoot: "docs/gh-pages/citizen",
    snapshot: "docs/gh-pages/citizen/data/citizen.json",
    concerns: "ui/citizen/concerns_v1.json",
    assets:
      "index.html,preset_codec.js,onboarding_funnel.js,first_answer_accelerator.js,unknown_explainability.js,cross_method_stability.js,evidence_trust_panel.js,tailwind_md3.generated.css,tailwind_md3.tokens.json",
    maxSnapshotBytes: 5000000,
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
    if (a === "--source-root") {
      out.sourceRoot = String(argv[i + 1] || "");
      i += 1;
      continue;
    }
    if (a === "--published-root") {
      out.publishedRoot = String(argv[i + 1] || "");
      i += 1;
      continue;
    }
    if (a === "--snapshot") {
      out.snapshot = String(argv[i + 1] || "");
      i += 1;
      continue;
    }
    if (a === "--concerns") {
      out.concerns = String(argv[i + 1] || "");
      i += 1;
      continue;
    }
    if (a === "--assets") {
      out.assets = String(argv[i + 1] || "");
      i += 1;
      continue;
    }
    if (a === "--max-snapshot-bytes") {
      out.maxSnapshotBytes = Number(argv[i + 1] || 0);
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

  if (!Number.isFinite(out.maxSnapshotBytes) || out.maxSnapshotBytes <= 0) {
    throw new Error("--max-snapshot-bytes must be > 0");
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

function toAssetList(csvRaw) {
  const out = [];
  for (const token of String(csvRaw || "").split(",")) {
    const t = String(token || "").trim().replace(/^\.?\//, "");
    if (!t) continue;
    out.push(t);
  }
  return Array.from(new Set(out));
}

function summarize(results) {
  const total = results.length;
  const fail = results.filter((r) => !r.ok).length;
  const pass = total - fail;
  const failedIds = results.filter((r) => !r.ok).map((r) => `${r.section}:${r.id}`);
  return {
    total_checks: total,
    total_pass: pass,
    total_fail: fail,
    failed_ids: failedIds,
  };
}

function readUtf8(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function fileExists(filePath) {
  try {
    return fs.existsSync(filePath);
  } catch (_) {
    return false;
  }
}

function pushResult(results, section, id, ok, error, extra) {
  results.push({
    section,
    id,
    ok: Boolean(ok),
    error: ok ? "" : String(error || "check_failed"),
    ...(extra || {}),
  });
}

function snapshotShapeCheck(snapshotJson) {
  const j = snapshotJson || {};
  const topicsOk = Array.isArray(j.topics);
  const partiesOk = Array.isArray(j.parties);
  const partyTopicPositionsOk = Array.isArray(j.party_topic_positions);
  const metaOk = Boolean(j && j.meta && typeof j.meta === "object");
  const asOfDateOk = Boolean(metaOk && typeof j.meta.as_of_date === "string" && String(j.meta.as_of_date).trim().length > 0);
  const qualityOk = Boolean(metaOk && j.meta.quality && typeof j.meta.quality === "object");
  return {
    ok: topicsOk && partiesOk && partyTopicPositionsOk && asOfDateOk && qualityOk,
    topics_total: topicsOk ? j.topics.length : 0,
    parties_total: partiesOk ? j.parties.length : 0,
    party_topic_positions_total: partyTopicPositionsOk ? j.party_topic_positions.length : 0,
    as_of_date: asOfDateOk ? String(j.meta.as_of_date) : "",
    has_meta_quality: qualityOk,
  };
}

function concernsShapeCheck(concernsJson) {
  const j = concernsJson || {};
  const concernsOk = Array.isArray(j.concerns) && j.concerns.length > 0;
  const packsOk = Array.isArray(j.packs) && j.packs.length > 0;
  return {
    ok: concernsOk && packsOk,
    concerns_total: Array.isArray(j.concerns) ? j.concerns.length : 0,
    packs_total: Array.isArray(j.packs) ? j.packs.length : 0,
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

  const sourceRoot = path.resolve(args.sourceRoot);
  const publishedRoot = path.resolve(args.publishedRoot);
  const snapshotPath = path.resolve(args.snapshot);
  const concernsPath = path.resolve(args.concerns);
  const assets = toAssetList(args.assets);

  const report = {
    generated_at: isoUtcNow(),
    source_root: sourceRoot,
    published_root: publishedRoot,
    snapshot_path: snapshotPath,
    concerns_path: concernsPath,
    assets,
    strict: Boolean(args.strict),
    max_snapshot_bytes: Number(args.maxSnapshotBytes),
    summary: {},
    readiness: {
      status: "failed",
      release_ready: false,
      parity_ok_assets: 0,
      parity_total_assets: assets.length,
      parity_failed_assets: [],
    },
    results: [],
  };

  try {
    for (const assetRel of assets) {
      const srcPath = path.join(sourceRoot, assetRel);
      const pubPath = path.join(publishedRoot, assetRel);
      const srcExists = fileExists(srcPath);
      const pubExists = fileExists(pubPath);

      pushResult(report.results, "asset_source", assetRel, srcExists, "source_asset_missing", {
        path: srcPath,
      });
      pushResult(report.results, "asset_published", assetRel, pubExists, "published_asset_missing", {
        path: pubPath,
      });

      if (!srcExists || !pubExists) {
        report.readiness.parity_failed_assets.push(assetRel);
        continue;
      }

      const srcRaw = readUtf8(srcPath);
      const pubRaw = readUtf8(pubPath);
      const same = srcRaw === pubRaw;
      const diff = same ? { line: 0, source_line: "", published_line: "" } : firstLineDiff(srcRaw, pubRaw);
      pushResult(report.results, "asset_parity", assetRel, same, "asset_parity_mismatch", {
        source_path: srcPath,
        published_path: pubPath,
        source_bytes: Buffer.byteLength(srcRaw, "utf8"),
        published_bytes: Buffer.byteLength(pubRaw, "utf8"),
        source_sha256: sha256Hex(srcRaw),
        published_sha256: sha256Hex(pubRaw),
        first_diff_line: diff.line,
        first_diff_source_line: diff.source_line,
        first_diff_published_line: diff.published_line,
      });

      if (same) {
        report.readiness.parity_ok_assets += 1;
      } else {
        report.readiness.parity_failed_assets.push(assetRel);
      }
    }

    if (!fileExists(snapshotPath)) {
      pushResult(report.results, "snapshot", "exists", false, "snapshot_missing", {
        path: snapshotPath,
      });
    } else {
      const snapshotRaw = readUtf8(snapshotPath);
      const snapshotBytes = Buffer.byteLength(snapshotRaw, "utf8");
      pushResult(
        report.results,
        "snapshot",
        "bytes_budget",
        snapshotBytes <= Number(args.maxSnapshotBytes),
        "snapshot_bytes_over_budget",
        {
          snapshot_bytes: snapshotBytes,
          max_snapshot_bytes: Number(args.maxSnapshotBytes),
        },
      );
      try {
        const snapshotJson = JSON.parse(snapshotRaw);
        const shape = snapshotShapeCheck(snapshotJson);
        pushResult(report.results, "snapshot", "shape", shape.ok, "snapshot_shape_invalid", shape);
      } catch (err) {
        pushResult(report.results, "snapshot", "shape", false, "snapshot_json_invalid", {
          parse_error: String((err && err.message) || err || "json_parse_error"),
        });
      }
    }

    if (!fileExists(concernsPath)) {
      pushResult(report.results, "concerns", "exists", false, "concerns_missing", {
        path: concernsPath,
      });
    } else {
      const concernsRaw = readUtf8(concernsPath);
      try {
        const concernsJson = JSON.parse(concernsRaw);
        const shape = concernsShapeCheck(concernsJson);
        pushResult(report.results, "concerns", "shape", shape.ok, "concerns_shape_invalid", shape);
      } catch (err) {
        pushResult(report.results, "concerns", "shape", false, "concerns_json_invalid", {
          parse_error: String((err && err.message) || err || "json_parse_error"),
        });
      }
    }
  } catch (err) {
    pushResult(report.results, "runtime", "exception", false, "runtime_error", {
      error: String((err && err.stack) || (err && err.message) || err || "runtime_error"),
    });
  }

  report.summary = summarize(report.results);
  const parityFailures = report.results.filter((r) => r.section === "asset_parity" && !r.ok).length;
  report.readiness.parity_total_assets = assets.length;
  report.readiness.parity_ok_assets = assets.length - parityFailures;
  report.readiness.parity_failed_assets = Array.from(
    new Set(report.results.filter((r) => r.section === "asset_parity" && !r.ok).map((r) => r.id)),
  );
  report.readiness.release_ready = report.summary.total_fail === 0;
  report.readiness.status = report.readiness.release_ready ? "ok" : "failed";

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

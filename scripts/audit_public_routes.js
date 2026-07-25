#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require("node:fs");
const path = require("node:path");

const DEFAULT_BASE_URL = "https://votaconlachola.org";
const DEFAULT_TIMEOUT_MS = 30000;
const PAGE_PREFIX_BYTES = 256 * 1024;
const FRAME_PREFIX_BYTES = 128 * 1024;
const ASSET_PREFIX_BYTES = 8 * 1024;

const ROUTE_CONTENT_MARKERS = {
  "/elecciones/andalucia-2026/": [
    "El recibo del agua de Andalucía",
    "Primera ley andaluza de regadíos",
    "Sin hito público localizado",
  ],
};

const ROUTES = [
  "/",
  "/topics/",
  "/actors/",
  "/decisions/",
  "/outcomes/",
  "/methods/",
  "/methods/coverage/",
  "/methods/datasets/",
  "/methods/explorer/",
  "/methods/graph/",
  "/citizen/",
  "/citizen/leaderboards/",
  "/explorer-temas/",
  "/explorer-votaciones/",
  "/explorer-sources/",
  "/explorer-politico/",
  "/explorer/",
  "/graph/",
  "/initiative-lifecycle/",
  "/legal-sanctions/",
  "/elections-behavior/",
  "/elecciones/andalucia-2026/",
  "/parliamentary-accountability/",
  "/parliamentary-accountability/attendance/",
  "/parliamentary-accountability/coalitions/",
  "/parliamentary-accountability/discipline/",
  "/parliamentary-accountability/outcomes/",
  "/people/",
  "/people/xray/",
  "/people/xray/party/",
  "/people/xray/institution/",
  "/people/xray/ambito/",
  "/people/xray/territorio/",
  "/people/xray/cargo/",
  "/policy-outcomes/",
  "/political-positions/",
];

const CRITICAL_ASSETS = [
  "/citizen/data/citizen.json",
  "/citizen/data/citizen_votes.json",
  "/citizen/data/citizen_declared.json",
  "/citizen/data/citizen_comparability.json",
  "/citizen/data/citizen_comparability_votes.json",
  "/citizen/data/citizen_comparability_declared.json",
  "/citizen/data/citizen_lineage.json",
  "/citizen/data/citizen_lineage_votes.json",
  "/citizen/data/citizen_lineage_declared.json",
  "/citizen/data/citizen_snapshot_diff.json",
  "/citizen/data/citizen_snapshot_diff_votes.json",
  "/citizen/data/citizen_snapshot_diff_declared.json",
  "/citizen/data/citizen_ranking_robustness.json",
  "/citizen/data/citizen_ranking_robustness_votes.json",
  "/citizen/data/citizen_ranking_robustness_declared.json",
  "/citizen/data/concern_pack_quality.json",
  "/citizen/data/concern_pack_quality_declared.json",
  "/citizen/data/concern_pack_quality_votes.json",
  "/explorer-temas/data/temas-preview.json",
  "/explorer-votaciones/data/votes-preview.json",
  "/explorer-sources/data/status.json",
  "/explorer-sources/data/ideal.json",
  "/explorer-sources/data/coverage-capacity.json",
  "/explorer-sources/data/coverage-model.json",
  "/graph/data/graph.json",
  "/people/data/profiles.json",
  "/people/data/xray.json",
  "/initiative-lifecycle/data/lifecycle.json",
  "/parliamentary-accountability/data/accountability.json",
  "/policy-outcomes/data/policy-outcomes.json",
  "/legal-sanctions/data/legal-sanctions.json",
  "/elections-behavior/data/elections-behavior.json",
  "/elecciones/andalucia-2026/data/water-receipt.json",
  "/political-positions/data/stances.json",
  "/political-positions/data/party-trajectories.json",
  "/political-positions/data/person-default-rows.json",
  "/political-positions/data/person-search-index.json",
  "/political-positions/data/person-trajectories.json",
  "/political-positions/data/topic-search-index.json",
];

function usage() {
  return [
    "Usage:",
    "  node scripts/audit_public_routes.js [options]",
    "",
    "Options:",
    `  --base-url <url>     Base URL to audit (default: ${DEFAULT_BASE_URL})`,
    `  --timeout-ms <n>     Per-request timeout in milliseconds (default: ${DEFAULT_TIMEOUT_MS})`,
    "  --json-out <path>    Optional JSON report output path",
    "  --help               Show this help",
  ].join("\n");
}

function toString(value) {
  return String(value == null ? "" : value);
}

function toInt(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : fallback;
}

function ensureParentDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function parseArgs(argv) {
  const out = {
    baseUrl: DEFAULT_BASE_URL,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    jsonOut: "",
    help: false,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const arg = toString(argv[i]).trim();
    if (arg === "--help" || arg === "-h") {
      out.help = true;
      continue;
    }
    if (arg === "--base-url") {
      out.baseUrl = toString(argv[i + 1]).trim();
      i += 1;
      continue;
    }
    if (arg === "--timeout-ms") {
      out.timeoutMs = Math.max(1000, toInt(argv[i + 1], DEFAULT_TIMEOUT_MS));
      i += 1;
      continue;
    }
    if (arg === "--json-out") {
      out.jsonOut = toString(argv[i + 1]).trim();
      i += 1;
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }

  if (!out.baseUrl) {
    throw new Error("--base-url must not be empty");
  }
  try {
    // eslint-disable-next-line no-new
    new URL(out.baseUrl);
  } catch (_err) {
    throw new Error(`Invalid --base-url: ${out.baseUrl}`);
  }
  return out;
}

function withProbe(url, suffix) {
  const out = new URL(url);
  out.searchParams.set("__audit", `${Date.now()}-${suffix}`);
  return out.toString();
}

function timeoutSignal(timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new Error(`Timed out after ${timeoutMs}ms`)), timeoutMs);
  return {
    signal: controller.signal,
    clear() {
      clearTimeout(timer);
    },
  };
}

async function readBodyPrefix(response, limitBytes) {
  if (!response.body) {
    return "";
  }
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;

  try {
    while (total < limitBytes) {
      const { done, value } = await reader.read();
      if (done || !value) {
        break;
      }
      const remaining = limitBytes - total;
      const slice = value.length > remaining ? value.subarray(0, remaining) : value;
      chunks.push(Buffer.from(slice));
      total += slice.length;
      if (slice.length < value.length) {
        break;
      }
    }
  } finally {
    try {
      await reader.cancel();
    } catch (_err) {
      // ignore cancellation errors on already-closed streams
    }
  }

  return Buffer.concat(chunks).toString("utf8");
}

async function fetchPrefix(url, timeoutMs, prefixBytes) {
  const timer = timeoutSignal(timeoutMs);
  try {
    const response = await fetch(url, {
      redirect: "follow",
      signal: timer.signal,
      headers: {
        "cache-control": "no-cache",
        pragma: "no-cache",
      },
    });
    const prefix = await readBodyPrefix(response, prefixBytes);
    return {
      ok: true,
      status: response.status,
      finalUrl: response.url,
      contentType: toString(response.headers.get("content-type")).trim(),
      prefix,
    };
  } catch (error) {
    return {
      ok: false,
      error: error && error.message ? String(error.message) : String(error),
      status: 0,
      finalUrl: url,
      contentType: "",
      prefix: "",
    };
  } finally {
    timer.clear();
  }
}

function extractTitle(html) {
  const match = toString(html).match(/<title>([^<]*)<\/title>/i);
  return match ? toString(match[1]).trim() : "";
}

function extractIframeSrc(html) {
  const match = toString(html).match(/<iframe[^>]+src="([^"]+)"/i);
  return match ? toString(match[1]).trim() : "";
}

function hasHiddenNextNotFoundTemplate(html) {
  return toString(html).includes("404: This page could not be found.");
}

function detectIframeEmbedded404(html) {
  const lowered = toString(html).toLowerCase();
  return (
    lowered.includes("<title>404") ||
    lowered.includes("page not found") ||
    lowered.includes("this page could not be found") ||
    lowered.includes("<h1>404") ||
    lowered.includes(">404<")
  );
}

function detectVisibleAppError(html) {
  const lowered = toString(html).toLowerCase();
  return (
    lowered.includes("application error") ||
    lowered.includes("client-side exception has occurred") ||
    lowered.includes("something went wrong")
  );
}

function detectHtmlAsset404(contentType, prefix) {
  if (!toString(contentType).toLowerCase().includes("html")) {
    return false;
  }
  return detectIframeEmbedded404(prefix);
}

async function auditRoute(baseUrl, route, timeoutMs) {
  const url = withProbe(new URL(route, baseUrl).toString(), `route-${encodeURIComponent(route)}`);
  const page = await fetchPrefix(url, timeoutMs, PAGE_PREFIX_BYTES);
  const iframeSrc = page.ok ? extractIframeSrc(page.prefix) : "";
  const iframeUrl = iframeSrc ? new URL(iframeSrc, baseUrl).toString() : "";
  const visibleAppError = page.ok ? detectVisibleAppError(page.prefix) : false;
  const expectedMarkers = ROUTE_CONTENT_MARKERS[route] || [];
  const missingContentMarkers = page.ok
    ? expectedMarkers.filter((marker) => !page.prefix.includes(marker))
    : expectedMarkers;
  let iframe = null;

  if (iframeUrl) {
    const iframeResponse = await fetchPrefix(
      withProbe(iframeUrl, `frame-${encodeURIComponent(route)}`),
      timeoutMs,
      FRAME_PREFIX_BYTES,
    );
    iframe = {
      src: iframeUrl,
      status: iframeResponse.status,
      content_type: iframeResponse.contentType,
      error: iframeResponse.ok ? "" : iframeResponse.error,
      embedded_404: iframeResponse.ok ? detectIframeEmbedded404(iframeResponse.prefix) : false,
      title: iframeResponse.ok ? extractTitle(iframeResponse.prefix) : "",
    };
  }

  const pageOk = page.ok && page.status === 200;
  const iframeOk = !iframe || (iframe.status === 200 && !iframe.embedded_404);
  return {
    route,
    url,
    status: page.status,
    final_url: page.finalUrl,
    content_type: page.contentType,
    title: page.ok ? extractTitle(page.prefix) : "",
    hidden_next_not_found_template: page.ok ? hasHiddenNextNotFoundTemplate(page.prefix) : false,
    visible_app_error: visibleAppError,
    missing_content_markers: missingContentMarkers,
    error: page.ok ? "" : page.error,
    iframe,
    ok: pageOk && iframeOk && !visibleAppError && missingContentMarkers.length === 0,
  };
}

async function auditAsset(baseUrl, assetPath, timeoutMs) {
  const url = withProbe(new URL(assetPath, baseUrl).toString(), `asset-${encodeURIComponent(assetPath)}`);
  const asset = await fetchPrefix(url, timeoutMs, ASSET_PREFIX_BYTES);
  const html404 = asset.ok ? detectHtmlAsset404(asset.contentType, asset.prefix) : false;
  return {
    path: assetPath,
    url,
    status: asset.status,
    final_url: asset.finalUrl,
    content_type: asset.contentType,
    error: asset.ok ? "" : asset.error,
    html_404: html404,
    ok: asset.ok && asset.status === 200 && !html404,
  };
}

function buildSummary(baseUrl, routeResults, assetResults) {
  const routeFailures = routeResults.filter((item) => !item.ok);
  const assetFailures = assetResults.filter((item) => !item.ok);
  const iframeFailures = routeResults.filter((item) => item.iframe && (item.iframe.status !== 200 || item.iframe.embedded_404));

  return {
    checked_at: new Date().toISOString(),
    base_url: baseUrl,
    route_total: routeResults.length,
    route_failures: routeFailures.length,
    iframe_failures: iframeFailures.length,
    asset_total: assetResults.length,
    asset_failures: assetFailures.length,
    ok: routeFailures.length === 0 && assetFailures.length === 0,
  };
}

function printSummary(summary, routeResults, assetResults) {
  console.log(`[public-route-audit] base=${summary.base_url}`);
  console.log(
    `[public-route-audit] routes=${summary.route_total} failures=${summary.route_failures} frames=${summary.iframe_failures} assets=${summary.asset_total} asset_failures=${summary.asset_failures}`,
  );

  const routeFailures = routeResults.filter((item) => !item.ok);
  if (routeFailures.length) {
    console.log("[public-route-audit] route failures:");
    for (const item of routeFailures) {
      const frame = item.iframe ? ` iframe=${item.iframe.status}${item.iframe.embedded_404 ? " embedded404" : ""}` : "";
      const markerReason = item.missing_content_markers.length
        ? `missing_markers:${item.missing_content_markers.join("|")}`
        : "";
      const reason = item.error || (item.visible_app_error ? "visible_app_error" : markerReason);
      console.log(`  - ${item.route} status=${item.status}${frame}${reason ? ` reason=${reason}` : ""}`);
    }
  }

  const assetFailures = assetResults.filter((item) => !item.ok);
  if (assetFailures.length) {
    console.log("[public-route-audit] asset failures:");
    for (const item of assetFailures) {
      const reason = item.error || (item.html_404 ? "html_404" : "");
      console.log(`  - ${item.path} status=${item.status}${reason ? ` reason=${reason}` : ""}`);
    }
  }
}

async function main() {
  const args = parseArgs(process.argv);
  const routeResults = [];
  const assetResults = [];

  for (const route of ROUTES) {
    routeResults.push(await auditRoute(args.baseUrl, route, args.timeoutMs));
  }
  for (const assetPath of CRITICAL_ASSETS) {
    assetResults.push(await auditAsset(args.baseUrl, assetPath, args.timeoutMs));
  }

  const summary = buildSummary(args.baseUrl, routeResults, assetResults);
  const report = {
    summary,
    routes: routeResults,
    assets: assetResults,
  };

  if (args.jsonOut) {
    ensureParentDir(args.jsonOut);
    fs.writeFileSync(args.jsonOut, `${JSON.stringify(report, null, 2)}\n`);
  }

  printSummary(summary, routeResults, assetResults);

  if (!summary.ok) {
    process.exitCode = 1;
  }
}

if (require.main === module) {
  try {
    const args = parseArgs(process.argv);
    if (args.help) {
      console.log(usage());
      process.exit(0);
    }
  } catch (error) {
    console.error(String(error && error.message ? error.message : error));
    console.error("");
    console.error(usage());
    process.exit(1);
  }

  main().catch((error) => {
    console.error(error && error.stack ? error.stack : String(error));
    process.exit(1);
  });
}

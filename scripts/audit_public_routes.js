#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { pathToFileURL } = require("node:url");

const DEFAULT_BASE_URL = "https://votaconlachola.org";
const DEFAULT_TIMEOUT_MS = 30000;
const PAGE_PREFIX_BYTES = 256 * 1024;
const FRAME_PREFIX_BYTES = 128 * 1024;
const ASSET_PREFIX_BYTES = 8 * 1024;
const REPO_ROOT = path.resolve(__dirname, "..");
const POLICY_OUTCOMES_ASSET_PATH = "/policy-outcomes/data/policy-outcomes.json";
const POLICY_OUTCOMES_LOCAL_ARTIFACT = path.join(
  REPO_ROOT,
  "ui/site/public/policy-outcomes/data/policy-outcomes.json",
);
const POLICY_OUTCOMES_CONTRACT_MODULE = path.join(
  REPO_ROOT,
  "ui/site/app/policy-outcomes/status-contract.mjs",
);

const ROUTE_CONTENT_MARKERS = {
  "/elecciones/andalucia-2026/": [
    "El recibo del agua de Andalucía",
    "Primera ley andaluza de regadíos",
    "Sin hito público localizado",
  ],
  "/promises/": [
    "Promesas con evidencia",
    "Lo dicho no es lo cumplido",
    "Veinte compromisos, veinte anclas",
  ],
  "/comparisons/": [
    "Lo dicho frente a lo observado",
    "Comparar no es sentenciar",
    "Ranking oculto",
  ],
  "/spending/": [
    "Dinero público con evidencia",
    "Adjudicado no significa pagado",
    "Veinte adjudicaciones reales, identidad pública intacta",
  ],
  "/agreements/": [
    "Acuerdos y reuniones con evidencia",
    "Reunión no significa influencia",
    "Resúmenes oficiales, sin completar huecos",
  ],
  "/geopolitics/": [
    "Geopolítica sin rellenar los huecos",
    "Autorización no significa tratado en vigor",
    "Acciones oficiales y estados desconocidos a la vista",
  ],
  "/indicators/": [
    "Lo que cambió, sin inventar por qué",
    "Un indicador no reparte mérito ni culpa",
    "Toda la geografía española del slice",
  ],
  "/actor-graph/": [
    "Quién aparece conectado con qué",
    "Mismo nombre no significa misma persona",
    "Una ruta del grafo no prueba corrupción",
  ],
  "/policy-outcomes/": [
    "Un candidato metodológico pendiente",
    "0 vínculos de resultado validados",
    "20 acciones × 1 serie elegible = 20 pares",
    "No se eliminó ni seudonimizó ningún nombre público",
    "La firma de escala no cubre este paquete",
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
  "/obstruction-tracker/",
  "/transparency/",
  "/promises/",
  "/comparisons/",
  "/spending/",
  "/agreements/",
  "/geopolitics/",
  "/indicators/",
  "/actor-graph/",
  "/explorer-politico/",
  "/explorer/",
  "/graph/",
  "/initiative-lifecycle/",
  "/legal-sanctions/",
  "/elections-behavior/",
  "/calendario-electoral/",
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
  "/legacy/citizen/data/citizen_comparability.json",
  "/legacy/citizen/data/citizen_comparability_votes.json",
  "/legacy/citizen/data/citizen_comparability_declared.json",
  "/legacy/citizen/data/citizen_lineage.json",
  "/legacy/citizen/data/citizen_lineage_votes.json",
  "/legacy/citizen/data/citizen_lineage_declared.json",
  "/legacy/citizen/data/citizen_snapshot_diff.json",
  "/legacy/citizen/data/citizen_snapshot_diff_votes.json",
  "/legacy/citizen/data/citizen_snapshot_diff_declared.json",
  "/legacy/citizen/data/citizen_ranking_robustness.json",
  "/legacy/citizen/data/citizen_ranking_robustness_votes.json",
  "/legacy/citizen/data/citizen_ranking_robustness_declared.json",
  "/citizen/data/concern_pack_quality.json",
  "/citizen/data/concern_pack_quality_declared.json",
  "/citizen/data/concern_pack_quality_votes.json",
  "/explorer-temas/data/temas-preview.json",
  "/explorer-votaciones/data/votes-preview.json",
  "/explorer-sources/data/status.json",
  "/obstruction-tracker/data/obstructions.json",
  "/transparency/data/transparency.json",
  "/promises/data/bng-2023.json",
  "/comparisons/data/comparisons.json",
  "/spending/data/placsp-sample.json",
  "/agreements/data/moncloa-sample.json",
  "/geopolitics/data/moncloa-sample.json",
  "/indicators/data/eurostat-gdp-es.json",
  "/actor-graph/data/graph.json",
  "/explorer-sources/data/ideal.json",
  "/legacy/graph/data/coverage-capacity.json",
  "/legacy/graph/data/coverage-model.json",
  "/graph/data/graph.json",
  "/people/data/profiles.json",
  "/people/data/xray.json",
  "/initiative-lifecycle/data/lifecycle.json",
  "/parliamentary-accountability/data/accountability.json",
  "/policy-outcomes/data/policy-outcomes.json",
  "/legal-sanctions/data/legal-sanctions.json",
  "/elections-behavior/data/elections-behavior.json",
  "/calendario-electoral/data/election-calendar.json",
  "/elecciones/andalucia-2026/data/accountability.json",
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

async function fetchBytes(url, timeoutMs) {
  const timer = timeoutSignal(timeoutMs);
  try {
    const response = await fetch(url, {
      redirect: "follow",
      signal: timer.signal,
      headers: { "cache-control": "no-cache", pragma: "no-cache" },
    });
    const bytes = Buffer.from(await response.arrayBuffer());
    return {
      ok: true,
      status: response.status,
      finalUrl: response.url,
      contentType: toString(response.headers.get("content-type")).trim(),
      bytes,
    };
  } catch (error) {
    return {
      ok: false,
      error: error && error.message ? String(error.message) : String(error),
      status: 0,
      finalUrl: url,
      contentType: "",
      bytes: Buffer.alloc(0),
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

async function auditPolicyOutcomesAsset(baseUrl, timeoutMs) {
  const contract = await import(pathToFileURL(POLICY_OUTCOMES_CONTRACT_MODULE).href);
  const url = withProbe(
    new URL(POLICY_OUTCOMES_ASSET_PATH, baseUrl).toString(),
    "asset-policy-outcomes-exact",
  );
  const asset = await fetchBytes(url, timeoutMs);
  const prefix = asset.bytes.subarray(0, ASSET_PREFIX_BYTES).toString("utf8");
  const html404 = asset.ok ? detectHtmlAsset404(asset.contentType, prefix) : false;
  const sha256 = crypto.createHash("sha256").update(asset.bytes).digest("hex");
  let expectedSha256 = "";
  let status = null;
  let manifest = null;
  let manifestResponse = null;
  let manifestSha256 = "";
  let localManifest = null;
  let localManifestRaw = null;
  const contractErrors = [];
  try {
    const localStatusRaw = fs.readFileSync(POLICY_OUTCOMES_LOCAL_ARTIFACT);
    expectedSha256 = crypto.createHash("sha256").update(localStatusRaw).digest("hex");
    const localStatus = JSON.parse(localStatusRaw.toString("utf8"));
    if (!contract.isSafePolicyOutcomesManifestPath(localStatus?.evidence_package?.manifest_path)) {
      throw new Error("unsafe local manifest path");
    }
    const localManifestPath = path.join(
      REPO_ROOT,
      "ui/site/public",
      ...localStatus.evidence_package.manifest_path.split("/").filter(Boolean),
    );
    localManifestRaw = fs.readFileSync(localManifestPath);
    localManifest = JSON.parse(localManifestRaw.toString("utf8"));
  } catch (error) {
    contractErrors.push(`local_expected_artifact:${error.message}`);
  }
  try {
    status = JSON.parse(asset.bytes.toString("utf8"));
  } catch (error) {
    contractErrors.push(`invalid_json:${error.message}`);
  }
  if (expectedSha256 && sha256 !== expectedSha256) contractErrors.push("exact_sha256_mismatch");

  const evidenceAssets = [];
  const observedAssets = {};
  let preliminaryValidation = null;
  if (status && contract.isSafePolicyOutcomesManifestPath(status?.evidence_package?.manifest_path)) {
    const publicManifestUrl = new URL(status.evidence_package.manifest_path, baseUrl).toString();
    manifestResponse = await fetchBytes(
      withProbe(publicManifestUrl, "policy-outcomes-evidence-manifest"),
      timeoutMs,
    );
    manifestSha256 = crypto.createHash("sha256").update(manifestResponse.bytes).digest("hex");
    try {
      manifest = JSON.parse(manifestResponse.bytes.toString("utf8"));
    } catch (error) {
      contractErrors.push(`manifest_invalid_json:${error.message}`);
    }
    if (localManifestRaw && manifestSha256 !== crypto.createHash("sha256").update(localManifestRaw).digest("hex")) {
      contractErrors.push("manifest_exact_sha256_mismatch");
    }
    if (manifest && localManifest) {
      const localCanonical = JSON.stringify(localManifest);
      const remoteCanonical = JSON.stringify(manifest);
      if (localCanonical !== remoteCanonical) contractErrors.push("manifest_local_remote_mismatch");
    }

    if (status && manifest) {
      preliminaryValidation = contract.validatePolicyOutcomesPackageContract({
        status,
        manifest,
        statusBytes: asset.bytes.length,
        statusSha256: sha256,
        manifestSha256,
      });
      if (!preliminaryValidation.ok) contractErrors.push(...preliminaryValidation.errors);
    }

    if (preliminaryValidation?.ok) {
      for (const [key, fact] of Object.entries(manifest.assets)) {
        const safeAssetPath = contract.resolvePolicyOutcomesEvidenceAssetPath(
          status.evidence_package.manifest_path,
          fact.path,
        );
        if (!safeAssetPath) {
          contractErrors.push(`manifest.assets.${key}:unsafe_path`);
          continue;
        }
        const assetUrl = new URL(safeAssetPath, baseUrl).toString();
        const response = await fetchBytes(
          withProbe(assetUrl, `policy-outcomes-evidence-${encodeURIComponent(key)}`),
          timeoutMs,
        );
        const observedSha256 = crypto.createHash("sha256").update(response.bytes).digest("hex");
        observedAssets[key] = { bytes: response.bytes.length, sha256: observedSha256 };
        const assetPrefix = response.bytes.subarray(0, ASSET_PREFIX_BYTES).toString("utf8");
        const assetHtml404 = response.ok
          ? detectHtmlAsset404(response.contentType, assetPrefix)
          : false;
        evidenceAssets.push({
          key,
          path: fact.path,
          url: assetUrl,
          status: response.status,
          bytes: response.bytes.length,
          sha256: observedSha256,
          expected_bytes: fact.bytes,
          expected_sha256: fact.sha256,
          error: response.ok ? "" : response.error,
          html_404: assetHtml404,
          ok: response.ok
            && response.status === 200
            && !assetHtml404
            && response.bytes.length === fact.bytes
            && observedSha256 === fact.sha256,
        });
      }
    }
  } else if (status) {
    contractErrors.push("unsafe_manifest_path");
  }

  if (preliminaryValidation?.ok) {
    const validation = contract.validatePolicyOutcomesPackage({
      status,
      manifest,
      statusBytes: asset.bytes.length,
      statusSha256: sha256,
      manifestSha256,
      observedAssets,
    });
    contractErrors.push(...validation.errors);
  }
  if (!manifestResponse?.ok || manifestResponse.status !== 200) {
    contractErrors.push(`manifest_http_${manifestResponse?.status || 0}`);
  }
  if (evidenceAssets.some((item) => !item.ok)) contractErrors.push("evidence_asset_integrity_failure");
  return {
    path: POLICY_OUTCOMES_ASSET_PATH,
    url,
    status: asset.status,
    final_url: asset.finalUrl,
    content_type: asset.contentType,
    bytes: asset.bytes.length,
    sha256,
    expected_sha256: expectedSha256,
    evidence_manifest: {
      path: status?.evidence_package?.manifest_path || "",
      status: manifestResponse?.status || 0,
      bytes: manifestResponse?.bytes?.length || 0,
      sha256: manifestSha256,
      expected_sha256: contract.CURRENT_POLICY_OUTCOMES_MANIFEST_SHA256,
      ok: Boolean(manifestResponse?.ok)
        && manifestResponse.status === 200
        && manifestSha256 === contract.CURRENT_POLICY_OUTCOMES_MANIFEST_SHA256,
    },
    evidence_assets: evidenceAssets,
    contract_errors: contractErrors,
    error: asset.ok ? "" : asset.error,
    html_404: html404,
    ok: asset.ok && asset.status === 200 && !html404 && contractErrors.length === 0,
  };
}

async function auditAsset(baseUrl, assetPath, timeoutMs) {
  if (assetPath === POLICY_OUTCOMES_ASSET_PATH) {
    return auditPolicyOutcomesAsset(baseUrl, timeoutMs);
  }
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

async function auditObstructionEvidence(baseUrl, timeoutMs) {
  const manifestPath = "/obstruction-tracker/evidence/manifest.json";
  const manifestUrl = withProbe(new URL(manifestPath, baseUrl).toString(), "obstruction-evidence-manifest");
  const manifestResponse = await fetchBytes(manifestUrl, timeoutMs);
  if (!manifestResponse.ok || manifestResponse.status !== 200) {
    return {
      manifest: { path: manifestPath, status: manifestResponse.status, error: manifestResponse.error || "", ok: false },
      files: [],
    };
  }

  let manifest;
  try {
    manifest = JSON.parse(manifestResponse.bytes.toString("utf8"));
  } catch (error) {
    return {
      manifest: { path: manifestPath, status: manifestResponse.status, error: `invalid_json:${error.message}`, ok: false },
      files: [],
    };
  }

  const items = Array.isArray(manifest.files) ? manifest.files : [];
  const results = new Array(items.length);
  let cursor = 0;
  const workerCount = Math.min(8, Math.max(items.length, 1));
  async function worker() {
    while (cursor < items.length) {
      const index = cursor;
      cursor += 1;
      const item = items[index];
      const publicFile = toString(item.public_file).trim();
      const assetPath = `/obstruction-tracker/evidence/${encodeURIComponent(publicFile)}`;
      const response = await fetchBytes(withProbe(new URL(assetPath, baseUrl).toString(), `obstruction-evidence-${index}`), timeoutMs);
      const sha256 = crypto.createHash("sha256").update(response.bytes).digest("hex");
      const expectedBytes = toInt(item.public_bytes, -1);
      const expectedSha256 = toString(item.public_sha256).trim();
      results[index] = {
        path: assetPath,
        source_path: toString(item.source_path).trim(),
        status: response.status,
        content_type: response.contentType,
        bytes: response.bytes.length,
        sha256,
        expected_bytes: expectedBytes,
        expected_sha256: expectedSha256,
        error: response.ok ? "" : response.error,
        ok: response.ok && response.status === 200 && response.bytes.length === expectedBytes && sha256 === expectedSha256,
      };
    }
  }
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return {
    manifest: {
      path: manifestPath,
      status: manifestResponse.status,
      schema_version: toString(manifest.schema_version),
      declared_files_total: toInt(manifest.summary?.files_total, -1),
      files_total: items.length,
      error: "",
      ok: manifest.schema_version === "obstruction_evidence_bundle_v1" && toInt(manifest.summary?.files_total, -1) === items.length,
    },
    files: results,
  };
}

function buildSummary(baseUrl, routeResults, assetResults, obstructionEvidence) {
  const routeFailures = routeResults.filter((item) => !item.ok);
  const assetFailures = assetResults.filter((item) => !item.ok);
  const iframeFailures = routeResults.filter((item) => item.iframe && (item.iframe.status !== 200 || item.iframe.embedded_404));
  const evidenceFailures = obstructionEvidence.files.filter((item) => !item.ok);
  const evidenceManifestFailures = obstructionEvidence.manifest.ok ? 0 : 1;

  return {
    checked_at: new Date().toISOString(),
    base_url: baseUrl,
    route_total: routeResults.length,
    route_failures: routeFailures.length,
    iframe_failures: iframeFailures.length,
    asset_total: assetResults.length,
    asset_failures: assetFailures.length,
    obstruction_evidence_total: obstructionEvidence.files.length,
    obstruction_evidence_failures: evidenceFailures.length + evidenceManifestFailures,
    ok: routeFailures.length === 0 && assetFailures.length === 0 && evidenceFailures.length === 0 && evidenceManifestFailures === 0,
  };
}

function printSummary(summary, routeResults, assetResults, obstructionEvidence) {
  console.log(`[public-route-audit] base=${summary.base_url}`);
  console.log(
    `[public-route-audit] routes=${summary.route_total} failures=${summary.route_failures} frames=${summary.iframe_failures} assets=${summary.asset_total} asset_failures=${summary.asset_failures} obstruction_evidence=${summary.obstruction_evidence_total} evidence_failures=${summary.obstruction_evidence_failures}`,
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
      const reason = item.error
        || (item.html_404 ? "html_404" : "")
        || (item.contract_errors?.length ? item.contract_errors.join("|") : "");
      console.log(`  - ${item.path} status=${item.status}${reason ? ` reason=${reason}` : ""}`);
    }
  }
  const evidenceFailures = obstructionEvidence.files.filter((item) => !item.ok);
  if (!obstructionEvidence.manifest.ok || evidenceFailures.length) {
    console.log("[public-route-audit] obstruction evidence failures:");
    if (!obstructionEvidence.manifest.ok) {
      console.log(`  - ${obstructionEvidence.manifest.path} status=${obstructionEvidence.manifest.status} reason=${obstructionEvidence.manifest.error || "manifest_contract"}`);
    }
    for (const item of evidenceFailures) {
      console.log(`  - ${item.path} status=${item.status} reason=${item.error || "bytes_or_sha256_mismatch"}`);
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
  const obstructionEvidence = await auditObstructionEvidence(args.baseUrl, args.timeoutMs);

  const summary = buildSummary(args.baseUrl, routeResults, assetResults, obstructionEvidence);
  const report = {
    summary,
    routes: routeResults,
    assets: assetResults,
    obstruction_evidence: obstructionEvidence,
  };

  if (args.jsonOut) {
    ensureParentDir(args.jsonOut);
    fs.writeFileSync(args.jsonOut, `${JSON.stringify(report, null, 2)}\n`);
  }

  printSummary(summary, routeResults, assetResults, obstructionEvidence);

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

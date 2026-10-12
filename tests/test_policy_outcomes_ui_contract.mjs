import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  CURRENT_POLICY_OUTCOMES_MANIFEST_SHA256,
  resolvePolicyOutcomesEvidenceAssetPath,
  validatePolicyOutcomesPackage,
} from "../ui/site/app/policy-outcomes/status-contract.mjs";
import {
  POLICY_OUTCOMES_RUNTIME_STATUS_PATH,
  verifyPolicyOutcomesRuntimePackage,
} from "../ui/site/app/policy-outcomes/runtime-verification.mjs";


const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(TEST_DIR, "..");
const PUBLIC_ROOT = path.join(REPO_ROOT, "ui/site/public");
const STATUS_PATH = path.join(PUBLIC_ROOT, "policy-outcomes/data/policy-outcomes.json");
const PAGE_SOURCE_PATH = path.join(REPO_ROOT, "ui/site/app/policy-outcomes/page.js");
const RUNTIME_GATE_SOURCE_PATH = path.join(
  REPO_ROOT,
  "ui/site/app/policy-outcomes/PolicyOutcomesRuntimeGate.js",
);
const ROUTE_AUDITOR_PATH = path.join(REPO_ROOT, "scripts/audit_public_routes.js");

if (!globalThis.crypto?.subtle) globalThis.crypto = crypto.webcrypto;

function sha256(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function loadFixture() {
  const statusRaw = fs.readFileSync(STATUS_PATH);
  const status = JSON.parse(statusRaw.toString("utf8"));
  const manifestPath = path.join(PUBLIC_ROOT, ...status.evidence_package.manifest_path.split("/").filter(Boolean));
  const manifestRaw = fs.readFileSync(manifestPath);
  const manifest = JSON.parse(manifestRaw.toString("utf8"));
  const packageDir = path.dirname(manifestPath);
  const observedAssets = {};
  for (const [key, fact] of Object.entries(manifest.assets)) {
    const bytes = fs.readFileSync(path.join(packageDir, ...fact.path.split("/")));
    observedAssets[key] = { bytes: bytes.length, sha256: sha256(bytes) };
  }
  return {
    status,
    manifest,
    statusRaw,
    manifestRaw,
    packageDir,
    observedAssets,
  };
}

function validate(fixture, overrides = {}) {
  const status = overrides.status || fixture.status;
  const manifest = overrides.manifest || fixture.manifest;
  const statusRaw = overrides.statusRaw || fixture.statusRaw;
  const manifestRaw = overrides.manifestRaw || fixture.manifestRaw;
  return validatePolicyOutcomesPackage({
    status,
    manifest,
    statusBytes: statusRaw.length,
    statusSha256: sha256(statusRaw),
    manifestSha256: sha256(manifestRaw),
    observedAssets: overrides.observedAssets || fixture.observedAssets,
  });
}

function runtimeFixtureMap(overrides = {}) {
  const files = new Map();
  const statusRaw = overrides.statusRaw || fixture.statusRaw;
  const manifestRaw = overrides.manifestRaw || fixture.manifestRaw;
  files.set(POLICY_OUTCOMES_RUNTIME_STATUS_PATH, statusRaw);
  files.set(fixture.status.evidence_package.manifest_path, manifestRaw);
  for (const fact of Object.values(fixture.manifest.assets)) {
    const publicPath = resolvePolicyOutcomesEvidenceAssetPath(
      fixture.status.evidence_package.manifest_path,
      fact.path,
    );
    files.set(publicPath, fs.readFileSync(path.join(fixture.packageDir, fact.path)));
  }
  for (const [publicPath, bytes] of Object.entries(overrides.files || {})) {
    files.set(publicPath, bytes);
  }
  return files;
}

function runtimeFetch(files, calls) {
  return async (publicPath, options) => {
    calls.push({ publicPath, options });
    const bytes = files.get(publicPath);
    if (!bytes) {
      return {
        ok: false,
        status: 404,
        redirected: false,
        async arrayBuffer() { return new ArrayBuffer(0); },
      };
    }
    const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    return {
      ok: true,
      status: 200,
      redirected: false,
      async arrayBuffer() {
        return view.buffer.slice(view.byteOffset, view.byteOffset + view.byteLength);
      },
    };
  };
}

const fixture = loadFixture();

test("current real status, pinned manifest, and every evidence asset validate", () => {
  const result = validate(fixture);
  assert.equal(result.ok, true, result.errors.join("\n"));
  assert.equal(sha256(fixture.manifestRaw), CURRENT_POLICY_OUTCOMES_MANIFEST_SHA256);
  assert.equal(fixture.status.pipeline.pending_methodological_candidates_disclosed, 1);
  assert.equal(fixture.status.pipeline.validated_outcome_links, 0);
  assert.equal(fixture.status.selected_inputs.relationship_state,
    "selected_together_in_one_pending_methodological_candidate");
});

test("browser runtime verifier fetches and hashes the complete real package", async () => {
  const calls = [];
  const result = await verifyPolicyOutcomesRuntimePackage({
    fetchImpl: runtimeFetch(runtimeFixtureMap(), calls),
  });
  assert.equal(result.ok, true, result.errors.join("\n"));
  assert.equal(result.verifiedAssets, 17);
  assert.equal(result.manifestSha256, CURRENT_POLICY_OUTCOMES_MANIFEST_SHA256);
  assert.equal(calls.length, 19);
  assert.equal(calls[0].publicPath, POLICY_OUTCOMES_RUNTIME_STATUS_PATH);
  assert.equal(calls[1].publicPath, fixture.status.evidence_package.manifest_path);
  for (const call of calls) {
    assert.equal(call.options.cache, "no-store");
    assert.equal(call.options.credentials, "same-origin");
    assert.equal(call.options.redirect, "error");
  }
});

test("browser runtime verifier fails closed on one changed evidence byte", async () => {
  const fact = fixture.manifest.assets.semantic_evidence;
  const publicPath = resolvePolicyOutcomesEvidenceAssetPath(
    fixture.status.evidence_package.manifest_path,
    fact.path,
  );
  const changed = Buffer.from(fs.readFileSync(path.join(fixture.packageDir, fact.path)));
  changed[0] ^= 1;
  const result = await verifyPolicyOutcomesRuntimePackage({
    fetchImpl: runtimeFetch(runtimeFixtureMap({ files: { [publicPath]: changed } }), []),
  });
  assert.equal(result.ok, false);
  assert.equal(result.verifiedAssets, 17);
  assert.ok(result.errors.includes("observed_assets.semantic_evidence:sha256"));
});

test("browser runtime verifier rejects an unsafe manifest path before another fetch", async () => {
  const status = clone(fixture.status);
  status.evidence_package.manifest_path = "/policy-outcomes/evidence/../manifest.json";
  const statusRaw = Buffer.from(`${JSON.stringify(status)}\n`, "utf8");
  const calls = [];
  const files = new Map([[POLICY_OUTCOMES_RUNTIME_STATUS_PATH, statusRaw]]);
  const result = await verifyPolicyOutcomesRuntimePackage({
    fetchImpl: runtimeFetch(files, calls),
  });
  assert.equal(result.ok, false);
  assert.deepEqual(result.errors, ["runtime_manifest:unsafe_path"]);
  assert.deepEqual(calls.map((call) => call.publicPath), [POLICY_OUTCOMES_RUNTIME_STATUS_PATH]);
});

test("public closure assets expose exact 20-by-1 bounded universe", () => {
  const actionFact = fixture.manifest.assets.action_candidate_universe;
  const eligibleFact = fixture.manifest.assets.eligible_indicator_series_universe;
  const actions = JSON.parse(fs.readFileSync(path.join(fixture.packageDir, actionFact.path), "utf8"));
  const eligible = JSON.parse(fs.readFileSync(path.join(fixture.packageDir, eligibleFact.path), "utf8"));
  assert.equal(actions.length, fixture.status.bounded_universe.action_candidates);
  assert.equal(eligible.length, fixture.status.bounded_universe.eligible_indicator_series);
  assert.equal(actions.length * eligible.length, fixture.status.bounded_universe.candidate_pairs);
  assert.equal(actionFact.sha256, fixture.status.bounded_universe.action_universe_sha256);
  assert.equal(eligibleFact.sha256, fixture.status.bounded_universe.eligible_indicator_series_sha256);
  assert.equal(fixture.status.bounded_universe.all_possible_action_indicator_pairs_searched, false);
});

test("extra and missing status keys fail closed", () => {
  const extra = clone(fixture.status);
  extra.unexpected = true;
  assert.equal(validate(fixture, { status: extra }).ok, false);
  const missing = clone(fixture.status);
  delete missing.claim_boundary;
  assert.equal(validate(fixture, { status: missing }).ok, false);
});

test("arrays and candidate-detail leakage fail closed", () => {
  const arrayLeak = clone(fixture.status);
  arrayLeak.contract_date = [];
  const arrayResult = validate(fixture, { status: arrayLeak });
  assert.equal(arrayResult.ok, false);
  assert.ok(arrayResult.errors.some((error) => error.includes("array_forbidden")));

  const detailLeak = clone(fixture.status);
  detailLeak.selected_inputs.official_member_name = "MARÍA PILAR LLOP CUENCA";
  const detailResult = validate(fixture, { status: detailLeak });
  assert.equal(detailResult.ok, false);
  assert.ok(detailResult.errors.some((error) => error.includes("detail_key_forbidden")));
});

test("internal candidate and actor identifiers fail closed", () => {
  const internalId = clone(fixture.status);
  internalId.selected_inputs.relationship_state = "vclc:outcome-link:000000000000000000000000";
  const result = validate(fixture, { status: internalId });
  assert.equal(result.ok, false);
  assert.ok(result.errors.some((error) => error.includes("internal_detail_value_forbidden")));
});

test("arbitrary well-formed validation hash, count, and date fail closed", () => {
  const hashDrift = clone(fixture.status);
  hashDrift.validation_identity.deterministic_fingerprint = "0".repeat(64);
  assert.equal(validate(fixture, { status: hashDrift }).ok, false);

  const countDrift = clone(fixture.status);
  countDrift.validation_identity.check_count += 1;
  assert.equal(validate(fixture, { status: countDrift }).ok, false);

  const dateDrift = clone(fixture.status);
  dateDrift.contract_date = "2099-01-01T00:00:00Z";
  assert.equal(validate(fixture, { status: dateDrift }).ok, false);
});

test("source drift and manifest-status mismatch fail closed", () => {
  const sourceDrift = clone(fixture.status);
  sourceDrift.selected_inputs.senate_vote.normalized_record_sha256 = "1".repeat(64);
  assert.equal(validate(fixture, { status: sourceDrift }).ok, false);

  const manifestMismatch = clone(fixture.manifest);
  manifestMismatch.status.sha256 = "2".repeat(64);
  const manifestRaw = Buffer.from(`${JSON.stringify(manifestMismatch)}\n`, "utf8");
  const result = validate(fixture, { manifest: manifestMismatch, manifestRaw });
  assert.equal(result.ok, false);
  assert.ok(result.errors.includes("manifest:release_identity"));
  assert.ok(result.errors.includes("status:sha256_mismatch"));
});

test("denying disclosed pending candidate fails closed", () => {
  const denial = clone(fixture.status);
  denial.pipeline.pending_methodological_candidates_disclosed = 0;
  const result = validate(fixture, { status: denial });
  assert.equal(result.ok, false);
  assert.ok(result.errors.includes("status.pipeline.pending_methodological_candidates_disclosed"));
});

test("any evidence asset byte or hash drift fails closed", () => {
  const observed = clone(fixture.observedAssets);
  observed.action_candidate_universe.bytes -= 1;
  observed.semantic_evidence.sha256 = "f".repeat(64);
  const result = validate(fixture, { observedAssets: observed });
  assert.equal(result.ok, false);
  assert.ok(result.errors.includes("observed_assets.action_candidate_universe:bytes"));
  assert.ok(result.errors.includes("observed_assets.semantic_evidence:sha256"));
});

test("missing, extra, or traversal evidence observations fail closed", () => {
  const missing = clone(fixture.observedAssets);
  delete missing.action_candidate_universe;
  const missingResult = validate(fixture, { observedAssets: missing });
  assert.equal(missingResult.ok, false);
  assert.ok(missingResult.errors.includes("observed_assets:keys"));
  assert.ok(missingResult.errors.includes("observed_assets.action_candidate_universe:missing"));

  const extra = clone(fixture.observedAssets);
  extra.unmanifested = { bytes: 1, sha256: "0".repeat(64) };
  const extraResult = validate(fixture, { observedAssets: extra });
  assert.equal(extraResult.ok, false);
  assert.ok(extraResult.errors.includes("observed_assets:keys"));

  const omittedResult = validatePolicyOutcomesPackage({
    status: fixture.status,
    manifest: fixture.manifest,
    statusBytes: fixture.statusRaw.length,
    statusSha256: sha256(fixture.statusRaw),
    manifestSha256: sha256(fixture.manifestRaw),
  });
  assert.equal(omittedResult.ok, false);
  assert.ok(omittedResult.errors.includes("observed_assets:object_required"));

  const manifestPath = fixture.status.evidence_package.manifest_path;
  assert.equal(
    resolvePolicyOutcomesEvidenceAssetPath(manifestPath, "assets/action-candidate-universe.canonical.json"),
    `${path.posix.dirname(manifestPath)}/assets/action-candidate-universe.canonical.json`,
  );
  assert.equal(resolvePolicyOutcomesEvidenceAssetPath(manifestPath, "../manifest.json"), null);
  assert.equal(resolvePolicyOutcomesEvidenceAssetPath(manifestPath, "assets/../manifest.json"), null);
  assert.equal(resolvePolicyOutcomesEvidenceAssetPath("/policy-outcomes/evidence/not-a-hash/manifest.json", "assets/a.json"), null);
});

test("extra or missing manifest keys invalidate pinned release", () => {
  const extra = clone(fixture.manifest);
  extra.extra = true;
  const extraRaw = Buffer.from(`${JSON.stringify(extra)}\n`, "utf8");
  assert.equal(validate(fixture, { manifest: extra, manifestRaw: extraRaw }).ok, false);

  const missing = clone(fixture.manifest);
  delete missing.authentication;
  const missingRaw = Buffer.from(`${JSON.stringify(missing)}\n`, "utf8");
  assert.equal(validate(fixture, { manifest: missing, manifestRaw: missingRaw }).ok, false);
});

test("invalid page state returns before any candidate or source facts render", () => {
  const source = fs.readFileSync(PAGE_SOURCE_PATH, "utf8");
  const guard = source.indexOf("if (!feedIsValid)");
  const verifiedFacts = source.indexOf("20 acciones × 1 serie elegible = 20 pares");
  assert.ok(guard > 0);
  assert.ok(verifiedFacts > guard);
  const failClosedBranch = source.slice(guard, source.indexOf("const pipeline", guard));
  assert.match(failClosedBranch, /No publica conteos, candidatos, fuentes ni conclusiones/u);
  assert.doesNotMatch(
    failClosedBranch,
    /20 acciones|264|Senado|Eurostat|candidato metodológico pendiente/u,
  );
  assert.doesNotMatch(
    source.slice(0, guard),
    /Un candidato metodológico pendiente|cero vínculos validados/u,
  );
});

test("browser gate withholds server-rendered facts until runtime verification succeeds", () => {
  const source = fs.readFileSync(RUNTIME_GATE_SOURCE_PATH, "utf8");
  assert.match(source, /useState\(\{ phase: "checking", errors: \[\] \}\)/u);
  const verifiedGuard = source.indexOf('if (state.phase === "verified")');
  const verifiedChildren = source.indexOf("{children}", verifiedGuard);
  const checkingBranch = source.indexOf("Los hechos permanecen ocultos", verifiedChildren);
  assert.ok(verifiedGuard > 0);
  assert.ok(verifiedChildren > verifiedGuard);
  assert.ok(checkingBranch > verifiedChildren);
  assert.doesNotMatch(source.slice(checkingBranch), /\{children\}/u);
  assert.match(source, /todos los activos de evidencia/u);
  assert.doesNotMatch(source, /Verificando[^\n]*\b\d+\b[^\n]*activos/u);
  assert.match(source, /key=\{state\.phase\}/u);
  assert.match(source, /styles\.runtimePhasePanel/u);
});

test("route auditor validates the pinned manifest before fetching package assets", () => {
  const source = fs.readFileSync(ROUTE_AUDITOR_PATH, "utf8");
  const preliminary = source.indexOf(
    "preliminaryValidation = contract.validatePolicyOutcomesPackageContract",
  );
  const fetchGuard = source.indexOf("if (preliminaryValidation?.ok)", preliminary);
  const assetLoop = source.indexOf(
    "for (const [key, fact] of Object.entries(manifest.assets))",
    fetchGuard,
  );
  const safeResolver = source.indexOf(
    "contract.resolvePolicyOutcomesEvidenceAssetPath",
    assetLoop,
  );
  const remoteFetch = source.indexOf("const response = await fetchBytes", safeResolver);
  assert.ok(preliminary > 0);
  assert.ok(fetchGuard > preliminary);
  assert.ok(assetLoop > fetchGuard);
  assert.ok(safeResolver > assetLoop);
  assert.ok(remoteFetch > safeResolver);
});

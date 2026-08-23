import {
  isSafePolicyOutcomesManifestPath,
  resolvePolicyOutcomesEvidenceAssetPath,
  validatePolicyOutcomesPackage,
  validatePolicyOutcomesPackageContract,
} from "./status-contract.mjs";


export const POLICY_OUTCOMES_RUNTIME_STATUS_PATH =
  "/policy-outcomes/data/policy-outcomes.json";

const CONTROL_DOCUMENT_MAX_BYTES = 1024 * 1024;
const VERIFY_WORKERS = 4;

function bytesToHex(bytes) {
  return Array.from(new Uint8Array(bytes), (value) => value.toString(16).padStart(2, "0")).join("");
}

async function sha256(bytes) {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return bytesToHex(digest);
}

function parseObject(bytes, label, errors) {
  if (bytes.byteLength > CONTROL_DOCUMENT_MAX_BYTES) {
    errors.push(`${label}:oversized`);
    return null;
  }
  try {
    const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      errors.push(`${label}:object_required`);
      return null;
    }
    return value;
  } catch (_error) {
    errors.push(`${label}:invalid_json`);
    return null;
  }
}

async function fetchBytes(fetchImpl, publicPath, signal) {
  const response = await fetchImpl(publicPath, {
    cache: "no-store",
    credentials: "same-origin",
    headers: { "cache-control": "no-cache", pragma: "no-cache" },
    redirect: "error",
    signal,
  });
  if (!response?.ok || response.status !== 200 || response.redirected) {
    throw new Error(`http_${response?.status || 0}`);
  }
  return new Uint8Array(await response.arrayBuffer());
}

export async function verifyPolicyOutcomesRuntimePackage({
  fetchImpl = globalThis.fetch,
  signal,
  statusPath = POLICY_OUTCOMES_RUNTIME_STATUS_PATH,
} = {}) {
  const errors = [];
  if (typeof fetchImpl !== "function") {
    return { ok: false, errors: ["runtime_fetch:unavailable"] };
  }

  let statusBytes;
  try {
    statusBytes = await fetchBytes(fetchImpl, statusPath, signal);
  } catch (error) {
    return { ok: false, errors: [`runtime_status:${error.message}`] };
  }
  const status = parseObject(statusBytes, "runtime_status", errors);
  const manifestPath = status?.evidence_package?.manifest_path;
  if (!isSafePolicyOutcomesManifestPath(manifestPath)) {
    errors.push("runtime_manifest:unsafe_path");
    return { ok: false, errors };
  }

  let manifestBytes;
  try {
    manifestBytes = await fetchBytes(fetchImpl, manifestPath, signal);
  } catch (error) {
    return { ok: false, errors: [...errors, `runtime_manifest:${error.message}`] };
  }
  const manifest = parseObject(manifestBytes, "runtime_manifest", errors);
  const statusSha256 = await sha256(statusBytes);
  const manifestSha256 = await sha256(manifestBytes);
  const preliminary = validatePolicyOutcomesPackageContract({
    status,
    manifest,
    statusBytes: statusBytes.byteLength,
    statusSha256,
    manifestSha256,
  });
  errors.push(...preliminary.errors);
  if (!preliminary.ok) return { ok: false, errors };

  const entries = Object.entries(manifest.assets);
  const observedAssets = {};
  let cursor = 0;
  async function verifyWorker() {
    while (cursor < entries.length) {
      const index = cursor;
      cursor += 1;
      const [key, fact] = entries[index];
      const publicPath = resolvePolicyOutcomesEvidenceAssetPath(manifestPath, fact.path);
      if (!publicPath) {
        errors.push(`runtime_assets.${key}:unsafe_path`);
        continue;
      }
      try {
        const bytes = await fetchBytes(fetchImpl, publicPath, signal);
        observedAssets[key] = {
          bytes: bytes.byteLength,
          sha256: await sha256(bytes),
        };
      } catch (error) {
        errors.push(`runtime_assets.${key}:${error.message}`);
      }
    }
  }
  await Promise.all(
    Array.from(
      { length: Math.min(VERIFY_WORKERS, Math.max(entries.length, 1)) },
      () => verifyWorker(),
    ),
  );
  const validation = validatePolicyOutcomesPackage({
    status,
    manifest,
    statusBytes: statusBytes.byteLength,
    statusSha256,
    manifestSha256,
    observedAssets,
  });
  errors.push(...validation.errors);
  return {
    ok: errors.length === 0,
    errors: [...new Set(errors)],
    manifestSha256,
    verifiedAssets: Object.keys(observedAssets).length,
  };
}

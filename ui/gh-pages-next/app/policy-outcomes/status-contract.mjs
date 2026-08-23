export const POLICY_OUTCOMES_STATUS_PATH = "/policy-outcomes/data/policy-outcomes.json";
export const POLICY_OUTCOMES_STATUS_SCHEMA = "policy_outcomes_public_status_v3";
export const POLICY_OUTCOMES_MANIFEST_SCHEMA = "policy_outcomes_public_evidence_manifest_v1";
export const POLICY_OUTCOMES_IDENTITY_CONTRACT = "policy_outcomes_public_evidence_identity_v1";

// Single release pin. Every status fact, source fact, count, URL, hash, and
// asset is then checked against this exact manifest instead of being copied
// into each consumer.
export const CURRENT_POLICY_OUTCOMES_MANIFEST_SHA256 =
  "2bfe3f2d0850c6775349b763239300f50eb199a04167026798764bb20ff83d07";

const HEX64_RE = /^[0-9a-f]{64}$/u;
const UTC_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/u;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/u;
const PACKAGE_MANIFEST_RE = /^\/policy-outcomes\/evidence\/([0-9a-f]{64})\/manifest\.json$/u;
const ASSET_PATH_RE = /^assets\/[a-z0-9][a-z0-9._-]*$/u;

const STATUS_KEYS = new Set([
  "bounded_universe",
  "claim_boundary",
  "contract_date",
  "data_policy",
  "evidence_package",
  "method_version",
  "pipeline",
  "public_payload_kind",
  "publication_state",
  "schema_version",
  "selected_inputs",
  "validation_identity",
]);
const PIPELINE_KEYS = new Set([
  "evidence_level",
  "human_review_required",
  "human_reviewed_pairs",
  "human_reviews",
  "pending_methodological_candidates_disclosed",
  "published_outcome_links",
  "release_memberships",
  "releases",
  "scale_stage",
  "validated_outcome_links",
]);
const SCOPE_KEYS = new Set([
  "action_candidates",
  "action_universe_canonical_bytes",
  "action_universe_sha256",
  "all_possible_action_indicator_pairs_searched",
  "all_possible_actions_searched",
  "all_possible_indicators_searched",
  "bounded_scope_complete",
  "candidate_pairs",
  "combined_scope_sha256",
  "eligible_indicator_series",
  "eligible_indicator_series_sha256",
]);
const SELECTED_INPUT_KEYS = new Set([
  "eurostat_indicator",
  "relationship_state",
  "senate_initiative",
  "senate_vote",
  "validation_state",
]);
const SENATE_VOTE_KEYS = new Set([
  "normalized_record_bytes",
  "normalized_record_sha256",
  "official_file_url",
  "official_page_url",
  "original_xml_capture_state",
  "source_id",
  "source_snapshot_date",
]);
const SENATE_INITIATIVE_KEYS = new Set([
  "normalized_record_bytes",
  "normalized_record_sha256",
  "official_url",
  "source_id",
  "source_snapshot_date",
]);
const EUROSTAT_KEYS = new Set([
  "comparison_state",
  "dataset_code",
  "official_url",
  "source_bytes",
  "source_id",
  "source_sha256",
  "source_snapshot_date",
  "source_updated_at",
]);
const CLAIM_KEYS = new Set([
  "causal_claim",
  "corruption_assessment",
  "effect_estimate",
  "political_merit_or_blame",
  "statistical_association_claim",
  "success_or_failure_assessment",
]);
const DATA_POLICY_KEYS = new Set([
  "official_public_identity_policy",
  "official_public_names_removed_or_pseudonymized",
  "official_public_names_retained_in_semantic_evidence",
  "real_data_only",
  "status_contains_individual_participant_rows",
  "synthetic_or_mock_rows",
]);
const VALIDATION_KEYS = new Set([
  "artifact_set_sha256",
  "bundle_semantic_sha256",
  "check_count",
  "deterministic_fingerprint",
  "internal_bundle_manifest_sha256",
  "report_sha256",
  "schema_version",
  "status",
]);
const EVIDENCE_PACKAGE_KEYS = new Set([
  "all_assets_content_addressed",
  "manifest_authentication_state",
  "manifest_path",
  "package_id",
]);
const MANIFEST_KEYS = new Set([
  "assets",
  "authentication",
  "bounded_universe",
  "claim_boundary",
  "contract_date",
  "identity_contract_version",
  "identity_retention",
  "package_id",
  "package_role",
  "publication_state",
  "schema_version",
  "signed_scale_origin_linkage",
  "source_inputs",
  "status",
  "validation_identity",
]);
const STATUS_FACT_KEYS = new Set(["bytes", "path", "schema_version", "sha256"]);
const IDENTITY_RETENTION_KEYS = new Set([
  "official_public_names_removed_or_pseudonymized",
  "official_public_names_retained",
  "semantic_evidence_asset_key",
  "semantic_evidence_copied_byte_for_byte",
]);
const AUTHENTICATION_KEYS = new Set([
  "note",
  "signature_algorithm",
  "signer_identity",
  "state",
]);
const SCALE_LINKAGE_KEYS = new Set([
  "linkage_state",
  "outcome_package_in_signed_scale_origin",
  "scale_origin_allowed_signers_sha256",
  "scale_origin_attestation_sha256",
  "scale_origin_live_parity_verified",
  "scale_origin_manifest_sha256",
  "scale_origin_manifest_url",
  "scale_origin_public_key_fingerprint",
  "scale_origin_signature_sha256",
  "scale_origin_signature_verified",
  "scale_origin_signer_identity",
  "scale_origin_snapshot_date",
]);
const ASSET_FACT_KEYS = new Set(["bytes", "media_type", "path", "role", "sha256"]);
const ASSET_KEYS = new Set([
  "action_candidate_universe",
  "eurostat_raw_capture",
  "eligible_indicator_series_universe",
  "independent_validation_evidence_projection",
  "internal_bundle_manifest",
  "internal_latest_pointer",
  "materialization_evidence_projection",
  "scale_origin_allowed_signers",
  "scale_origin_attestation",
  "scale_origin_attestation_signature",
  "scale_origin_live_parity",
  "scale_origin_live_verification",
  "semantic_evidence",
  "senate_initiative_normalized_record",
  "senate_vote_normalized_record",
  "signed_scale_origin_manifest",
  "sqlite_bundle",
]);

const PROHIBITED_STATUS_KEYS = new Set([
  "action",
  "actions",
  "association",
  "associations",
  "candidate",
  "candidates",
  "claims",
  "comparisons",
  "evidence",
  "indicator",
  "indicators",
  "link_versions",
  "links",
  "observation",
  "observation_refs",
  "observations",
  "official_member_name",
  "outcome",
  "outcomes",
  "participant",
  "participant_refs",
  "participants",
  "policy_events",
  "reviews",
  "scope_closures",
  "series",
]);
const PROHIBITED_STATUS_VALUE_MARKERS = [
  "vclc:outcome-link:",
  "vclc:outcome-link-version:",
  "vclc:outcome-link-participant-ref:",
  "urn:vclc:actor:",
  "official_member_name",
];

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function sameKeys(value, expected) {
  if (!isRecord(value)) return false;
  const keys = Object.keys(value);
  return keys.length === expected.size && keys.every((key) => expected.has(key));
}

function deepEqual(left, right) {
  if (left === right) return true;
  if (Array.isArray(left) || Array.isArray(right)) return false;
  if (!isRecord(left) || !isRecord(right)) return false;
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  if (leftKeys.length !== rightKeys.length) return false;
  return leftKeys.every(
    (key, index) => key === rightKeys[index] && deepEqual(left[key], right[key]),
  );
}

function positiveInteger(value) {
  return Number.isSafeInteger(value) && value > 0;
}

function nonNegativeInteger(value) {
  return Number.isSafeInteger(value) && value >= 0;
}

function httpsUrl(value) {
  if (typeof value !== "string" || !value.startsWith("https://")) return false;
  try {
    return new URL(value).protocol === "https:";
  } catch (_error) {
    return false;
  }
}

function collectStatusLeakErrors(value, path = "status") {
  const errors = [];
  if (Array.isArray(value)) {
    errors.push(`${path}:array_forbidden`);
    return errors;
  }
  if (typeof value === "string") {
    for (const marker of PROHIBITED_STATUS_VALUE_MARKERS) {
      if (value.includes(marker)) errors.push(`${path}:internal_detail_value_forbidden`);
    }
    return errors;
  }
  if (!isRecord(value)) return errors;
  for (const [key, nested] of Object.entries(value)) {
    if (PROHIBITED_STATUS_KEYS.has(key)) errors.push(`${path}.${key}:detail_key_forbidden`);
    errors.push(...collectStatusLeakErrors(nested, `${path}.${key}`));
  }
  return errors;
}

function expectKeys(errors, value, expected, label) {
  if (!sameKeys(value, expected)) errors.push(`${label}:keys`);
}

function expectSha(errors, value, label) {
  if (typeof value !== "string" || !HEX64_RE.test(value)) errors.push(`${label}:sha256`);
}

function validateScope(scope, errors, label) {
  expectKeys(errors, scope, SCOPE_KEYS, label);
  if (!isRecord(scope)) return;
  for (const key of [
    "action_candidates",
    "eligible_indicator_series",
    "candidate_pairs",
    "action_universe_canonical_bytes",
  ]) {
    if (!positiveInteger(scope[key])) errors.push(`${label}.${key}`);
  }
  for (const key of [
    "action_universe_sha256",
    "eligible_indicator_series_sha256",
    "combined_scope_sha256",
  ]) expectSha(errors, scope[key], `${label}.${key}`);
  if (scope.action_candidates * scope.eligible_indicator_series !== scope.candidate_pairs) {
    errors.push(`${label}:pair_arithmetic`);
  }
  if (scope.bounded_scope_complete !== true) errors.push(`${label}.bounded_scope_complete`);
  for (const key of [
    "all_possible_actions_searched",
    "all_possible_indicators_searched",
    "all_possible_action_indicator_pairs_searched",
  ]) {
    if (scope[key] !== false) errors.push(`${label}.${key}`);
  }
}

function validateSelectedInputs(inputs, errors, label) {
  expectKeys(errors, inputs, SELECTED_INPUT_KEYS, label);
  if (!isRecord(inputs)) return;
  if (inputs.relationship_state !== "selected_together_in_one_pending_methodological_candidate") {
    errors.push(`${label}.relationship_state`);
  }
  if (inputs.validation_state !== "not_a_validated_outcome_link") {
    errors.push(`${label}.validation_state`);
  }
  const vote = inputs.senate_vote;
  const initiative = inputs.senate_initiative;
  const eurostat = inputs.eurostat_indicator;
  expectKeys(errors, vote, SENATE_VOTE_KEYS, `${label}.senate_vote`);
  expectKeys(errors, initiative, SENATE_INITIATIVE_KEYS, `${label}.senate_initiative`);
  expectKeys(errors, eurostat, EUROSTAT_KEYS, `${label}.eurostat_indicator`);
  if (isRecord(vote)) {
    if (!positiveInteger(vote.normalized_record_bytes)) errors.push(`${label}.senate_vote.bytes`);
    expectSha(errors, vote.normalized_record_sha256, `${label}.senate_vote.record`);
    if (!httpsUrl(vote.official_page_url) || !httpsUrl(vote.official_file_url)) {
      errors.push(`${label}.senate_vote.urls`);
    }
    if (!DATE_RE.test(String(vote.source_snapshot_date || ""))) errors.push(`${label}.senate_vote.date`);
    if (vote.original_xml_capture_state !== "absent_from_current_snapshot") {
      errors.push(`${label}.senate_vote.original_xml_capture_state`);
    }
  }
  if (isRecord(initiative)) {
    if (!positiveInteger(initiative.normalized_record_bytes)) errors.push(`${label}.senate_initiative.bytes`);
    expectSha(errors, initiative.normalized_record_sha256, `${label}.senate_initiative.record`);
    if (!httpsUrl(initiative.official_url)) errors.push(`${label}.senate_initiative.url`);
    if (!DATE_RE.test(String(initiative.source_snapshot_date || ""))) errors.push(`${label}.senate_initiative.date`);
  }
  if (isRecord(eurostat)) {
    if (!positiveInteger(eurostat.source_bytes)) errors.push(`${label}.eurostat_indicator.bytes`);
    expectSha(errors, eurostat.source_sha256, `${label}.eurostat_indicator.source`);
    if (!httpsUrl(eurostat.official_url)) errors.push(`${label}.eurostat_indicator.url`);
    if (!DATE_RE.test(String(eurostat.source_snapshot_date || ""))) errors.push(`${label}.eurostat_indicator.date`);
    if (eurostat.comparison_state !== "baseline") errors.push(`${label}.eurostat_indicator.comparison_state`);
  }
}

function validateClaimBoundary(policy, errors, label) {
  expectKeys(errors, policy, CLAIM_KEYS, label);
  if (!isRecord(policy)) return;
  const expected = {
    statistical_association_claim: "none",
    causal_claim: "none",
    effect_estimate: "not_computed",
    political_merit_or_blame: "not_assessed",
    success_or_failure_assessment: "not_assessed",
    corruption_assessment: "not_assessed",
  };
  for (const [key, value] of Object.entries(expected)) {
    if (policy[key] !== value) errors.push(`${label}.${key}`);
  }
}

function validateValidationIdentity(identity, errors, label) {
  expectKeys(errors, identity, VALIDATION_KEYS, label);
  if (!isRecord(identity)) return;
  if (identity.status !== "passed") errors.push(`${label}.status`);
  if (identity.schema_version !== "outcome_context_validation_v1") errors.push(`${label}.schema_version`);
  if (!positiveInteger(identity.check_count)) errors.push(`${label}.check_count`);
  for (const key of [
    "deterministic_fingerprint",
    "report_sha256",
    "artifact_set_sha256",
    "bundle_semantic_sha256",
    "internal_bundle_manifest_sha256",
  ]) expectSha(errors, identity[key], `${label}.${key}`);
}

function validateStatus(status, errors) {
  expectKeys(errors, status, STATUS_KEYS, "status");
  if (!isRecord(status)) return;
  errors.push(...collectStatusLeakErrors(status));
  if (status.schema_version !== POLICY_OUTCOMES_STATUS_SCHEMA) errors.push("status.schema_version");
  if (status.public_payload_kind !== "pending_methodological_candidate_status_with_evidence") {
    errors.push("status.public_payload_kind");
  }
  if (status.method_version !== "outcome_linking_v1") errors.push("status.method_version");
  if (status.publication_state !== "one_pending_methodological_candidate_disclosed_zero_validated_outcome_links") {
    errors.push("status.publication_state");
  }
  if (!UTC_RE.test(String(status.contract_date || ""))) errors.push("status.contract_date");
  const pipeline = status.pipeline;
  expectKeys(errors, pipeline, PIPELINE_KEYS, "status.pipeline");
  if (isRecord(pipeline)) {
    const exact = {
      scale_stage: "C0",
      evidence_level: "L1",
      pending_methodological_candidates_disclosed: 1,
      human_reviewed_pairs: 0,
      human_reviews: 0,
      validated_outcome_links: 0,
      published_outcome_links: 0,
      releases: 0,
      release_memberships: 0,
      human_review_required: true,
    };
    for (const [key, value] of Object.entries(exact)) {
      if (pipeline[key] !== value) errors.push(`status.pipeline.${key}`);
    }
  }
  validateScope(status.bounded_universe, errors, "status.bounded_universe");
  validateSelectedInputs(status.selected_inputs, errors, "status.selected_inputs");
  validateClaimBoundary(status.claim_boundary, errors, "status.claim_boundary");
  const dataPolicy = status.data_policy;
  expectKeys(errors, dataPolicy, DATA_POLICY_KEYS, "status.data_policy");
  if (isRecord(dataPolicy)) {
    if (dataPolicy.real_data_only !== true) errors.push("status.data_policy.real_data_only");
    if (dataPolicy.synthetic_or_mock_rows !== 0) errors.push("status.data_policy.synthetic_or_mock_rows");
    if (!positiveInteger(dataPolicy.official_public_names_retained_in_semantic_evidence)) {
      errors.push("status.data_policy.official_public_names_retained_in_semantic_evidence");
    }
    if (dataPolicy.official_public_names_removed_or_pseudonymized !== 0) {
      errors.push("status.data_policy.official_public_names_removed_or_pseudonymized");
    }
    if (dataPolicy.status_contains_individual_participant_rows !== false) {
      errors.push("status.data_policy.status_contains_individual_participant_rows");
    }
  }
  validateValidationIdentity(status.validation_identity, errors, "status.validation_identity");
  const evidencePackage = status.evidence_package;
  expectKeys(errors, evidencePackage, EVIDENCE_PACKAGE_KEYS, "status.evidence_package");
  if (isRecord(evidencePackage)) {
    expectSha(errors, evidencePackage.package_id, "status.evidence_package.package_id");
    const match = String(evidencePackage.manifest_path || "").match(PACKAGE_MANIFEST_RE);
    if (!match || match[1] !== evidencePackage.package_id) errors.push("status.evidence_package.manifest_path");
    if (evidencePackage.manifest_authentication_state !== "unsigned") {
      errors.push("status.evidence_package.manifest_authentication_state");
    }
    if (evidencePackage.all_assets_content_addressed !== true) {
      errors.push("status.evidence_package.all_assets_content_addressed");
    }
  }
}

function validateManifest(manifest, errors) {
  expectKeys(errors, manifest, MANIFEST_KEYS, "manifest");
  if (!isRecord(manifest)) return;
  if (manifest.schema_version !== POLICY_OUTCOMES_MANIFEST_SCHEMA) errors.push("manifest.schema_version");
  if (manifest.identity_contract_version !== POLICY_OUTCOMES_IDENTITY_CONTRACT) {
    errors.push("manifest.identity_contract_version");
  }
  expectSha(errors, manifest.package_id, "manifest.package_id");
  if (!UTC_RE.test(String(manifest.contract_date || ""))) errors.push("manifest.contract_date");
  if (manifest.package_role !== "public_verification_evidence_for_one_pending_methodological_candidate") {
    errors.push("manifest.package_role");
  }
  if (manifest.publication_state !== "one_pending_methodological_candidate_disclosed_zero_validated_outcome_links") {
    errors.push("manifest.publication_state");
  }
  const statusFact = manifest.status;
  expectKeys(errors, statusFact, STATUS_FACT_KEYS, "manifest.status");
  if (isRecord(statusFact)) {
    if (statusFact.path !== POLICY_OUTCOMES_STATUS_PATH) errors.push("manifest.status.path");
    if (statusFact.schema_version !== POLICY_OUTCOMES_STATUS_SCHEMA) errors.push("manifest.status.schema_version");
    if (!positiveInteger(statusFact.bytes)) errors.push("manifest.status.bytes");
    expectSha(errors, statusFact.sha256, "manifest.status.sha256");
  }
  validateSelectedInputs(manifest.source_inputs, errors, "manifest.source_inputs");
  validateScope(manifest.bounded_universe, errors, "manifest.bounded_universe");
  validateValidationIdentity(manifest.validation_identity, errors, "manifest.validation_identity");
  validateClaimBoundary(manifest.claim_boundary, errors, "manifest.claim_boundary");
  const retention = manifest.identity_retention;
  expectKeys(errors, retention, IDENTITY_RETENTION_KEYS, "manifest.identity_retention");
  if (isRecord(retention)) {
    if (!positiveInteger(retention.official_public_names_retained)) errors.push("manifest.identity_retention.retained");
    if (retention.official_public_names_removed_or_pseudonymized !== 0) errors.push("manifest.identity_retention.removed");
    if (retention.semantic_evidence_asset_key !== "semantic_evidence") errors.push("manifest.identity_retention.asset_key");
    if (retention.semantic_evidence_copied_byte_for_byte !== true) errors.push("manifest.identity_retention.byte_copy");
  }
  const authentication = manifest.authentication;
  expectKeys(errors, authentication, AUTHENTICATION_KEYS, "manifest.authentication");
  if (isRecord(authentication)) {
    if (authentication.state !== "unsigned") errors.push("manifest.authentication.state");
    if (authentication.signature_algorithm !== "none") errors.push("manifest.authentication.signature_algorithm");
    if (authentication.signer_identity !== null) errors.push("manifest.authentication.signer_identity");
  }
  const scale = manifest.signed_scale_origin_linkage;
  expectKeys(errors, scale, SCALE_LINKAGE_KEYS, "manifest.signed_scale_origin_linkage");
  if (isRecord(scale)) {
    if (scale.linkage_state !== "verified_upstream_scale_origin_not_attesting_this_outcome_package") {
      errors.push("manifest.signed_scale_origin_linkage.linkage_state");
    }
    if (scale.outcome_package_in_signed_scale_origin !== false) errors.push("manifest.signed_scale_origin_linkage.membership");
    if (scale.scale_origin_signature_verified !== true) errors.push("manifest.signed_scale_origin_linkage.signature");
    if (scale.scale_origin_live_parity_verified !== true) errors.push("manifest.signed_scale_origin_linkage.parity");
    if (scale.scale_origin_signer_identity !== "vclc-snapshot-release-2026") {
      errors.push("manifest.signed_scale_origin_linkage.signer_identity");
    }
    if (scale.scale_origin_public_key_fingerprint
        !== "SHA256:R2B1jFbkLoigmKxObr+ExlBLrKENkaUDp0C3ip0Lj7A") {
      errors.push("manifest.signed_scale_origin_linkage.public_key_fingerprint");
    }
    if (!DATE_RE.test(String(scale.scale_origin_snapshot_date || ""))) errors.push("manifest.signed_scale_origin_linkage.date");
    if (!httpsUrl(scale.scale_origin_manifest_url)) errors.push("manifest.signed_scale_origin_linkage.url");
    for (const key of [
      "scale_origin_manifest_sha256",
      "scale_origin_allowed_signers_sha256",
      "scale_origin_attestation_sha256",
      "scale_origin_signature_sha256",
    ]) expectSha(errors, scale[key], `manifest.signed_scale_origin_linkage.${key}`);
  }
  const assets = manifest.assets;
  expectKeys(errors, assets, ASSET_KEYS, "manifest.assets");
  if (isRecord(assets)) {
    const paths = new Set();
    for (const [key, fact] of Object.entries(assets)) {
      expectKeys(errors, fact, ASSET_FACT_KEYS, `manifest.assets.${key}`);
      if (!isRecord(fact)) continue;
      if (!ASSET_PATH_RE.test(String(fact.path || ""))) errors.push(`manifest.assets.${key}.path`);
      if (paths.has(fact.path)) errors.push(`manifest.assets.${key}.duplicate_path`);
      paths.add(fact.path);
      if (!positiveInteger(fact.bytes)) errors.push(`manifest.assets.${key}.bytes`);
      expectSha(errors, fact.sha256, `manifest.assets.${key}.sha256`);
      if (typeof fact.media_type !== "string" || !fact.media_type) errors.push(`manifest.assets.${key}.media_type`);
      if (typeof fact.role !== "string" || !fact.role) errors.push(`manifest.assets.${key}.role`);
    }
  }
}

function validateCrossContract(status, manifest, errors) {
  if (!isRecord(status) || !isRecord(manifest)) return;
  if (status.contract_date !== manifest.contract_date) errors.push("cross.contract_date");
  if (status.publication_state !== manifest.publication_state) errors.push("cross.publication_state");
  if (!deepEqual(status.selected_inputs, manifest.source_inputs)) errors.push("cross.source_inputs");
  if (!deepEqual(status.bounded_universe, manifest.bounded_universe)) errors.push("cross.bounded_universe");
  if (!deepEqual(status.validation_identity, manifest.validation_identity)) errors.push("cross.validation_identity");
  if (!deepEqual(status.claim_boundary, manifest.claim_boundary)) errors.push("cross.claim_boundary");
  if (status.evidence_package?.package_id !== manifest.package_id) errors.push("cross.package_id");
  if (status.evidence_package?.manifest_path !== `/policy-outcomes/evidence/${manifest.package_id}/manifest.json`) {
    errors.push("cross.manifest_path");
  }
  if (status.data_policy?.official_public_names_retained_in_semantic_evidence
      !== manifest.identity_retention?.official_public_names_retained) {
    errors.push("cross.official_names_retained");
  }
  if (status.selected_inputs?.senate_vote?.normalized_record_sha256
      !== manifest.assets?.senate_vote_normalized_record?.sha256
      || status.selected_inputs?.senate_vote?.normalized_record_bytes
      !== manifest.assets?.senate_vote_normalized_record?.bytes) {
    errors.push("cross.senate_vote_asset");
  }
  if (status.selected_inputs?.senate_initiative?.normalized_record_sha256
      !== manifest.assets?.senate_initiative_normalized_record?.sha256
      || status.selected_inputs?.senate_initiative?.normalized_record_bytes
      !== manifest.assets?.senate_initiative_normalized_record?.bytes) {
    errors.push("cross.senate_initiative_asset");
  }
  if (status.selected_inputs?.eurostat_indicator?.source_sha256
      !== manifest.assets?.eurostat_raw_capture?.sha256
      || status.selected_inputs?.eurostat_indicator?.source_bytes
      !== manifest.assets?.eurostat_raw_capture?.bytes) {
    errors.push("cross.eurostat_asset");
  }
  if (status.bounded_universe?.action_universe_sha256
      !== manifest.assets?.action_candidate_universe?.sha256
      || status.bounded_universe?.action_universe_canonical_bytes
      !== manifest.assets?.action_candidate_universe?.bytes) {
    errors.push("cross.action_universe_asset");
  }
  if (status.bounded_universe?.eligible_indicator_series_sha256
      !== manifest.assets?.eligible_indicator_series_universe?.sha256) {
    errors.push("cross.eligible_series_universe_asset");
  }
  if (status.validation_identity?.report_sha256
      !== manifest.assets?.independent_validation_evidence_projection?.sha256) {
    errors.push("cross.validation_report_asset");
  }
  if (status.validation_identity?.bundle_semantic_sha256 === manifest.assets?.semantic_evidence?.sha256) {
    errors.push("cross.semantic_identity_must_not_equal_physical_hash");
  }
  if (status.validation_identity?.internal_bundle_manifest_sha256
      !== manifest.assets?.internal_bundle_manifest?.sha256) {
    errors.push("cross.internal_manifest_asset");
  }
  if (manifest.signed_scale_origin_linkage?.scale_origin_manifest_sha256
      !== manifest.assets?.signed_scale_origin_manifest?.sha256) {
    errors.push("cross.scale_manifest_asset");
  }
  if (manifest.signed_scale_origin_linkage?.scale_origin_attestation_sha256
      !== manifest.assets?.scale_origin_attestation?.sha256) {
    errors.push("cross.scale_attestation_asset");
  }
  if (manifest.signed_scale_origin_linkage?.scale_origin_signature_sha256
      !== manifest.assets?.scale_origin_attestation_signature?.sha256) {
    errors.push("cross.scale_signature_asset");
  }
  if (manifest.signed_scale_origin_linkage?.scale_origin_allowed_signers_sha256
      !== manifest.assets?.scale_origin_allowed_signers?.sha256) {
    errors.push("cross.scale_allowed_signers_asset");
  }
}

export function isSafePolicyOutcomesManifestPath(value) {
  return typeof value === "string" && PACKAGE_MANIFEST_RE.test(value);
}

export function resolvePolicyOutcomesEvidenceAssetPath(manifestPath, assetPath) {
  const manifestMatch = typeof manifestPath === "string"
    ? manifestPath.match(PACKAGE_MANIFEST_RE)
    : null;
  if (!manifestMatch || typeof assetPath !== "string" || !ASSET_PATH_RE.test(assetPath)) {
    return null;
  }
  return `/policy-outcomes/evidence/${manifestMatch[1]}/${assetPath}`;
}

export function validateObservedEvidenceAssets(manifest, observedAssets) {
  const errors = [];
  if (!isRecord(manifest?.assets) || !isRecord(observedAssets)) return ["observed_assets:object_required"];
  const expectedKeys = Object.keys(manifest.assets).sort();
  const observedKeys = Object.keys(observedAssets).sort();
  if (!deepEqual(
    Object.fromEntries(expectedKeys.map((key) => [key, true])),
    Object.fromEntries(observedKeys.map((key) => [key, true])),
  )) errors.push("observed_assets:keys");
  for (const key of expectedKeys) {
    const expected = manifest.assets[key];
    const observed = observedAssets[key];
    if (!isRecord(observed)) {
      errors.push(`observed_assets.${key}:missing`);
      continue;
    }
    if (observed.bytes !== expected.bytes) errors.push(`observed_assets.${key}:bytes`);
    if (observed.sha256 !== expected.sha256) errors.push(`observed_assets.${key}:sha256`);
  }
  return errors;
}

export function validatePolicyOutcomesPackageContract({
  status,
  manifest,
  statusBytes,
  statusSha256,
  manifestSha256,
} = {}) {
  const errors = [];
  validateStatus(status, errors);
  validateManifest(manifest, errors);
  validateCrossContract(status, manifest, errors);
  if (manifestSha256 !== CURRENT_POLICY_OUTCOMES_MANIFEST_SHA256) {
    errors.push("manifest:release_identity");
  }
  if (isRecord(manifest?.status)) {
    if (statusBytes !== manifest.status.bytes) errors.push("status:bytes_mismatch");
    if (statusSha256 !== manifest.status.sha256) errors.push("status:sha256_mismatch");
  }
  return { ok: errors.length === 0, errors };
}

export function validatePolicyOutcomesPackage(options = {}) {
  const contract = validatePolicyOutcomesPackageContract(options);
  const errors = [
    ...contract.errors,
    ...validateObservedEvidenceAssets(options.manifest, options.observedAssets),
  ];
  return { ok: errors.length === 0, errors };
}

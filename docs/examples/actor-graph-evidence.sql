-- Run against etl/data/staging/actor-graph-v1.db.
-- Shows real actor -> relationship -> context -> exact evidence provenance.

.headers on
.mode column

SELECT
  subject.canonical_label AS actor,
  nodes.actor_kind,
  nodes.actor_subtype,
  relationships.relationship_type,
  versions.role_label,
  object.canonical_label AS related_actor,
  relationships.context_kind,
  relationships.context_id,
  versions.valid_from,
  versions.valid_to,
  versions.observed_at,
  versions.resolution_state,
  evidence.evidence_kind,
  evidence.source_id,
  evidence.source_url,
  evidence.source_content_sha256,
  evidence.source_locator
FROM actor_graph_relationships AS relationships
JOIN actor_graph_relationship_versions AS versions
  ON versions.relationship_id = relationships.relationship_id
JOIN actor_graph_nodes AS nodes
  ON nodes.actor_id = relationships.subject_actor_id
JOIN actor_graph_node_versions AS subject
  ON subject.actor_id = relationships.subject_actor_id
 AND subject.release_id = versions.release_id
LEFT JOIN actor_graph_node_versions AS object
  ON object.actor_id = relationships.object_actor_id
 AND object.release_id = versions.release_id
JOIN actor_graph_relationship_evidence AS evidence
  ON evidence.relationship_version_id = versions.relationship_version_id
WHERE relationships.relationship_type IN (
  'holds_role_at',
  'candidate_for',
  'elected_in',
  'acts_in_spending_item',
  'party_to_agreement',
  'acts_in_geopolitical_action',
  'publishes_manifesto'
)
ORDER BY
  relationships.relationship_type,
  evidence.source_id,
  relationships.context_id
LIMIT 25;

-- Identity policy must remain source-scoped until exact official identifiers or
-- reviewed evidence support a cross-source decision.
SELECT
  decisions.outcome,
  decisions.method,
  decisions.confidence,
  COUNT(*) AS decisions
FROM actor_resolution_decisions AS decisions
GROUP BY decisions.outcome, decisions.method, decisions.confidence
ORDER BY decisions DESC;

-- Public accountability identity is retained. This query exposes exact source
-- labels and identifiers; it does not anonymize official public fields.
SELECT
  versions.canonical_label,
  identifiers.namespace,
  identifiers.value,
  identifiers.provenance_state,
  identifiers.source_id,
  identifiers.source_url
FROM actor_graph_identifier_versions AS identifiers
JOIN actor_graph_node_versions AS versions
  ON versions.actor_id = identifiers.actor_id
 AND versions.release_id = identifiers.release_id
ORDER BY identifiers.source_id, versions.canonical_label, identifiers.namespace
LIMIT 25;

-- Real PLACSP MVP: actor -> procurement award -> official evidence.
-- Run:
-- sqlite3 -header -column etl/data/staging/spending-placsp-mvp.db \
--   < docs/examples/placsp-actor-spending-evidence.sql
--
-- Important: spending_kind=procurement_award and paid_on IS NULL. These rows
-- prove a published award. They do not prove contract signature, invoice,
-- payment, delivery, irregularity, illegality, or corruption.

SELECT
  actor.actor_role,
  actor.actor_kind,
  actor.source_label AS actor_name_exact,
  actor.source_identifier AS actor_identifier_exact,
  item.spending_item_id,
  item.spending_kind,
  item.external_contract_id,
  item.title,
  item.amount_decimal,
  item.currency,
  item.amount_semantics,
  item.decision_on,
  item.paid_on,
  evidence.evidence_role,
  evidence.evidence_state,
  COALESCE(evidence.document_url, evidence.source_url) AS official_evidence_url,
  evidence.content_sha256 AS captured_source_record_sha256
FROM spending_item_actors AS actor
JOIN spending_items AS item
  ON item.spending_item_id = actor.spending_item_id
JOIN spending_item_evidence AS evidence
  ON evidence.spending_item_id = item.spending_item_id
 AND evidence.evidence_ordinal = 0
WHERE actor.actor_role IN ('contracting_authority', 'supplier')
ORDER BY item.decision_on, item.spending_item_id, actor.actor_ordinal;

-- Actor -> agreement -> official evidence.
-- Real materialized DB:
--   etl/data/staging/agreements-moncloa-mvp.db
--
-- The query does not infer attendance or influence. Topic rows are visibly
-- derived and retain their method/review state.
SELECT
  party.source_label AS actor,
  party.party_role,
  agreement.agreement_id,
  agreement.agreement_kind,
  agreement.agreement_status,
  agreement.adopted_on,
  agreement.title,
  agreement.summary,
  meeting.meeting_kind,
  meeting.attendance_disclosure_state,
  GROUP_CONCAT(DISTINCT topic.topic_label) AS derived_topics,
  GROUP_CONCAT(DISTINCT topic.review_status) AS topic_review_states,
  evidence.evidence_role,
  evidence.exact_quote,
  evidence.source_url,
  evidence.content_sha256,
  evidence.quote_sha256
FROM agreement_parties AS party
JOIN agreements AS agreement
  ON agreement.agreement_id = party.agreement_id
LEFT JOIN accountability_meetings AS meeting
  ON meeting.meeting_id = agreement.meeting_id
LEFT JOIN agreement_topics AS topic
  ON topic.agreement_id = agreement.agreement_id
JOIN agreement_evidence AS evidence
  ON evidence.agreement_id = agreement.agreement_id
 AND evidence.evidence_role = 'official_summary'
WHERE party.source_label = 'Consejo de Ministros'
GROUP BY
  party.agreement_party_id,
  agreement.agreement_id,
  evidence.agreement_evidence_id
ORDER BY agreement.adopted_on, agreement.agreement_id;

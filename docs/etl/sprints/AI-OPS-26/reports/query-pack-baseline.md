# Query Pack Baseline (T3)

Generated artifacts:
- `docs/etl/sprints/AI-OPS-26/evidence/baseline-metrics.json`

DB:
- `etl/data/staging/politicos-es.db`

## Baseline Summary

- `topic_evidence_reviews_total`: `537`
- `topic_evidence_reviews_pending`: `6`
- `topic_evidence_reviews_pending_by_reason`: `no_signal=6`
- `parl_vote_member_votes` unresolved rows: `34,780`
- `parl_vote_member_votes` unresolved names: `321`
- `text_documents` (`source_id=parl_initiative_docs`) total: `555`
- `text_documents` missing excerpt: `456`
- `policy_events` total: `548`
- `policy_event_axis_scores` total: `0`
- tracker parity: `mismatches=0`, `done_zero_real=0`

## Lane A Baseline SQL (topic_evidence_reviews)

Purpose:
- Extract pending declared queue for `programas_partidos`.

```sql
SELECT
  r.evidence_id,
  p.name AS person_name,
  t.label AS topic_label,
  e.excerpt AS evidence_excerpt,
  e.evidence_date,
  sr.source_url,
  r.review_reason
FROM topic_evidence_reviews r
JOIN topic_evidence e ON e.evidence_id = r.evidence_id
LEFT JOIN persons p ON p.person_id = e.person_id
LEFT JOIN topics t ON t.topic_id = e.topic_id
LEFT JOIN source_records sr ON sr.source_record_pk = e.source_record_pk
WHERE r.source_id = 'programas_partidos'
  AND r.status = 'pending'
ORDER BY r.evidence_id;
```

CLI extract:
```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "<SQL arriba>"
```

## Lane B Baseline SQL (parl_vote_member_votes unresolved)

Purpose:
- Build unresolved-name resolution tasks grouped by normalized member name.

```sql
WITH unresolved AS (
  SELECT
    source_id,
    lower(trim(member_name)) AS member_name_normalized,
    MIN(member_name) AS member_name_example,
    MIN(group_code) AS group_code_example,
    MIN(legislature) AS legislature_example,
    COUNT(*) AS unresolved_rows
  FROM parl_vote_member_votes
  WHERE person_id IS NULL
  GROUP BY source_id, lower(trim(member_name))
)
SELECT *
FROM unresolved
ORDER BY unresolved_rows DESC, source_id, member_name_normalized;
```

CLI extract:
```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "<SQL arriba>"
```

## Lane C Baseline SQL (text_documents missing excerpts)

Purpose:
- Prepare document excerpt/summary queue.

```sql
SELECT
  td.source_url AS doc_url,
  td.source_record_pk,
  td.content_type,
  td.raw_path,
  i.initiative_id,
  CASE
    WHEN td.content_type LIKE 'application/pdf%' THEN 'pdf'
    WHEN td.content_type LIKE 'text/html%' THEN 'html'
    ELSE 'other'
  END AS doc_kind
FROM text_documents td
LEFT JOIN parl_initiative_documents pid
  ON pid.source_record_pk = td.source_record_pk
LEFT JOIN parl_initiatives i
  ON i.initiative_id = pid.initiative_id
WHERE td.source_id = 'parl_initiative_docs'
  AND (td.text_excerpt IS NULL OR trim(td.text_excerpt) = '')
ORDER BY td.source_record_pk;
```

CLI extract:
```bash
sqlite3 -header -csv etl/data/staging/politicos-es.db "<SQL arriba>"
```

## Lane D Baseline SQL (concern-tagging candidates)

Purpose:
- Generate concern-tagging units from declared evidence and/or Lane C adjudicated excerpt outputs.

```sql
SELECT
  e.evidence_id AS unit_id,
  'topic_evidence' AS unit_type,
  t.label AS title,
  e.excerpt,
  sr.source_url
FROM topic_evidence e
LEFT JOIN topics t ON t.topic_id = e.topic_id
LEFT JOIN source_records sr ON sr.source_record_pk = e.source_record_pk
WHERE e.evidence_type LIKE 'declared:%'
  AND e.excerpt IS NOT NULL
  AND trim(e.excerpt) <> ''
ORDER BY e.evidence_id DESC
LIMIT 500;
```

## Lane E Baseline SQL (policy_events axis coding)

Purpose:
- Generate policy-event coding tasks for first bounded batch.

```sql
SELECT
  pe.policy_event_id,
  pe.event_date,
  pe.title,
  pe.summary,
  pe.source_id,
  pe.source_url
FROM policy_events pe
LEFT JOIN policy_event_axis_scores s
  ON s.policy_event_id = pe.policy_event_id
WHERE s.policy_event_id IS NULL
ORDER BY pe.event_date DESC, pe.policy_event_id DESC
LIMIT 120;
```

## Tracker Parity Command

```bash
python3 scripts/e2e_tracker_status.py \
  --db etl/data/staging/politicos-es.db \
  --tracker docs/etl/e2e-scrape-load-tracker.md \
  --waivers docs/etl/mismatch-waivers.json
```

Expected baseline parity:
- `mismatches=0`
- `waivers_active=0`
- `done_zero_real=0`

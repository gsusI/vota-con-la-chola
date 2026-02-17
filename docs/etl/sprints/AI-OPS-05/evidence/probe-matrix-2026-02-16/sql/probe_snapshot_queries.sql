-- Replace :source_id manually when running ad-hoc snapshots.

-- Latest run snapshot for one source.
SELECT
  run_id,
  source_id,
  status,
  records_seen,
  records_loaded,
  started_at,
  finished_at,
  duration_s,
  message,
  source_url
FROM ingestion_runs
WHERE run_id = (
  SELECT MAX(run_id) FROM ingestion_runs WHERE source_id = ':source_id'
);

-- Current source_records volume for one source.
SELECT
  source_id,
  COUNT(*) AS source_records_total
FROM source_records
WHERE source_id = ':source_id'
GROUP BY source_id;

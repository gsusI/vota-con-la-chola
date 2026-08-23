.headers on
.mode column

SELECT
  d.label AS indicator,
  s.geography_code,
  s.geography_name,
  s.geography_level,
  o.period_label,
  o.value_decimal,
  d.unit_code,
  COALESCE(o.source_status_code, 'none') AS source_status,
  o.revision_state,
  e.value_json_pointer,
  substr(e.source_content_sha256, 1, 16) || '...' AS source_sha256
FROM indicator_observation_versions AS o
JOIN indicator_series_versions AS s
  ON s.indicator_series_version_id = o.indicator_series_version_id
JOIN indicator_definitions AS d
  ON d.indicator_id = s.indicator_id
JOIN indicator_observation_evidence AS e
  ON e.indicator_observation_version_id = o.indicator_observation_version_id
WHERE s.geography_code IN ('ES', 'ES11', 'ES21', 'ES30', 'ES61')
  AND o.period_label = '2024'
ORDER BY s.geography_code;

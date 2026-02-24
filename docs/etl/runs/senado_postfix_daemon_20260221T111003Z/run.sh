#!/usr/bin/env bash
set -euo pipefail
DB="etl/data/staging/politicos-es.db"
q_done(){ sqlite3 "$DB" "SELECT SUM(CASE WHEN td.source_record_pk IS NOT NULL THEN 1 ELSE 0 END) FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id LEFT JOIN text_documents td ON td.source_record_pk=pid.source_record_pk AND td.source_id='parl_initiative_docs' WHERE i.source_id='senado_iniciativas';"; }
q_total(){ sqlite3 "$DB" "SELECT COUNT(*) FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id WHERE i.source_id='senado_iniciativas';"; }
START=$(q_done); TOTAL=$(q_total)
echo "start=$(date -u +%Y-%m-%dT%H:%M:%SZ) done=$START total=$TOTAL"
for r in $(seq 1 24); do
  BEFORE=$(q_done)
  OUT="${1}/round_${r}.json"
  python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
    --db "$DB" \
    --initiative-source-ids senado_iniciativas \
    --include-unlinked \
    --retry-forbidden \
    --limit-initiatives 220 \
    --max-docs-per-initiative 1 \
    --timeout 10 \
    --sleep-seconds 0 \
    --sleep-jitter-seconds 0 > "$OUT" 2>&1 || true
  FETCH_OK=$(python3 - <<'PY' "$OUT"
import json,sys
try:
  j=json.load(open(sys.argv[1]))
  print(int(j.get('documents',{}).get('fetched_ok',0)))
except Exception:
  print(0)
PY
)
  URLS=$(python3 - <<'PY' "$OUT"
import json,sys
try:
  j=json.load(open(sys.argv[1]))
  print(int(j.get('documents',{}).get('urls_to_fetch',0)))
except Exception:
  print(0)
PY
)
  AFTER=$(q_done)
  echo "ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) round=$r urls_to_fetch=$URLS fetched_ok=$FETCH_OK delta=$((AFTER-BEFORE)) done=$AFTER/$(q_total)"
  if [ $((AFTER-BEFORE)) -gt 0 ]; then sleep 90; else sleep 300; fi
done
END=$(q_done)
echo "end=$(date -u +%Y-%m-%dT%H:%M:%SZ) start=$START end=$END delta=$((END-START)) total=$(q_total)"

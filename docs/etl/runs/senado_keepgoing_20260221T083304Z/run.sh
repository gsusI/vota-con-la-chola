#!/usr/bin/env bash
set -euo pipefail
DB="etl/data/staging/politicos-es.db"
RUN_DIR="$1"
q_done(){
  sqlite3 "$DB" "SELECT SUM(CASE WHEN td.source_record_pk IS NOT NULL THEN 1 ELSE 0 END) FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id LEFT JOIN text_documents td ON td.source_record_pk=pid.source_record_pk AND td.source_id='parl_initiative_docs' WHERE i.source_id='senado_iniciativas';"
}
before="$(q_done)"
echo "run_dir=$RUN_DIR"
echo "before=$before"
for r in $(seq 1 15); do
  python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
    --db "$DB" \
    --initiative-source-ids senado_iniciativas \
    --include-unlinked \
    --limit-initiatives 4000 \
    --max-docs-per-initiative 1 \
    --timeout 10 \
    --sleep-seconds 0 \
    --sleep-jitter-seconds 0 > "$RUN_DIR/round_${r}_skip.json" || true

  sk_ok=$(python3 - <<'PY' "$RUN_DIR/round_${r}_skip.json"
import json,sys
try:
    j=json.load(open(sys.argv[1]))
    print(int(j.get('documents',{}).get('fetched_ok',0)))
except Exception:
    print(0)
PY
)
  sk_fetch=$(python3 - <<'PY' "$RUN_DIR/round_${r}_skip.json"
import json,sys
try:
    j=json.load(open(sys.argv[1]))
    print(int(j.get('documents',{}).get('urls_to_fetch',0)))
except Exception:
    print(0)
PY
)

  rp_ok=0
  if [ "$sk_fetch" -eq 0 ]; then
    python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
      --db "$DB" \
      --initiative-source-ids senado_iniciativas \
      --include-unlinked \
      --retry-forbidden \
      --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json \
      --limit-initiatives 80 \
      --max-docs-per-initiative 1 \
      --timeout 10 \
      --sleep-seconds 0 \
      --sleep-jitter-seconds 0 > "$RUN_DIR/round_${r}_retry.json" || true
    rp_ok=$(python3 - <<'PY' "$RUN_DIR/round_${r}_retry.json"
import json,sys
try:
    j=json.load(open(sys.argv[1]))
    print(int(j.get('documents',{}).get('fetched_ok',0)))
except Exception:
    print(0)
PY
)
  fi

  done_now="$(q_done)"
  echo "round=$r skip_ok=$sk_ok skip_fetch=$sk_fetch retry_ok=$rp_ok done=$done_now delta=$((done_now-before))"

  if [ "$done_now" -ge 7905 ]; then
    break
  fi

  if [ "$rp_ok" -eq 0 ] && [ "$sk_ok" -eq 0 ]; then
    sleep 30
  else
    sleep 8
  fi
done

after="$(q_done)"
echo "after=$after total_delta=$((after-before))"
sqlite3 -header -csv "$DB" <<'SQL'
SELECT COUNT(*) AS total_docs,
       SUM(CASE WHEN td.source_record_pk IS NOT NULL THEN 1 ELSE 0 END) AS downloaded_docs,
       SUM(CASE WHEN td.source_record_pk IS NULL THEN 1 ELSE 0 END) AS missing_docs,
       ROUND(100.0*SUM(CASE WHEN td.source_record_pk IS NOT NULL THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_downloaded
FROM parl_initiative_documents pid
JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id
LEFT JOIN text_documents td ON td.source_record_pk=pid.source_record_pk AND td.source_id='parl_initiative_docs'
WHERE i.source_id='senado_iniciativas';
SQL

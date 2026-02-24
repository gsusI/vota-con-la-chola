#!/usr/bin/env bash
set -u
cd "/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola"
round=0
while true; do
  round=$((round+1))
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] round=$round start"
  python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
    --db etl/data/staging/politicos-es.db \
    --initiative-source-ids senado_iniciativas \
    --include-unlinked \
    --limit-initiatives 4000 \
    --max-docs-per-initiative 1 \
    --timeout 10 \
    --sleep-seconds 0 \
    --sleep-jitter-seconds 0 || true
  python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
    --db etl/data/staging/politicos-es.db \
    --initiative-source-ids senado_iniciativas \
    --include-unlinked \
    --retry-forbidden \
    --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json \
    --limit-initiatives 60 \
    --max-docs-per-initiative 1 \
    --timeout 10 \
    --sleep-seconds 0 \
    --sleep-jitter-seconds 0 || true
  done_now=$(sqlite3 etl/data/staging/politicos-es.db "SELECT SUM(CASE WHEN td.source_record_pk IS NOT NULL THEN 1 ELSE 0 END) FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id LEFT JOIN text_documents td ON td.source_record_pk=pid.source_record_pk AND td.source_id='parl_initiative_docs' WHERE i.source_id='senado_iniciativas';")
  total=$(sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id WHERE i.source_id='senado_iniciativas';")
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] round=$round done=$done_now/$total"
  if [ "$done_now" -ge "$total" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] COMPLETE"
    exit 0
  fi
  sleep 60
done

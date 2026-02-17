#!/usr/bin/env bash
set -euo pipefail

SNAPSHOT_DATE="${SNAPSHOT_DATE:-2026-02-16}"
DB_PATH="${DB_PATH:-etl/data/staging/probe-matrix-20260216.db}"
EVID_DIR="docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16"
LOG_DIR="$EVID_DIR/logs"
SQL_DIR="$EVID_DIR/sql"

mkdir -p "$LOG_DIR" "$SQL_DIR"

capture_snapshot() {
  local source_id="$1"
  local mode="$2"
  sqlite3 -header -csv "$DB_PATH" \
    "SELECT run_id, source_id, status, records_seen, records_loaded, started_at, finished_at, duration_s, message, source_url FROM ingestion_runs WHERE run_id=(SELECT MAX(run_id) FROM ingestion_runs WHERE source_id='${source_id}');" \
    >"$SQL_DIR/${source_id}__${mode}__run_snapshot.csv"
  sqlite3 -header -csv "$DB_PATH" \
    "SELECT source_id, COUNT(*) AS source_records_total FROM source_records WHERE source_id='${source_id}' GROUP BY source_id;" \
    >"$SQL_DIR/${source_id}__${mode}__source_records_snapshot.csv"
}

run_probe() {
  local source_id="$1"
  local mode="$2"
  local from_file_path="$3"
  local stdout_file="$LOG_DIR/${source_id}__${mode}.stdout.log"
  local stderr_file="$LOG_DIR/${source_id}__${mode}.stderr.log"

  local cmd=(
    python3 scripts/ingestar_politicos_es.py ingest
    --db "$DB_PATH"
    --source "$source_id"
    --snapshot-date "$SNAPSHOT_DATE"
    --timeout 30
  )

  if [[ "$mode" == "strict-network" ]]; then
    cmd+=(--strict-network)
  else
    cmd+=(--from-file "$from_file_path")
  fi

  {
    printf '$ '
    printf '%q ' "${cmd[@]}"
    printf '\n'
  } >"$stdout_file"

  set +e
  "${cmd[@]}" >>"$stdout_file" 2>"$stderr_file"
  local exit_code=$?
  set -e

  printf 'exit_code=%s\n' "$exit_code" >>"$stdout_file"
  capture_snapshot "$source_id" "$mode"
}

python3 scripts/ingestar_politicos_es.py init-db --db "$DB_PATH" >"$LOG_DIR/init-db.stdout.log" 2>"$LOG_DIR/init-db.stderr.log"
sqlite3 -header -csv "$DB_PATH" \
  "SELECT run_id, source_id, status, records_seen, records_loaded FROM ingestion_runs ORDER BY run_id;" \
  >"$SQL_DIR/000_init_ingestion_runs.csv"

run_probe "moncloa_referencias" "strict-network" "etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216"
run_probe "moncloa_referencias" "from-file" "etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216"

run_probe "moncloa_rss_referencias" "strict-network" "etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216"
run_probe "moncloa_rss_referencias" "from-file" "etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216"

run_probe "parlamento_navarra_parlamentarios_forales" "strict-network" "etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages"
run_probe "parlamento_navarra_parlamentarios_forales" "from-file" "etl/data/raw/manual/navarra_persona_profiles_20260212T144911Z/pages"

run_probe "parlamento_galicia_deputados" "strict-network" "etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages"
run_probe "parlamento_galicia_deputados" "from-file" "etl/data/raw/manual/galicia_deputado_profiles_20260212T141929Z/pages"

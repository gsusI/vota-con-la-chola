#!/usr/bin/env bash
set -uo pipefail

DB_PATH="${DB_PATH:-etl/data/staging/politicos-es.db}"
COOKIE_FILE="${COOKIE_FILE:-etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json}"
BURST_LIMIT="${BURST_LIMIT:-120}"
WIDE_LIMIT="${WIDE_LIMIT:-4000}"
TIMEOUT_SECS="${TIMEOUT_SECS:-10}"
COOLDOWN_SECS="${COOLDOWN_SECS:-60}"
ACTIVE_SLEEP_SECS="${ACTIVE_SLEEP_SECS:-10}"
MAX_IDLE_ROUNDS="${MAX_IDLE_ROUNDS:-6}"
MAX_ROUNDS="${MAX_ROUNDS:-0}"
STOP_ON_UNIFORM_404="${STOP_ON_UNIFORM_404:-1}"
ARCHIVE_FALLBACK="${ARCHIVE_FALLBACK:-1}"
ARCHIVE_TIMEOUT="${ARCHIVE_TIMEOUT:-12}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUN_DIR:-docs/etl/runs/senado_tail_daemon_${STAMP}}"
mkdir -p "$RUN_DIR"

ARCHIVE_ARGS=()
if [ "$ARCHIVE_FALLBACK" = "1" ]; then
  ARCHIVE_ARGS=(--archive-fallback --archive-timeout "$ARCHIVE_TIMEOUT")
fi

q_total() {
  sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id WHERE i.source_id='senado_iniciativas';"
}

q_done() {
  sqlite3 "$DB_PATH" "SELECT SUM(CASE WHEN td.source_record_pk IS NOT NULL THEN 1 ELSE 0 END) FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id LEFT JOIN text_documents td ON td.source_record_pk=pid.source_record_pk AND td.source_id='parl_initiative_docs' WHERE i.source_id='senado_iniciativas';"
}

q_missing_total() {
  sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id LEFT JOIN text_documents td ON td.source_record_pk=pid.source_record_pk AND td.source_id='parl_initiative_docs' WHERE i.source_id='senado_iniciativas' AND td.source_record_pk IS NULL;"
}

q_missing_status() {
  local status="${1:-0}"
  sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id LEFT JOIN text_documents td ON td.source_record_pk=pid.source_record_pk AND td.source_id='parl_initiative_docs' LEFT JOIN document_fetches df ON df.doc_url=pid.doc_url WHERE i.source_id='senado_iniciativas' AND td.source_record_pk IS NULL AND COALESCE(df.last_http_status,0)=${status};"
}

write_stop_summary() {
  local reason="$1"
  local round="$2"
  local done="$3"
  local total="$4"
  local missing="$5"
  local m404="$6"
  local m403="$7"
  local m500="$8"
  local idle_rounds="$9"
  python3 - <<'PY' "$RUN_DIR/_stop_summary.json" "$reason" "$round" "$done" "$total" "$missing" "$m404" "$m403" "$m500" "$idle_rounds"
import json, sys
out, reason, round_n, done, total, missing, m404, m403, m500, idle_rounds = sys.argv[1:]
payload = {
    "stop_reason": reason,
    "round": int(round_n),
    "done": int(done),
    "total": int(total),
    "missing": int(missing),
    "missing_404": int(m404),
    "missing_403": int(m403),
    "missing_500": int(m500),
    "idle_rounds": int(idle_rounds),
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(out)
PY
}

json_int() {
  local file="$1"
  local expr="$2"
  python3 - <<'PY' "$file" "$expr"
import json,sys
path, expr = sys.argv[1], sys.argv[2]
try:
    with open(path, "r", encoding="utf-8") as f:
        j = json.load(f)
except Exception:
    print(0)
    raise SystemExit(0)
if expr == "retry_ok":
    print(int(j.get("documents",{}).get("fetched_ok",0)))
elif expr == "skip_ok":
    print(int(j.get("documents",{}).get("fetched_ok",0)))
elif expr == "skip_fetch":
    print(int(j.get("documents",{}).get("urls_to_fetch",0)))
else:
    print(0)
PY
}

TOTAL="$(q_total)"
ROUND=0
IDLE_ROUNDS=0

echo "run_dir=$RUN_DIR"
echo "start done=$(q_done) total=$TOTAL"

while true; do
  ROUND=$((ROUND + 1))
  BEFORE="$(q_done)"

  python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
    --db "$DB_PATH" \
    --initiative-source-ids senado_iniciativas \
    --include-unlinked \
    --retry-forbidden \
    --cookie-file "$COOKIE_FILE" \
    --limit-initiatives "$BURST_LIMIT" \
    --max-docs-per-initiative 1 \
    --timeout "$TIMEOUT_SECS" \
    --sleep-seconds 0 \
    --sleep-jitter-seconds 0 \
    "${ARCHIVE_ARGS[@]}" > "$RUN_DIR/round_${ROUND}_retry_cookie.json" 2>&1 || true

  python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
    --db "$DB_PATH" \
    --initiative-source-ids senado_iniciativas \
    --include-unlinked \
    --limit-initiatives "$WIDE_LIMIT" \
    --max-docs-per-initiative 1 \
    --timeout "$TIMEOUT_SECS" \
    --sleep-seconds 0 \
    --sleep-jitter-seconds 0 \
    "${ARCHIVE_ARGS[@]}" > "$RUN_DIR/round_${ROUND}_skip_wide.json" 2>&1 || true

  RETRY_OK="$(json_int "$RUN_DIR/round_${ROUND}_retry_cookie.json" "retry_ok")"
  SKIP_OK="$(json_int "$RUN_DIR/round_${ROUND}_skip_wide.json" "skip_ok")"
  SKIP_FETCH="$(json_int "$RUN_DIR/round_${ROUND}_skip_wide.json" "skip_fetch")"

  AFTER="$(q_done)"
  MISSING_TOTAL="$(q_missing_total)"
  MISSING_404="$(q_missing_status 404)"
  MISSING_403="$(q_missing_status 403)"
  MISSING_500="$(q_missing_status 500)"
  DELTA=$((AFTER - BEFORE))
  echo "round=$ROUND retry_ok=$RETRY_OK skip_ok=$SKIP_OK skip_urls_to_fetch=$SKIP_FETCH delta=$DELTA done=$AFTER/$TOTAL missing=$MISSING_TOTAL m404=$MISSING_404 m403=$MISSING_403 m500=$MISSING_500 idle_rounds=$IDLE_ROUNDS"

  if [ "$DELTA" -gt 0 ]; then
    IDLE_ROUNDS=0
  else
    IDLE_ROUNDS=$((IDLE_ROUNDS + 1))
  fi

  if [ "$AFTER" -ge "$TOTAL" ]; then
    echo "COMPLETE round=$ROUND done=$AFTER total=$TOTAL"
    write_stop_summary "complete" "$ROUND" "$AFTER" "$TOTAL" "$MISSING_TOTAL" "$MISSING_404" "$MISSING_403" "$MISSING_500" "$IDLE_ROUNDS" >/dev/null
    exit 0
  fi

  if [ "$STOP_ON_UNIFORM_404" -eq 1 ] && [ "$MISSING_TOTAL" -gt 0 ] && [ "$MISSING_404" -eq "$MISSING_TOTAL" ]; then
    echo "STOP uniform_404_tail round=$ROUND missing=$MISSING_TOTAL"
    write_stop_summary "uniform_404_tail" "$ROUND" "$AFTER" "$TOTAL" "$MISSING_TOTAL" "$MISSING_404" "$MISSING_403" "$MISSING_500" "$IDLE_ROUNDS" >/dev/null
    exit 0
  fi

  if [ "$MAX_ROUNDS" -gt 0 ] && [ "$ROUND" -ge "$MAX_ROUNDS" ]; then
    echo "STOP max_rounds round=$ROUND done=$AFTER total=$TOTAL"
    write_stop_summary "max_rounds" "$ROUND" "$AFTER" "$TOTAL" "$MISSING_TOTAL" "$MISSING_404" "$MISSING_403" "$MISSING_500" "$IDLE_ROUNDS" >/dev/null
    exit 0
  fi

  if [ "$IDLE_ROUNDS" -ge "$MAX_IDLE_ROUNDS" ]; then
    echo "STOP no_progress round=$ROUND idle_rounds=$IDLE_ROUNDS"
    write_stop_summary "no_progress" "$ROUND" "$AFTER" "$TOTAL" "$MISSING_TOTAL" "$MISSING_404" "$MISSING_403" "$MISSING_500" "$IDLE_ROUNDS" >/dev/null
    exit 0
  fi

  if [ "$DELTA" -gt 0 ]; then
    sleep "$ACTIVE_SLEEP_SECS"
  else
    sleep "$COOLDOWN_SECS"
  fi
done

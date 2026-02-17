#!/usr/bin/env bash
set -u
set -o pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/run_source_probe_matrix.sh [options]

Execute rows from source probe matrix and write deterministic logs/artifacts.

Options:
  --matrix PATH           Probe matrix TSV/CSV (default: docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv)
  --out-dir PATH          Override output root; writes PATH/logs and PATH/sql (keeps deterministic row_id filenames)
  --db PATH               Override --db in matrix ingest commands
  --snapshot-date DATE    Override --snapshot-date in matrix ingest commands (YYYY-MM-DD)
  --row-id ID             Execute only one row_id
  --source-id ID          Execute only one source_id
  --mode MODE             Execute only one mode (strict-network|from-file|replay)
  --allow-failures        Exit 0 even if some rows fail
  --dry-run               Do not execute ingest commands; emit summary entries only
  -h, --help              Show help
EOF
}

MATRIX="docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv"
OUT_DIR=""
DB_OVERRIDE=""
SNAPSHOT_OVERRIDE=""
ROW_FILTER=""
SOURCE_FILTER=""
MODE_FILTER=""
ALLOW_FAILURES=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --matrix)
      MATRIX="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --db)
      DB_OVERRIDE="${2:-}"
      shift 2
      ;;
    --snapshot-date)
      SNAPSHOT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --row-id)
      ROW_FILTER="${2:-}"
      shift 2
      ;;
    --source-id)
      SOURCE_FILTER="${2:-}"
      shift 2
      ;;
    --mode)
      MODE_FILTER="${2:-}"
      shift 2
      ;;
    --allow-failures)
      ALLOW_FAILURES=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$MATRIX" ]]; then
  echo "ERROR matrix not found: $MATRIX" >&2
  exit 2
fi

if [[ -n "$SNAPSHOT_OVERRIDE" ]]; then
  if ! python3 - "$SNAPSHOT_OVERRIDE" <<'PY'
import datetime as dt
import sys
dt.date.fromisoformat(sys.argv[1].strip())
PY
  then
    echo "ERROR invalid --snapshot-date (expected YYYY-MM-DD): $SNAPSHOT_OVERRIDE" >&2
    exit 2
  fi
fi

ROWS_TMP="$(mktemp "${TMPDIR:-/tmp}/source_probe_rows.XXXXXX")"
cleanup() {
  rm -f "$ROWS_TMP"
}
trap cleanup EXIT

python3 - "$MATRIX" "$ROWS_TMP" "$ROW_FILTER" "$SOURCE_FILTER" "$MODE_FILTER" <<'PY'
import csv
import pathlib
import sys

matrix_path = pathlib.Path(sys.argv[1])
rows_path = pathlib.Path(sys.argv[2])
row_filter = sys.argv[3].strip()
source_filter = sys.argv[4].strip()
mode_filter = sys.argv[5].strip()

content = matrix_path.read_text(encoding="utf-8")
lines = content.splitlines()
if not lines:
    raise SystemExit(f"matrix vacia: {matrix_path}")

header = lines[0]
delimiter = "\t" if "\t" in header else ","
reader = csv.DictReader(lines, delimiter=delimiter)
required = [
    "row_id",
    "source_id",
    "mode",
    "snapshot_date",
    "ingest_command",
    "expected_stdout_log",
    "expected_stderr_log",
    "expected_run_snapshot_csv",
    "expected_source_records_snapshot_csv",
]
missing = [key for key in required if key not in (reader.fieldnames or [])]
if missing:
    raise SystemExit(f"matrix missing required columns: {', '.join(missing)}")

count = 0
with rows_path.open("w", encoding="utf-8", newline="") as out:
    for row in reader:
        if row_filter and row.get("row_id", "").strip() != row_filter:
            continue
        if source_filter and row.get("source_id", "").strip() != source_filter:
            continue
        if mode_filter and row.get("mode", "").strip() != mode_filter:
            continue

        values: list[str] = []
        for key in required:
            token = str(row.get(key, "")).replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()
            values.append(token)
        out.write("\t".join(values) + "\n")
        count += 1

if count == 0:
    raise SystemExit("matrix filters produced zero rows")
PY

if [[ -n "$OUT_DIR" ]]; then
  SUMMARY_PATH="${OUT_DIR%/}/probe_runner_summary.tsv"
else
  SUMMARY_PATH="$(dirname "$MATRIX")/source_probe_matrix.run-summary.tsv"
fi
mkdir -p "$(dirname "$SUMMARY_PATH")"
printf "row_id\tsource_id\tmode\tstatus\texit_code\tstarted_at\tfinished_at\tstdout_log\tstderr_log\trun_snapshot_csv\tsource_records_snapshot_csv\tnote\n" > "$SUMMARY_PATH"

TOTAL=0
OK=0
FAILED=0

while IFS=$'\t' read -r row_id source_id mode row_snapshot ingest_command expected_stdout expected_stderr expected_run_snapshot expected_source_snapshot; do
  TOTAL=$((TOTAL + 1))

  if [[ -n "$OUT_DIR" ]]; then
    stdout_log="${OUT_DIR%/}/logs/${row_id}.stdout.log"
    stderr_log="${OUT_DIR%/}/logs/${row_id}.stderr.log"
    run_snapshot_csv="${OUT_DIR%/}/sql/${row_id}_run_snapshot.csv"
    source_snapshot_csv="${OUT_DIR%/}/sql/${row_id}_source_records_snapshot.csv"
  else
    stdout_log="$expected_stdout"
    stderr_log="$expected_stderr"
    run_snapshot_csv="$expected_run_snapshot"
    source_snapshot_csv="$expected_source_snapshot"
  fi

  mkdir -p "$(dirname "$stdout_log")" "$(dirname "$stderr_log")" "$(dirname "$run_snapshot_csv")" "$(dirname "$source_snapshot_csv")"

  command_to_run="$(python3 - "$ingest_command" "$DB_OVERRIDE" "$SNAPSHOT_OVERRIDE" <<'PY'
import shlex
import sys

command = sys.argv[1]
db_override = sys.argv[2].strip()
snapshot_override = sys.argv[3].strip()

tokens = shlex.split(command)

def set_arg(flag: str, value: str) -> None:
    if not value:
        return
    if flag in tokens:
        idx = tokens.index(flag)
        if idx + 1 < len(tokens):
            tokens[idx + 1] = value
        else:
            tokens.append(value)
    else:
        tokens.extend([flag, value])

set_arg("--db", db_override)
set_arg("--snapshot-date", snapshot_override)
print(" ".join(shlex.quote(token) for token in tokens))
PY
)"

  db_effective="$(python3 - "$ingest_command" "$DB_OVERRIDE" <<'PY'
import shlex
import sys

command = sys.argv[1]
override = sys.argv[2].strip()
tokens = shlex.split(command)
db = ""
if "--db" in tokens:
    idx = tokens.index("--db")
    if idx + 1 < len(tokens):
        db = tokens[idx + 1]
if override:
    db = override
print(db)
PY
)"

  snapshot_effective="$(python3 - "$row_snapshot" "$SNAPSHOT_OVERRIDE" "$ingest_command" <<'PY'
import shlex
import sys

row_snapshot = sys.argv[1].strip()
override = sys.argv[2].strip()
command = sys.argv[3]

if override:
    print(override)
    raise SystemExit(0)
if row_snapshot:
    print(row_snapshot)
    raise SystemExit(0)

tokens = shlex.split(command)
snapshot = ""
if "--snapshot-date" in tokens:
    idx = tokens.index("--snapshot-date")
    if idx + 1 < len(tokens):
        snapshot = tokens[idx + 1]
print(snapshot)
PY
)"

  started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  {
    echo "# row_id=${row_id}"
    echo "# source_id=${source_id}"
    echo "# mode=${mode}"
    echo "# started_at=${started_at}"
    echo "# command=${command_to_run}"
  } > "$stdout_log"
  : > "$stderr_log"

  exit_code=0
  status="ok"
  note=""

  if [[ "$DRY_RUN" -eq 1 ]]; then
    status="dry-run"
  else
    bash -lc "$command_to_run" >> "$stdout_log" 2>> "$stderr_log"
    exit_code=$?
    if [[ "$exit_code" -ne 0 ]]; then
      status="error"
      tail_note="$(tail -n 1 "$stderr_log" | tr '\t\r\n' '   ' | sed 's/  */ /g')"
      note="command_exit=${exit_code}"
      if [[ -n "$tail_note" ]]; then
        note="${note}; tail=${tail_note}"
      fi
    fi

    if [[ -n "$db_effective" ]]; then
      python3 scripts/ingestar_politicos_es.py export-run-snapshot \
        --db "$db_effective" \
        --source-id "$source_id" \
        --mode "$mode" \
        --command "$command_to_run" \
        --snapshot-date "$snapshot_effective" \
        --out "$run_snapshot_csv" >> "$stdout_log" 2>> "$stderr_log" || {
          status="error"
          if [[ -z "$note" ]]; then
            note="export_run_snapshot_failed"
          else
            note="${note}; export_run_snapshot_failed"
          fi
        }

      python3 - "$db_effective" "$source_id" "$source_snapshot_csv" >> "$stdout_log" 2>> "$stderr_log" <<'PY'
import csv
import datetime as dt
import sqlite3
import sys
from pathlib import Path

db_path = sys.argv[1]
source_id = sys.argv[2]
out_path = Path(sys.argv[3])
out_path.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
try:
    run = conn.execute(
        """
        SELECT run_id, status, records_seen, records_loaded, started_at, finished_at, message
        FROM ingestion_runs
        WHERE source_id = ?
        ORDER BY run_id DESC
        LIMIT 1
        """,
        (source_id,),
    ).fetchone()
    total = conn.execute(
        "SELECT COUNT(*) AS c FROM source_records WHERE source_id = ?",
        (source_id,),
    ).fetchone()
finally:
    conn.close()

with out_path.open("w", encoding="utf-8", newline="") as fh:
    writer = csv.writer(fh, lineterminator="\n")
    writer.writerow(
        [
            "source_id",
            "run_id",
            "run_status",
            "run_records_seen",
            "run_records_loaded",
            "source_records_total",
            "run_started_at",
            "run_finished_at",
            "message",
            "generated_at",
        ]
    )
    writer.writerow(
        [
            source_id,
            "" if run is None else run["run_id"],
            "" if run is None else run["status"],
            "" if run is None else run["records_seen"],
            "" if run is None else run["records_loaded"],
            "" if total is None else total["c"],
            "" if run is None else run["started_at"],
            "" if run is None else run["finished_at"],
            "" if run is None else (run["message"] or ""),
            dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        ]
    )
PY
    else
      status="error"
      if [[ -z "$note" ]]; then
        note="missing_db_arg"
      else
        note="${note}; missing_db_arg"
      fi
    fi
  fi

  finished_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$row_id" \
    "$source_id" \
    "$mode" \
    "$status" \
    "$exit_code" \
    "$started_at" \
    "$finished_at" \
    "$stdout_log" \
    "$stderr_log" \
    "$run_snapshot_csv" \
    "$source_snapshot_csv" \
    "$note" >> "$SUMMARY_PATH"

  if [[ "$status" == "ok" || "$status" == "dry-run" ]]; then
    OK=$((OK + 1))
  else
    FAILED=$((FAILED + 1))
  fi
done < "$ROWS_TMP"

echo "Probe matrix execution completed."
echo "summary_path=${SUMMARY_PATH}"
echo "rows_total=${TOTAL}"
echo "rows_ok=${OK}"
echo "rows_failed=${FAILED}"

if [[ "$FAILED" -gt 0 && "$ALLOW_FAILURES" -ne 1 ]]; then
  exit 1
fi
exit 0

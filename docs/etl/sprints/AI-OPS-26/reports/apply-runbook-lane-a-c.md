# Apply Runbook (lane_a / lane_c)

Scope:
- `lane_a`: real apply to `topic_evidence_reviews` + mandatory recompute.
- `lane_c`: apply-preview only (no DB mutation in T1-T5).

## Inputs

Required:
- `DB=etl/data/staging/politicos-es.db`
- `AS_OF_DATE=2026-02-17` (or explicit runtime date)
- `LANE_A_DECISIONS=docs/etl/sprints/AI-OPS-26/exports/factory/lane_a/<batch_id>/decisions_adjudicated.csv`
- `LANE_C_PATCH=docs/etl/sprints/AI-OPS-26/exports/factory/lane_c/<batch_id>/sql_patch.csv`

## safety prechecks

1. Verify files exist.
2. Verify lane_a headers exactly.
3. Verify lane_c patch key uniqueness (`source_record_pk` + `doc_url`).
4. Capture before/after snapshots for queue and positions.

```bash
set -euo pipefail

test -f "$LANE_A_DECISIONS"
head -n1 "$LANE_A_DECISIONS" | rg "batch_id,evidence_id,proposed_status,proposed_final_stance,agreement_ratio,adjudicator_note"

sqlite3 "$DB" "
SELECT 'pending_before', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='programas_partidos' AND status='pending';
SELECT 'resolved_before', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='programas_partidos' AND status='resolved';
SELECT 'ignored_before', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='programas_partidos' AND status='ignored';
" | tee docs/etl/sprints/AI-OPS-26/evidence/lane_a_before.txt
```

## lane_a apply (review-decision)

Apply policy:
- `proposed_status=resolved` rows are applied by final stance buckets.
- `proposed_status=ignored` rows are applied without stance.
- Run dry-run first, then real apply.

### 1) Dry-run buckets

```bash
for stance in support oppose mixed unclear no_signal; do
  ids=$(awk -F, -v s="$stance" 'NR>1 && $3=="resolved" && $4==s {print $2}' "$LANE_A_DECISIONS" | paste -sd, -)
  if [ -n "$ids" ]; then
    python3 scripts/ingestar_parlamentario_es.py review-decision \
      --db "$DB" \
      --source-id programas_partidos \
      --evidence-ids "$ids" \
      --status resolved \
      --final-stance "$stance" \
      --note "AI-OPS-26 lane_a dry-run" \
      --dry-run
  fi
done

ids_ignored=$(awk -F, 'NR>1 && $3=="ignored" {print $2}' "$LANE_A_DECISIONS" | paste -sd, -)
if [ -n "$ids_ignored" ]; then
  python3 scripts/ingestar_parlamentario_es.py review-decision \
    --db "$DB" \
    --source-id programas_partidos \
    --evidence-ids "$ids_ignored" \
    --status ignored \
    --note "AI-OPS-26 lane_a dry-run" \
    --dry-run
fi
```

### 2) Real apply buckets

```bash
for stance in support oppose mixed unclear no_signal; do
  ids=$(awk -F, -v s="$stance" 'NR>1 && $3=="resolved" && $4==s {print $2}' "$LANE_A_DECISIONS" | paste -sd, -)
  if [ -n "$ids" ]; then
    python3 scripts/ingestar_parlamentario_es.py review-decision \
      --db "$DB" \
      --source-id programas_partidos \
      --evidence-ids "$ids" \
      --status resolved \
      --final-stance "$stance" \
      --note "AI-OPS-26 lane_a apply"
  fi
done

ids_ignored=$(awk -F, 'NR>1 && $3=="ignored" {print $2}' "$LANE_A_DECISIONS" | paste -sd, -)
if [ -n "$ids_ignored" ]; then
  python3 scripts/ingestar_parlamentario_es.py review-decision \
    --db "$DB" \
    --source-id programas_partidos \
    --evidence-ids "$ids_ignored" \
    --status ignored \
    --note "AI-OPS-26 lane_a apply"
fi
```

## recompute (mandatory after lane_a apply)

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions \
  --db "$DB" \
  --source-id programas_partidos \
  --as-of-date "$AS_OF_DATE"

python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions \
  --db "$DB" \
  --as-of-date "$AS_OF_DATE"
```

## lane_a safety postchecks (before/after)

```bash
sqlite3 "$DB" "
SELECT 'pending_after', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='programas_partidos' AND status='pending';
SELECT 'resolved_after', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='programas_partidos' AND status='resolved';
SELECT 'ignored_after', COUNT(*)
FROM topic_evidence_reviews
WHERE source_id='programas_partidos' AND status='ignored';
SELECT 'declared_positions_after', COUNT(*)
FROM topic_positions
WHERE computed_method='declared';
SELECT 'combined_positions_after', COUNT(*)
FROM topic_positions
WHERE computed_method='combined';
" | tee docs/etl/sprints/AI-OPS-26/evidence/lane_a_after.txt
```

PASS condition:
- `pending_after < pending_before` and recompute commands complete.

## lane_c apply-preview (no mutation)

Goal:
- Validate patch quality before any `UPDATE text_documents`.

### 1) safety checks

```bash
set -euo pipefail

test -f "$LANE_C_PATCH"
head -n1 "$LANE_C_PATCH" | rg "source_record_pk,doc_url,final_excerpt_text,final_excerpt_chars"

awk -F, 'NR>1 {k=$1"|"$2; c[k]++} END{for (k in c) if (c[k]>1) {print k","c[k]; bad=1} exit bad}' "$LANE_C_PATCH"
```

### 2) preview join coverage and null checks

```bash
sqlite3 "$DB" <<SQL
.mode csv
CREATE TEMP TABLE lane_c_patch (
  source_record_pk INTEGER,
  doc_url TEXT,
  final_excerpt_text TEXT,
  final_excerpt_chars INTEGER
);
.import '$LANE_C_PATCH' lane_c_patch
DELETE FROM lane_c_patch WHERE source_record_pk='source_record_pk';

SELECT 'lane_c_patch_rows', COUNT(*) FROM lane_c_patch;
SELECT 'lane_c_target_rows', COUNT(*)
FROM text_documents td
JOIN lane_c_patch p
  ON p.source_record_pk = td.source_record_pk
 AND p.doc_url = td.source_url
WHERE td.source_id='parl_initiative_docs';
SELECT 'lane_c_null_excerpt_rows', COUNT(*)
FROM lane_c_patch
WHERE final_excerpt_text IS NULL OR trim(final_excerpt_text)='';
SQL
```

Note:
- lane_c apply SQL is intentionally deferred to post-factory gate after QA approval.

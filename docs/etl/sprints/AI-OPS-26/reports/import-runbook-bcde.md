# Import Runbook BCDE (AI-OPS-26)

Scope:
- Defines apply preconditions for non-applied lanes from this sprint.
- No schema migration, no policy changes.

## lane_b preconditions (name resolution)

Required:
- `decisions_adjudicated.csv` exists and validated.
- `final_decision=match` rows have non-empty `final_person_id`.
- Ambiguous/no_match rows are excluded from apply set.

Apply strategy:
1. Build an apply subset from `final_decision=match` only.
2. Join subset to `parl_vote_member_votes` by `source_id + member_name_normalized`.
3. Update `person_id` only when current `person_id IS NULL`.
4. Emit before/after unresolved counters.

Hold criteria:
- if `final_decision=ambiguous` exceeds `25%` of rows, keep full lane on hold.

## lane_c preconditions (excerpt patch)

Required:
- `sql_patch.csv` key uniqueness: `source_record_pk + doc_url`.
- `final_excerpt_text` non-empty for apply subset.
- `matched_target_rows == patch_rows` in preview report.

Apply strategy:
1. Load patch CSV to temp table.
2. `UPDATE text_documents SET text_excerpt=?, text_chars=? WHERE source_record_pk=? AND source_url=?`.
3. Restrict updates to `source_id='parl_initiative_docs'`.
4. Emit updated row count and remaining missing excerpt count.

Hold criteria:
- any duplicate keys or null excerpt rows in apply subset.

## lane_d preconditions (concern tags)

Required:
- `primary_concern_id` must be included in `final_concern_ids_csv`.
- concern ids must exist in `ui/citizen/concerns_v1.json`.

Apply strategy:
1. Load adjudicated concern tags into staging table.
2. Apply as derived metadata table (recommended: separate table, not overwrite source evidence).
3. Keep source linkage (`unit_type`, `unit_id`, `source_url`).

Hold criteria:
- unknown concern IDs or malformed CSV lists.

## lane_e preconditions (policy axis)

Required:
- `final_direction in {-1,0,1}`.
- `final_intensity` and `final_confidence` in `[0,1]`.
- `policy_event_id` exists in `policy_events`.

Apply strategy:
1. Insert/upsert into `policy_event_axis_scores` from adjudicated rows.
2. Preserve source metadata in audit fields or staging artifacts.
3. Emit counts by axis and direction.

Hold criteria:
- enum/numeric validation failures > 0.

## common safeguards

- run dry-run validation before any write.
- capture before/after KPI snapshots.
- if any precondition fails: keep lane `hold_for_review` and log reason.

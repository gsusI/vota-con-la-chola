# Factory Contract v2 (AI-OPS-26)

Contract version:
- `factory_contract_v2`

Applies to lanes:
- `lane_a`, `lane_b`, `lane_c`, `lane_d`, `lane_e`

## Shared Files (per batch)

Required files:
- `manifest.json`
- `tasks_input.csv`
- `workers_raw.csv` (or `workers_raw_pass1.csv` + `workers_raw_pass2.csv` when dual-pass)
- `decisions_adjudicated.csv`
- `qa_report.md`

All CSV files must:
- Be UTF-8.
- Include exactly one header row (exact column names, exact order).
- Use comma delimiter.
- Use empty string for nulls (no `NULL` literal).

## manifest.json (required keys)

Required keys:
- `contract_version` (must equal `factory_contract_v2`)
- `batch_id`
- `lane_id`
- `generated_at_utc` (ISO-8601)
- `generator`
- `db_path`
- `source_sql`
- `source_sql_sha256`
- `tasks_row_count`
- `notes`

Optional keys:
- `input_artifacts`
- `upstream_batch_ids`
- `warnings`

## Enum and numeric rules

Global enum rules:
- `status`: `pending|resolved|ignored` (when present)
- `final_decision`: `match|ambiguous|no_match`
- `direction`: `-1|0|1`
- `confidence` (numeric): `[0,1]`
- `agreement_ratio` (numeric): `[0,1]`

Validation rules:
- Every `decisions_adjudicated.csv` must have unique unit key per lane.
- Any row with invalid enum value is rejected.
- Any row with numeric out-of-range value is rejected.

## Lane A (stance review)

`tasks_input.csv` header:
- `batch_id,evidence_id,person_name,topic_label,evidence_excerpt,evidence_date,source_url,review_reason`

`workers_raw.csv` header:
- `batch_id,evidence_id,worker_id,worker_stance,worker_confidence,worker_note`

`decisions_adjudicated.csv` header:
- `batch_id,evidence_id,proposed_status,proposed_final_stance,agreement_ratio,adjudicator_note`

Lane A enum:
- `worker_stance|proposed_final_stance`: `support|oppose|mixed|unclear|no_signal`
- `proposed_status`: `resolved|ignored`

Lane A nullability:
- `proposed_final_stance` may be empty only when `proposed_status=ignored`.

## Lane B (name resolution)

`tasks_input.csv` header:
- `batch_id,source_id,member_name_normalized,member_name_example,group_code_example,legislature_example,candidate_person_ids_json,candidate_names_json,candidate_party_json,task_note`

`workers_raw_pass1.csv` / `workers_raw_pass2.csv` header:
- `batch_id,source_id,member_name_normalized,worker_id,selected_person_id,decision,worker_confidence,worker_note`

`decisions_adjudicated.csv` header:
- `batch_id,source_id,member_name_normalized,final_decision,final_person_id,agreement_ratio,adjudicator_note`

Lane B enum:
- `decision|final_decision`: `match|ambiguous|no_match`

Lane B nullability:
- `selected_person_id` required when `decision=match`; empty otherwise.
- `final_person_id` required when `final_decision=match`; empty otherwise.

## Lane C (initiative document excerpt)

`tasks_input.csv` header:
- `batch_id,doc_url,initiative_id,doc_kind,content_type,source_record_pk,raw_path`

`workers_raw_excerpts.csv` header:
- `batch_id,doc_url,worker_id,excerpt_text,excerpt_chars,worker_note`

`workers_raw_quotes.csv` header:
- `batch_id,doc_url,worker_id,quote_1,quote_2,summary_1to3_sentences`

`decisions_adjudicated.csv` header:
- `batch_id,doc_url,final_excerpt_text,final_excerpt_chars,final_quote_1,final_quote_2,final_summary_1to3_sentences,adjudicator_note`

Lane C constraints:
- `final_excerpt_chars` must equal character length of `final_excerpt_text`.
- `final_excerpt_chars` max recommended bound: `4000`.

## Lane D (concern tagging)

`tasks_input.csv` header:
- `batch_id,unit_type,unit_id,title,excerpt,source_url,allowed_concerns_json`

`workers_raw.csv` header:
- `batch_id,unit_type,unit_id,worker_id,concern_ids_csv,primary_concern_id,confidence,worker_note`

`decisions_adjudicated.csv` header:
- `batch_id,unit_type,unit_id,final_concern_ids_csv,primary_concern_id,agreement_ratio,adjudicator_note`

Lane D enum:
- `confidence`: `high|medium|low`

Lane D constraints:
- `primary_concern_id` must be included in `concern_ids_csv`.
- Max 3 concerns per unit.

## Lane E (policy axis coding)

`tasks_input.csv` header:
- `batch_id,policy_event_id,event_date,title,summary,source_id,source_url,domain_hint,candidate_axes_json`

`workers_raw_pass1.csv` / `workers_raw_pass2.csv` header:
- `batch_id,policy_event_id,worker_id,policy_axis_key,direction,intensity,confidence,worker_note`

`decisions_adjudicated.csv` header:
- `batch_id,policy_event_id,policy_axis_key,final_direction,final_intensity,final_confidence,agreement_ratio,adjudicator_note`

Lane E enum:
- `direction|final_direction`: `-1|0|1`

Lane E numeric constraints:
- `intensity|final_intensity`: `[0,1]`
- `confidence|final_confidence`: `[0,1]`

## Rejection Policy

Reject entire batch when:
- Header mismatch in any required CSV.
- Missing `manifest.json` keys.
- Duplicate lane unit keys in `decisions_adjudicated.csv`.
- Invalid enum values above `0` tolerance.

Accept with warnings when:
- Non-critical free-text cleanup needed in notes.
- Row-level rejects `<= 5%` and traceability keys remain valid.

Mandatory QA outputs (`qa_report.md`):
- `rows_total`
- `rows_accepted`
- `rows_rejected`
- `reject_reason_breakdown`
- `enum_violations`
- `duplicate_key_count`
- `agreement_ratio_summary`

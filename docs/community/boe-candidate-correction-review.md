# BOE candidate correction review

This lane converts official BOE correction text into reconstructable candidate-state operations. It never edits the immutable proclamation rows and never guesses a missing identifier.

## Current public work packet

- `776` exact paragraphs from `8` official correction documents.
- `776` stable dual-review tasks with blank decisions.
- `3,713` pending candidacies and `31,241` exact public candidate rows in one deduplicated JSONL context corpus.
- All names, official text, BOE URLs, checksums, source positions, chambers, districts and candidacy numbers remain intact.

Generate or validate the packet:

```bash
just etl-scale-boe-election-candidate-correction-review-queue
python3 -m unittest tests.test_prepare_boe_candidate_correction_review_queue tests.test_report_scale_readiness -v
just etl-scale-readiness
```

Artifacts:

- Tasks: `docs/etl/sprints/SCALE-FOUNDATION-20260810/exports/boe-candidate-correction-review-queue.csv`
- Deduplicated candidate context: `docs/etl/sprints/SCALE-FOUNDATION-20260810/exports/boe-candidate-correction-review-context.jsonl`
- Machine report: `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-candidate-correction-review-queue.json`

## Review protocol

1. Reserve one correction document in a public issue or PR before editing.
2. Open each task's official `source_url`. Compare `source_text_exact` with the BOE page and checksum-bound raw capture.
3. Use `suggested_candidacy_ids_json` only as a structural hint. Resolve the full candidacy and candidate rows from the context JSONL. Never match people across sources by name alone.
4. Fill only the `reviewer_1_*` or `reviewer_2_*` fields assigned to you. Do not edit source, scope, fingerprint or context fields.
5. Use a public contributor handle or a governance-issued opaque reviewer ID. Do not put an email address, workstation username or private account identifier in the queue.
6. Reviewer 2 must be a different human. At least one of the two reviewers must use independence class `independent`.
7. If the two decisions or operation specs differ, a third person must fill every adjudication field.
8. Regenerate the queue. Identical evidence preserves completed review fields. Evidence, schema or task removal after human work fails closed.

Allowed decisions:

| Decision | Meaning | Operation spec |
| --- | --- | --- |
| `operation_evidence` | This paragraph supports one or more exact state changes. | Required |
| `context_only` | Official context, heading or explanatory text; no direct state change. | Must be blank |
| `needs_more_evidence` | The exact effect cannot yet be reconstructed safely. | Must be blank |

Every completed reviewer slot requires reviewer ID, independence class, decision, rationale and ISO-8601 timestamp. Partial slots fail validation.

## Operation-spec contract

`*_operation_spec_json` must be a JSON object containing a non-empty `operations` list. Each operation requires:

- `operation_type`: `replace_candidacy_name`, `replace_candidate_slot`, `replace_candidate_list`, or `replace_candidacy_status_and_list`;
- `base_document_id`: one of the task's exact target proclamation IDs;
- `candidacy_id`: the exact `boe-candidacy:*` identity from the context corpus;
- `before_value` and `after_value`: distinct values copied from immutable base and correction evidence;
- `evidence_paragraph_numbers`: positive BOE paragraph numbers, including the current task paragraph.

Candidate operations may also include `candidate_type_code`, `candidate_order`, and `substitute_for_candidate_order`. Unknown keys, invalid slot numbers, unsupported operation types, out-of-scope documents, equal before/after values, and missing current-paragraph evidence fail validation.

## Completion gate

A correction document is ready for materialization only when:

- every paragraph has two valid human reviews;
- every disagreement is adjudicated;
- accepted operation specs reconcile to the same immutable base document;
- the materializer reproduces exact before/after state and source evidence;
- base tables remain unchanged;
- effective candidates, candidacies, operations, source records and FK checks balance;
- central readiness passes.

Until then, the affected `31,241` base candidate rows remain visible as captured official evidence but excluded from effective candidate state.

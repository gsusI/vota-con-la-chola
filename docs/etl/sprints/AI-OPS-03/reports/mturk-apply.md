# MTurk apply report: ai-ops-03 (2026-02-16 12:32:08)

## Inputs
- DB: `etl/data/staging/politicos-es.db`
- Source: `congreso_intervenciones`
- Snapshot date: `2026-02-12`

## Commands run
- Validation pass: Python script iterating `etl/data/raw/manual/mturk_reviews/mturk-20260216-congreso-*` with schema checks and pending-gate checks
- Recompute: `python3 -m etl.parlamentario_es.cli backfill-declared-positions --db etl/data/staging/politicos-es.db --source-id congreso_intervenciones --as-of-date 2026-02-12`
- Recompute: `python3 -m etl.parlamentario_es.cli backfill-combined-positions --db etl/data/staging/politicos-es.db --as-of-date 2026-02-12`

## Initial queue status
| status | count |
| --- | ---: |
| ignored | 474 |
| resolved | 50 |

### Initial pending by review reason
| review_reason | count |
| --- | ---: |

### Initial mturk note rows
- Total rows matching `'%mturk%'`: `103`

## Batch outcomes
- Applied: `0`
- Skipped: `27`
- Failed: `7`

### Applied batches
| batch_id | rows | workers_csv_rows |
| --- | ---: | ---: |

### Skipped batches
| batch_id | rows | reason |
| --- | ---: | --- |
| mturk-20260216-congreso-a1 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a10 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a11 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a12 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a13 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a14 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a15 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a16 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a17 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a18 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a19 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a2 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a20 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a21 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a22 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a23 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a24 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a25 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a26 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a27 | 3 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a3 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a4 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a5 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a6 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a7 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a8 | 20 | no pending evidence IDs; already applied |
| mturk-20260216-congreso-a9 | 20 | no pending evidence IDs; already applied |

### Failed batches
| batch_id | rows | error |
| --- | ---: | --- |
| mturk-20260216-congreso-b01 | 0 | tasks_input.csv and decisions_adjudicated.csv evidence_id mismatch |
| mturk-20260216-congreso-b02 | 0 | tasks_input.csv and decisions_adjudicated.csv evidence_id mismatch |
| mturk-20260216-congreso-b03 | 0 | tasks_input.csv and decisions_adjudicated.csv evidence_id mismatch |
| mturk-20260216-congreso-b04 | 0 | tasks_input.csv and decisions_adjudicated.csv evidence_id mismatch |
| mturk-20260216-congreso-b05 | 0 | tasks_input.csv and decisions_adjudicated.csv evidence_id mismatch |
| mturk-20260216-congreso-b06 | 0 | tasks_input.csv and decisions_adjudicated.csv evidence_id mismatch |
| mturk-20260216-congreso-hv0 | 0 | missing file(s): workers_raw.csv, decisions_adjudicated.csv |

## Post-apply queue metrics
| status | count |
| --- | ---: |
| ignored | 474 |
| resolved | 50 |

### Pending by review reason
| review_reason | count |
| --- | ---: |

### Final mturk note counts
| note | count |
| --- | ---: |
| mturk batch mturk-20260216-congreso-a10 | 4 |
| mturk batch mturk-20260216-congreso-a10: no actionable signal | 3 |
| mturk batch mturk-20260216-congreso-a11: no actionable signal | 1 |
| mturk batch mturk-20260216-congreso-a12 | 4 |
| mturk batch mturk-20260216-congreso-a12: no actionable signal | 4 |
| mturk batch mturk-20260216-congreso-a13: no actionable signal | 2 |
| mturk batch mturk-20260216-congreso-a14: no actionable signal | 3 |
| mturk batch mturk-20260216-congreso-a15 | 1 |
| mturk batch mturk-20260216-congreso-a15: no actionable signal | 2 |
| mturk batch mturk-20260216-congreso-a16 | 2 |
| mturk batch mturk-20260216-congreso-a16: no actionable signal | 4 |
| mturk batch mturk-20260216-congreso-a17 | 3 |
| mturk batch mturk-20260216-congreso-a18 | 1 |
| mturk batch mturk-20260216-congreso-a18: no actionable signal | 2 |
| mturk batch mturk-20260216-congreso-a19: no actionable signal | 4 |
| mturk batch mturk-20260216-congreso-a1: adjudicated unclear | 3 |
| mturk batch mturk-20260216-congreso-a20 | 3 |
| mturk batch mturk-20260216-congreso-a20: no actionable signal | 2 |
| mturk batch mturk-20260216-congreso-a21 | 2 |
| mturk batch mturk-20260216-congreso-a21: no actionable signal | 5 |
| mturk batch mturk-20260216-congreso-a22: no actionable signal | 4 |
| mturk batch mturk-20260216-congreso-a23 | 1 |
| mturk batch mturk-20260216-congreso-a23: no actionable signal | 3 |
| mturk batch mturk-20260216-congreso-a24 | 2 |
| mturk batch mturk-20260216-congreso-a24: no actionable signal | 3 |
| mturk batch mturk-20260216-congreso-a25 | 6 |
| mturk batch mturk-20260216-congreso-a25: no actionable signal | 1 |
| mturk batch mturk-20260216-congreso-a26 | 3 |
| mturk batch mturk-20260216-congreso-a27 | 1 |
| mturk batch mturk-20260216-congreso-a2: adjudicated unclear | 1 |
| mturk batch mturk-20260216-congreso-a3: no actionable signal | 1 |
| mturk batch mturk-20260216-congreso-a4: adjudicated unclear | 3 |
| mturk batch mturk-20260216-congreso-a4: no actionable signal | 1 |
| mturk batch mturk-20260216-congreso-a5: adjudicated unclear | 3 |
| mturk batch mturk-20260216-congreso-a5: no actionable signal | 2 |
| mturk batch mturk-20260216-congreso-a6: adjudicated unclear | 1 |
| mturk batch mturk-20260216-congreso-a6: no actionable signal | 4 |
| mturk batch mturk-20260216-congreso-a7: adjudicated unclear | 3 |
| mturk batch mturk-20260216-congreso-a8: no actionable signal | 2 |
| mturk batch mturk-20260216-congreso-a9: adjudicated unclear | 2 |
| mturk batch mturk-20260216-congreso-a9: no actionable signal | 1 |

### MTurk note count summary
- Total note rows matching `LIKE 'mturk batch %'`: `103`

## Recompute results
- `backfill-declared-positions`: `positions_total=157`, `topic_sets.inserted=157`
- `backfill-combined-positions`: `inserted=68530`, `would_insert=68530`

## Acceptance checks
- `topic_evidence_reviews` pending remains 0: PASS
- canonical note format for new writes: PASS (no new notes written in this run)
- failed batches explicitly listed: PASS

# Programas Partidos: Tests (v1)

Date: 2026-02-17  
Sprint: `AI-OPS-18`  
Source ID: `programas_partidos`

## What These Tests Protect
- Manifest-driven ingestion is reproducible from the sample CSV.
- Traceability contracts are honored:
  - `source_records.content_sha256` matches the program document bytes (not the manifest).
  - `text_documents.raw_path` bytes are materialized under the provided `raw_dir`.
- Idempotence (pragmatic):
  - `source_records` and `text_documents` do not duplicate on repeated ingests.
  - Program topic_set (`Programas de partidos` + `legislature=election_cycle`) is not duplicated.
  - `topic_evidence` is rebuilt deterministically for programs and remains stable by key fields.
- Minimum declared-signal and aggregation viability:
  - declared stance produces at least one `support` and one `oppose` on the sample.
  - declared positions can be computed (`topic_positions` inserted).

## How To Run
Local:
```bash
python3 -m unittest -v tests/test_parl_programas_partidos.py
```

Docker (canonical):
```bash
just etl-test
```

## Files
- Test: `tests/test_parl_programas_partidos.py`
- Sample manifest: `etl/data/raw/samples/programas_partidos_sample.csv`
- Sample docs: `etl/data/raw/samples/programas_partidos/*.html`


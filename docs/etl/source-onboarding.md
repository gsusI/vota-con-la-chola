# Source onboarding

One source path:

1. `just add-source <source_id> name="..." scope="..." url="..." format=json`
2. Replace generated sample with small representative fixture.
3. Implement `parse_records(payload)` in generated parser.
4. Run generated source test, then `just etl-contributor-gates`.
5. Open PR with blocker/legal notes if upstream access or reuse is limited.

Generated files:

- `publicdata_connectors_es/contrib/config.py`: source config registered into ETL.
- `etl/data/raw/samples/<source_id>_sample.<format>`: sample fixture.
- `publicdata_connectors_es/contrib/parsers/<source_id>.py`: parser.
- `tests/test_<source_id>_source_onboarding.py`: strict sample ingest test.
- `docs/etl/sources/<source_id>.md`: docs hook.

Default scaffold uses `source_records_only`. This makes new datasets traceable first.
Domain-specific normalization/backfills can come after the source lands in catalog and CI.

Contributor gates:

- sample E2E and source tests
- schema compatibility by applying current schema to a fresh DB
- source catalog contract
- privacy/leak scan
- publish dry-run contract

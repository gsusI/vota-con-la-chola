# Source onboarding

One source path:

1. Capture a small representative payload from the exact official HTTPS source and record its RFC 3339 retrieval time and SHA-256.
2. `just add-source <source_id> name="..." scope="..." url="https://fuente-oficial/..." sample_file="..." sample_sha256="..." captured_at="...Z" rights_basis="datos públicos oficiales" format=json`
3. Implement `parse_records(payload)` in generated parser.
4. Run generated source test, then `just etl-contributor-gates`.
5. Open PR with blocker/legal notes if upstream access or reuse is limited.

Generated files:

- `publicdata_connectors_es/contrib/config.py`: source config registered into ETL.
- `etl/data/raw/samples/<source_id>_sample.<format>`: exact official capture or exact real-record subset; never invented fixture data.
- `etl/data/raw/samples/<source_id>_sample.provenance.json`: exact URL, retrieval, bytes, checksum, rights basis, and real-data policy.
- `publicdata_connectors_es/contrib/parsers/<source_id>.py`: parser.
- `tests/test_<source_id>_source_onboarding.py`: strict sample ingest test.
- `docs/etl/sources/<source_id>.md`: docs hook.

Default scaffold uses `source_records_only`. This makes new datasets traceable first.
Domain-specific normalization/backfills can come after the source lands in catalog and CI.

Contributor gates:

- sample E2E and source tests
- schema compatibility by applying current schema to a fresh DB
- source catalog contract
- official-sample origin/hash audit
- secret, private-session, and workstation-leak scan; public-domain identities remain intact
- publish dry-run contract

Synthetic, mock, invented, placeholder, loopback, and `example.*` payloads are forbidden. Official public-domain personal fields remain exact in samples, normalized rows, and publishable artifacts; only secrets, private session state, workstation traces, and non-public inputs are excluded.

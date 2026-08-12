# Data integrity repair - 2026-08-12

## Where we are now

- Four canonical databases pass SQLite `quick_check`, foreign-key validation, recovery-residue checks, and stale-run checks.
- Six suspect SQLite artifacts remain preserved in dated quarantine with byte counts and SHA-256 checksums.
- Forty-two zero-byte derived text artifacts remain preserved in dated quarantine and are excluded from active output discovery.
- Fourteen abandoned zero-row ingestion markers are closed as explicit errors across the canonical and top-level staging inventory.
- Separate real-data audit found implicit sample fallback contamination in the canonical DB: `12` non-real source records had produced `10` policy events, `10` issues, and `10` accountability-ledger entries. Those rows were deleted by exact primary key, downstream artifacts were rebuilt, FK errors remained `0`, and the clean ledger now contains `126,760` real rows.
- Known fabricated source fixtures and their machine-generated evidence were removed. Historical narrative reports remain only as an audit trail and must not be used as current evidence where they cite removed fixtures.
- Official public-domain personal information is not removed by this repair. Names, official identifiers, dates of birth, official contacts, suppliers, beneficiaries, candidates, and representatives remain publishable exactly as their official source provides them. Only credentials, session state, workstation paths, and non-public data remain blocked.
- The Andalucia 2026 exporter no longer replaces official physical-person grant beneficiaries with a generic placeholder. The current public and published snapshots contain the official beneficiary name in `11` linked fields and contain `0` copies of the retired placeholder; the source-published masked identifier remains masked exactly as received.
- Infoelectoral replay and publish tests now use the retained complete official captures and official URLs. DIR3 has no accepted real capture: strict network access terminates on an official `Request Rejected` HTML response and remains a documented zero-row block rather than falling back to a fixture.
- Host verification passes `1,231` tests with `32` honest skips for unavailable optional/official captures. The ETL container initially exposed a missing PDF runtime dependency; `pypdf` is now installed in the production image and all `5/5` real Andalucia-program/official-BOE control tests pass there.
- Static publication proof passes `1,429` generated pages, `37/37` audited public routes, `41/41` critical JSON assets, `1,439` not-found payload checks, and the Cloudflare per-file size gate. No remote publication was performed.
- Fresh official BDNS `S1` now closes acquisition-to-analytics without identity suppression: `100/100` pages, `100,000` distinct source rows/URLs/version sightings, `80,509,937` raw bytes, zero retries/dead work, SQLite `quick_check=ok`, FK `0`; v5 writes one `3,464,007`-byte Parquet file and independently validates all `100,000` beneficiary names plus all `39,539` source-published identifiers exactly. Unchanged replay hardlinks `1/1` partition. Registry/readiness now validate `6/6` real corpora; only `2` exceed one million and `0` are promoted.
- Docker build-context regression from accumulated local evidence was closed: current context is `686.51 kB`, down from the observed `87.80 MB`, while rebuilt tracker gate remains `0` mismatches, `0` waivers, and `0` DONE-with-zero-real sources.

Evidence:

- `docs/etl/sprints/DATA-INTEGRITY-20260812/evidence/quarantine-manifest.json`
- `docs/etl/sprints/DATA-INTEGRITY-20260812/evidence/canonical-run-repairs.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/non-real-record-purge-20260812.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-data-only-validation.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/public-route-audit-20260812.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/dir3-age-access-blocker-20260812.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-concessions-real-s1-run-20260812.json`
- `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/bdns-public-money-real-s1-v5-validation-20260812.json`
- `etl/data/published/data-integrity-latest.json`

## Where we are going

Every canonical snapshot must fail closed before publication when SQLite is malformed, foreign keys are broken, recovery tables contain rows, ingestion runs are abandoned, active derived text files are empty, or synthetic/mock/fallback-derived content appears in active raw, derived, published, or UI artifacts.

## What is next

Run `just etl-data-integrity-audit` and `just real-data-only-check` before snapshot packaging or publication. Regenerate quarantined text only from its immutable source document; never restore a zero-byte artifact into the active tree. A blocked source stays at zero until a real official capture exists; never substitute a fixture.

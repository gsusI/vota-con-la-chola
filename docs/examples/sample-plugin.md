# Reference plugin: Congreso representatives

Estado: `implemented`

Fecha: `2026-08-19`

## Qué demuestra

`plugins/congreso_representatives` is the minimal plugin-system v1 reference. It
uses the official Congreso active-representatives source already captured and
registered by the project.

It is not a synthetic sample:

- source: Congreso de los Diputados official open-data endpoint;
- capture date: `2026-02-12T12:05:29+00:00`;
- sample bytes: `2,073`;
- sample SHA-256:
  `6cb85d7fb70dd807c9a5a85e91fa3e4a20d1b19edb4f981a5c63c0d113444ef4`;
- records: `3` exact official public records selected without identity redaction;
- source sidecar:
  `etl/data/raw/samples/congreso_diputados_sample.provenance.json`.

The plugin retains the names and all other personal fields published in those
records. No mock, generated, placeholder, anonymized or implicitly substituted row
is used.

## Files

- `plugins/congreso_representatives/plugin.json`: manifest v1.
- `plugins/congreso_representatives/plugin.py`: lifecycle hooks and legacy adapter.
- `publicdata_core/plugins.py`: SDK types, validator, loader, registry and official
  capture adapter.
- `scripts/run_reference_plugin.py`: executable end-to-end runner.
- `scripts/validate_reference_plugin.py`: double-replay validator.
- `tests/test_reference_plugin_congreso.py`: contract, provenance, hook, schema and
  idempotence tests.

## Lifecycle exercised

1. Loader validates manifest and exact capture bytes before importing entry point.
2. `register` exposes plugin/source/output identity.
3. `validate_config` rejects missing snapshot/capture.
4. `plan`/`discover` emit one bounded work item.
5. `acquire` replays exact official bytes or, only with explicit `--network`, calls
   the official endpoint.
6. `parse` yields source record envelopes with record/artifact hashes.
7. `normalize` emits source-scoped stable actor and role-assignment URNs plus exact
   raw payload/source linkage.
8. `validate` reconciles seen/loaded records and identity/provenance fields.
9. The compatibility adapter loads the same records through the current standard
   SQLite schema (`source_records`, `persons`, `mandates`, dimensions and FKs).
10. `checkpoint` records logical hash/count; `cleanup` touches only temp scope.

## Run

Canonical gate:

```bash
just reference-plugin-check
```

Explicit runner using the registered official capture:

```bash
python3 scripts/run_reference_plugin.py \
  --db /tmp/vclc-reference-plugin.db \
  --raw-dir /tmp/vclc-reference-plugin-raw \
  --snapshot-date 2026-02-12 \
  --repeat 2
```

Live official network acquisition is opt-in:

```bash
python3 scripts/run_reference_plugin.py \
  --db /tmp/vclc-reference-plugin-live.db \
  --raw-dir /tmp/vclc-reference-plugin-live-raw \
  --snapshot-date 2026-08-19 \
  --network
```

The default is deterministic official-capture replay. It is not fallback after a
network error; the execution mode is explicit in the report.

## Verified result

The double replay must report:

- plugin `org.votaconlachola.congreso-representatives` version `1.0.0`;
- `3` parsed and `3` normalized records;
- `3` source records, `3` mandates and `3` linked persons after both replays;
- `2` ingestion runs;
- `0` FK failures;
- exact official source URL in fetch lineage;
- stable logical hash and public IDs;
- `synthetic_or_mock = false`;
- official public-domain personal information retained.

## Copying the pattern

For a new plugin:

1. Capture a small exact subset from the official HTTPS source.
2. Record official URL, capture time, bytes, SHA-256 and rights basis.
3. Preserve every officially published personal field.
4. Copy the manifest structure and replace capabilities, hooks and contracts.
5. Use the official source ID when present. If an exact capture omits it, use a
   documented source-scoped stable tuple such as name + territory + start date;
   never use a name alone.
6. Implement streaming parse and bounded normalize hooks.
7. Add exact-capture replay, idempotence, provenance, schema and strict-network
   tests.
8. Run global real-only and publication-hygiene gates before publication.

Do not copy this source's political semantics into another domain. Reuse the SDK
contracts; implement source-specific parsing and normalization separately.

## Limitations and next slice

- The registry is in-repo and allowlisted; installable entry-point discovery remains
  intentionally disabled until several manifests prove the contract.
- Standard SQLite loading uses the existing representative-pipeline compatibility
  adapter. Later migrations can replace it after old/new parity passes.
- This three-record official capture proves contract behavior, not million-scale
  throughput. Capacity promotion still requires the registered representative
  corpus and scale-readiness gates.
- The next architecture step is manifest generation in `add_source`, then gradual
  migration of one connector family at a time.

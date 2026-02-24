# AI-OPS-124 — Contrato periódico del Atlas de Restricciones

## Objetivo
Cerrar la brecha operativa de la fila `105` del tracker (`Publicación periódica del Atlas de Restricciones Ciudadanas`) entregando un contrato reproducible con:
- snapshot JSON versionado,
- artefactos tabulares Parquet (`irlc_by_fragment`, `accountability_edges`),
- diff entre snapshots,
- changelog append-only estable por snapshot.

## Cambios entregados
- `scripts/export_liberty_restrictions_snapshot.py`
  - Nuevos outputs opcionales:
    - `--irlc-parquet-out`
    - `--accountability-parquet-out`
    - `--prev-snapshot`
    - `--diff-out`
    - `--changelog-jsonl`
    - `--changelog-out`
    - `--parquet-compression`
  - Nuevo contrato operativo:
    - export tabular de IRLC por fragmento,
    - export tabular de edges de accountability,
    - diff estructurado por secciones (`added/removed/unchanged`),
    - changelog JSONL con `entry_id` estable y dedupe.
- `justfile`
  - Nuevas variables del lane Atlas (`LIBERTY_RESTRICTIONS_SNAPSHOT_*`).
  - `parl-export-liberty-restrictions-snapshot` ahora ejecuta dentro del contenedor ETL (pyarrow disponible) y publica snapshot + parquet + diff + changelog en una sola corrida.
- `tests/test_export_liberty_restrictions_snapshot.py`
  - Cobertura nueva para:
    - flattening de filas Parquet,
    - contrato `diff/changelog`,
    - escritura parquet y dedupe de historial.

## Ejecución y resultados
- `python3 -m unittest tests/test_export_liberty_restrictions_snapshot.py -q`
  - PASS (`3` tests; `1` skip local por `pyarrow` fuera de contenedor).
- `just parl-test-liberty-restrictions`
  - PASS (`37` tests; `1` skip por `pyarrow` local).
- `LIBERTY_RESTRICTIONS_SNAPSHOT_PREV=docs/etl/sprints/AI-OPS-118/exports/liberty_restrictions_snapshot_latest.json just parl-export-liberty-restrictions-snapshot`
  - PASS.
  - Snapshot totals:
    - `restrictions_total=8`
    - `accountability_edges_total=15`
    - `proportionality_reviews_total=8`
    - `enforcement_observations_total=16`
    - `indirect_edges_total=12`
    - `delegated_links_total=8`
  - Parquet outputs:
    - `irlc_by_fragment_latest.parquet`: `8` filas, `21` columnas.
    - `accountability_edges_latest.parquet`: `15` filas, `8` columnas.
  - Diff con `prev_snapshot` igual al snapshot actual: `status=unchanged`, `changed_sections_total=0`.
  - Changelog append-only: `entry_id` estable y append correcto.

## Evidencia
- `docs/etl/sprints/AI-OPS-124/evidence/unittest_export_liberty_restrictions_snapshot_20260223T190900Z.txt`
- `docs/etl/sprints/AI-OPS-124/evidence/just_parl_test_liberty_restrictions_20260223T190900Z.txt`
- `docs/etl/sprints/AI-OPS-124/evidence/just_parl_export_liberty_restrictions_snapshot_20260223T190900Z.txt`
- `docs/etl/sprints/AI-OPS-124/evidence/liberty_restrictions_snapshot_diff_20260223T190900Z.json`
- `docs/etl/sprints/AI-OPS-124/evidence/liberty_restrictions_snapshot_changelog_20260223T190900Z.json`
- `docs/etl/sprints/AI-OPS-124/evidence/liberty_restrictions_snapshot_changelog_history_20260223T190900Z.jsonl`
- `docs/etl/sprints/AI-OPS-124/evidence/parquet_row_counts_20260223T190900Z.txt`
- `docs/etl/sprints/AI-OPS-124/exports/liberty_restrictions_snapshot_20260223T190900Z.json`
- `docs/etl/sprints/AI-OPS-124/exports/irlc_by_fragment_20260223T190900Z.parquet`
- `docs/etl/sprints/AI-OPS-124/exports/accountability_edges_20260223T190900Z.parquet`

## Estado DoD (fila 105)
- Contrato periódico reproducible: `OK`.
- Artefactos tabulares requeridos (`irlc_by_fragment`, `accountability_edges`): `OK`.
- Diff/changelog estable por snapshot: `OK`.

# AI-OPS-314 — Hardening de scope seleccionado (`--doc-urls-file`) sin truncado por `limit_initiatives`

## Objetivo

Cerrar una brecha operativa detectada en la lane de cohorte snapshot: cuando se usaba `--doc-urls-file`, el `limit_initiatives` podía recortar iniciativas fuera del paquete seleccionado y dejar parte de la cohorte sin evaluar.

## Cambios de código (repo-control)

- `etl/parlamentario_es/text_documents.py`
  - Cuando hay scope seleccionado (`selected_doc_urls` y/o `selected_doc_entry_keys`), se desactiva el `LIMIT` global para evitar truncado de cohorte.
  - Si hay `selected_doc_entry_keys`, se añade filtro SQL explícito por `initiative_id` para acotar el query a la cohorte seleccionada.
  - Nuevas métricas de trazabilidad:
    - `selected_initiatives_total`
    - `selected_scope_no_limit`
- `etl/parlamentario_es/cli.py`
  - Fix contractual: `_parse_doc_urls_file()` devuelve siempre 3 valores (incluido path vacío), evitando crash por unpack cuando no se pasa `--doc-urls-file`.
- Tests
  - Nuevo: `tests/test_parl_cli_doc_urls_file.py`
  - Nuevo: `test_backfill_initiative_documents_selected_scope_ignores_limit_initiatives`
  - Ajuste de expectativas en test de `selected_doc_entry_keys` para el nuevo filtro por iniciativa.

## Validación local

- `python3 -m unittest -v tests.test_parl_cli_doc_urls_file tests.test_parl_text_documents`
  - `Ran 20 tests`, `OK`.
  - Evidencia: `docs/etl/sprints/AI-OPS-314/evidence/unittest_parl_doc_urls_scope_lane_20260228T221321Z.txt`.

## Ejecución operativa (DB principal)

DB: `etl/data/staging/politicos-es.db`

1. Precheck de captura manual (strict)
- `status=degraded`, `captures_total=4`, `usable_captures_total=0`, `strict rc=4`.
- Se mantiene bloqueo de palanca cookie, por lo que se ejecuta lane archivística acotada (una corrida).

2. Retry acotado sobre packet fijo (`AI-OPS-312`)
- `selected_doc_urls_total=60`
- `selected_doc_entry_keys_total=60`
- `selected_initiatives_total=59`
- `selected_scope_no_limit=true`
- `initiatives_seen=59`
- `doc_links_seen=59`
- `urls_to_fetch=1`
- `fetched_ok=0`, `archive_fetched_ok=0`

Lectura: el hardening elimina el truncado por `limit_initiatives` (antes del fix la misma lane estaba viendo solo `13` links del paquete), pero no hubo recuperación en red en este intento único por persistencia de bloqueo/ausencia de snapshot archivístico utilizable para la URL pendiente.

3. Post-proceso y delta
- `downloaded_missing_extraction` permanece `0`.
- Delta de cobertura y cola: sin cambios materiales (`0`).

## Estado del slice

- `visible_progress`: YES (hardening contractual de lane + validación en DB real sin truncado de cohorte).
- `820/822`: se mantienen `PARTIAL` (bloqueo externo vigente), con lane de retry más robusta para futuras corridas con nueva palanca.

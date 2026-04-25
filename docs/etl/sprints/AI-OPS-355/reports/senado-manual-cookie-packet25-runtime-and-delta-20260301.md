# AI-OPS-355 — Senado `status=404` packet 25 (cookie manual) con runtime guard

## Objetivo
Escalar la lane `status=404` de `packet=8` a `packet=25` con guard de runtime y delta neta de cobertura en la misma sesión.

## Ejecución
- DB: `etl/data/staging/politicos-es.db`
- Cookie usada (válida): `etl/data/raw/manual/senado_cookie_refresh_ai_ops_299_02_leg10_tipo610_20260301T075159Z.cookies.json`
- Export packet: `docs/etl/sprints/AI-OPS-355/exports/senado_status404_linked_packet25_20260301T084757Z.csv` (`24` URLs)
- Retry command lane (`status=404`, `archive-fallback=404`, `limit=25`, `timeout=12`) completado en `6.64s`

## Resultado del retry
- `candidate_urls=24`
- `urls_to_fetch=24`
- `fetched_ok=24`
- `archive_hits=0`
- `archive_fetched_ok=0`
- `failures_total=0`

Fuente: `docs/etl/sprints/AI-OPS-355/evidence/senado_status404_manual_cookie_archive_retry_packet25_20260301T084757Z.json`

## Delta de cobertura (antes/después)
- `downloaded_doc_links`: `4804 -> 4828` (`+24`)
- `missing_doc_links_actionable`: `4559 -> 4535` (`-24`)
- `missing_urls` linked-to-votes: `783 -> 759` (`-24`)
- `blocked_403_urls`: `189 -> 189` (`0`)

Fuentes:
- `docs/etl/sprints/AI-OPS-355/evidence/quality_initiatives_before_packet25_20260301T084757Z.json`
- `docs/etl/sprints/AI-OPS-355/evidence/quality_initiatives_after_packet25_20260301T084757Z.json`
- `docs/etl/sprints/AI-OPS-355/evidence/senado_waf_block_profile_before_packet25_20260301T084757Z.json`
- `docs/etl/sprints/AI-OPS-355/evidence/senado_waf_block_profile_after_packet25_20260301T084757Z.json`

## DoD de la fila 845
- Runtime guard: `PASS` (`6.64s`, sin timeout)
- Delta mínima requerida (`+2` descargados o `-2` accionables): `PASS` (`+24` / `-24`)
- Estado: **cumplido**

## Gap residual y siguiente lane
- El packet actual no redujo `403` (`189` estable); el residual operativo más costoso sigue en cohortes WAF.
- Siguiente slice propuesto: lane prioritaria `status=403 linked_to_votes` en packet acotado y con fallback/manual capture selectivo.

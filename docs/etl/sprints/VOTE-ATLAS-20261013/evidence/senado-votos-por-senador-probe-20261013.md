# Senado XV: votos por senador no accesibles (2026-10-13)

Objetivo: añadir el voto de cada senador/a de la XV legislatura al mapa de votaciones (como ya se hace con los diputados).

Reproducir:

```bash
python3 scripts/ingestar_parlamentario_es.py ingest --db <copia>.db --source senado_votaciones --senado-legs 15 --snapshot-date 2026-10-13 --timeout 30 --strict-network
```

| probed_at_utc | url | resultado |
|---|---|---|
| 2026-10-13T08:20Z | `--strict-network` (arriba) | aborta con `HTTPError: HTTP Error 500` al bajar un fichero de votación |
| 2026-10-13T08:40Z | mismo comando sin `--strict-network` | `ingestion_runs`: `events_loaded=100`, `member_votes_loaded=0`, `note=network-partial` |
| 2026-10-13T08:43Z | `https://www.senado.es/web/ficopendataservlet?tipoFich=9&legis=15` | `200`, XML con `201` URLs `tipoFich=12` y `100` URLs de votación `legis15/votaciones/ses_*.xml` |
| 2026-10-13T08:43Z | `https://www.senado.es/legis15/votaciones/ses_10_52.xml`, `ses_17_100.xml` | `HTTP 500` |
| 2026-10-13T08:44Z | muestra aleatoria (semilla 1) de 15 URLs `legis15/votaciones/ses_*.xml` | `0` × 200, `9` × 500, `6` × 404 |

Lectura: el índice oficial de datos abiertos del Senado enlaza ficheros de votación de la XV que el propio servidor no sirve (500/404). Sin esos ficheros no hay voto por senador; solo totales por votación. Las votaciones del Senado se excluyen del mapa y del explorador por persona hasta que vuelvan a estar disponibles.

Reintento con palanca nueva (VPN del equipo desconectada, 2026-10-13T08:44Z):

| probed_at_utc | url | resultado |
|---|---|---|
| 2026-10-13T08:44:39Z | misma muestra de 15 URLs `legis15/votaciones/ses_*.xml` | `15` × 404 (ya no hay 500) |
| 2026-10-13T08:45Z | `.../rwdsesionespleno/detalle/votaciones/index.html?legis=15&id1=10&id2=52` (página de la votación) | `HTTP 500` |
| 2026-10-13T08:45Z | `https://www.senado.es/legis15/votaciones/ses_10.xml` | `200`, solo número, fecha y diario de la sesión; sin votos |
| 2026-10-13T08:45Z | `ficopendataservlet?legis=15&tipoFich=13&id1=10&id2=52` | `200`, ficha de la sesión plenaria; sin votos por senador |

Conclusión: con y sin VPN, el Senado no sirve el voto nominal por senador de la XV en sus datos abiertos. Bloqueo registrado como `nso-2026-10-senado-votos-xv-404` en `docs/etl/name-and-shame-access-blockers.md`.

Segundo reintento con la VPN realmente desconectada (IP de salida en España, 2026-10-13T08:46Z):

| probed_at_utc | url | resultado |
|---|---|---|
| 2026-10-13T08:46:38Z | muestra de 15 URLs `legis15/votaciones/ses_*.xml` (cliente del ETL) | `15` × 404 |
| 2026-10-13T08:47Z | `ses_10_52.xml`, `ses_17_100.xml` con user-agent de navegador (`curl -A`) | `404`, `404` |
| 2026-10-13T08:47Z | página de detalle de la votación con user-agent de navegador | `500` |
| 2026-10-13T08:48Z | ficha de la iniciativa `600/000001` en navegador real | carga bien, pero ya no muestra sección de votaciones (solo BOCG/DS) |

No es un bloqueo por IP ni por user-agent: los ficheros enlazados desde el índice oficial no existen (404) y la vista de votación falla (500).

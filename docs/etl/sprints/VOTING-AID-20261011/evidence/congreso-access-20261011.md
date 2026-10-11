# Congreso open-data access probe (2026-10-11)

Reproduce: `curl -s -o /dev/null -w '%{http_code}' -A '<user-agent>' '<url>'`. The ETL sends `BASE_HEADERS` from `etl/politicos_es/config.py` (browser-style User-Agent).

| probed_at_utc | url | user_agent | http_status |
|---|---|---|---|
| 2026-10-11T20:38:14Z | `https://www.congreso.es/es/opendata/votaciones` | curl default | 403 |
| 2026-10-11T20:38:15Z | `https://www.congreso.es/es/opendata/votaciones` | python-urllib/3.12 | 403 |
| 2026-10-11T20:38:20Z | `https://www.congreso.es/es/opendata/votaciones` | ETL BASE_HEADERS | 200 |
| 2026-10-11T20:38:22Z | `https://www.congreso.es/webpublica/opendata/votaciones/Leg15/Sesion156/20260127/Votacion001/VOT_20260127153134.json` | curl default | 403 |
| 2026-10-11T20:38:23Z | `https://www.congreso.es/webpublica/opendata/votaciones/Leg15/Sesion156/20260127/Votacion001/VOT_20260127153134.json` | python-urllib/3.12 | 403 |
| 2026-10-11T20:38:26Z | `https://www.congreso.es/webpublica/opendata/votaciones/Leg15/Sesion156/20260127/Votacion001/VOT_20260127153134.json` | ETL BASE_HEADERS | 200 |

ETL run with the same headers (scratch copy of `politicos-es-005.db`): `python3 scripts/ingestar_parlamentario_es.py ingest --source congreso_votaciones --congreso-legs 15 --since-date 2025-11-01 --snapshot-date 2026-10-11 --timeout 30 --strict-network` -> `ingestion_runs` status `ok`, `events_loaded=718`, `member_votes_loaded=250950`, votes through `2026-09-30`. `congreso_iniciativas` -> `initiatives_loaded=647`.

Reading: the Akamai edge denies non-browser User-Agents (`Access Denied` HTML, 403) and serves the same URLs to the ETL's headers. Earlier incidents with the same headers no longer reproduce.

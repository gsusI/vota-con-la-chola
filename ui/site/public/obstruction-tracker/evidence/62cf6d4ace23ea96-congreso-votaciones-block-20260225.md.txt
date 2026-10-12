# Congreso de España: votaciones bloqueadas (2026-02-25)

- UTC: 2026-02-25T12:34:01Z
- Command: `curl -I --max-time 20 https://www.congreso.es/es/opendata/votaciones`
- Result: `HTTP/2 403` with HTML body (content-type `text/html`, content-length `399`).
- Repro status: `--max-time 20` returns immediate `403`; ingest attempts for `congreso_votaciones` stall/hang before row production in this environment and were stopped.
- Related command attempts:
  - `python3 scripts/ingestar_parlamentario_es.py ingest --source congreso_votaciones --max-votes 200`
  - `python3 scripts/ingestar_parlamentario_es.py ingest --source congreso_votaciones --max-votes 200` with `SNAPSHOT_DATE=2026-02-25` (manual probe, no records loaded)
- Tracker note observed in `ingestion_runs` (politicos staging DB): `congreso_votaciones` latest runs show `status=running` then aborted without payload.

# Name & Shame: Public-Data Access Obstruction Log

Purpose:
- Keep an evidence-first, append-only record of official organisms/institutions that block reproducible access to public-interest data.
- Support democratic accountability with verifiable technical evidence, not speculation.

Version:
- `v1` (as of `2026-02-17`, built from current tracker + AI-OPS-08/09 evidence artifacts).

Operating rules:
- One row per incident window (`organism + source_id + endpoint + date range`).
- Every row must link to concrete evidence artifacts.
- Keep language factual and auditable.
- Never delete historical rows. If resolved, update `status` and add `resolution_evidence`.

## Incident Log

| incident_id | first_seen_utc | last_seen_utc | organism | source_id | endpoint_or_page | failure_mode | evidence | tracker_rows_impacted | status | resolution_evidence | next_escalation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| nso-2026-02-galicia-403 | 2026-02-16T21:14:53Z | 2026-02-16T21:14:53Z | Parlamento de Galicia | `parlamento_galicia_deputados` | `https://www.parlamentodegalicia.gal/Composicion/Deputados` | `HTTP 403` en `--strict-network` (`urllib.error.HTTPError`) | `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-probe-galicia-strict.log`; `docs/etl/sprints/AI-OPS-08/reports/waiver-burndown-apply-recompute.md` | `docs/etl/e2e-scrape-load-tracker.md:45` | OPEN |  | Reintento por snapshot + apertura de incidencia formal con evidencia adjunta para exigir acceso reproducible |
| nso-2026-02-navarra-403 | 2026-02-16T21:14:30Z | 2026-02-16T21:14:30Z | Parlamento de Navarra | `parlamento_navarra_parlamentarios_forales` | `https://parlamentodenavarra.es/es/composicion-organos/parlamentarios-forales` | `HTTP 403` en `--strict-network` (`urllib.error.HTTPError`) | `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-apply-recompute-probe-navarra-strict.log`; `docs/etl/sprints/AI-OPS-08/reports/waiver-burndown-apply-recompute.md` | `docs/etl/e2e-scrape-load-tracker.md:53` | OPEN |  | Reintento por snapshot + apertura de incidencia formal con evidencia adjunta para exigir acceso reproducible |
| nso-2026-02-bdns-api-antihtml | 2026-02-17T00:00:00Z | 2026-02-17T23:59:59Z | IGAE / Ministerio de Hacienda (BDNS/SNPSAP) | `bdns_api_subvenciones` | `https://www.pap.hacienda.gob.es/bdnstrans/GE/es/convocatorias` | Payload HTML anti-scraping en endpoint esperado como JSON (`Respuesta HTML inesperada para BDNS feed`) | `docs/etl/sprints/AI-OPS-09/reports/bdns-apply-recompute.md`; `docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_api_subvenciones__strict-network.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/tracker-row-reconciliation.md` | `docs/etl/e2e-scrape-load-tracker.md:65` | OPEN |  | Solicitar canal técnico/API estable machine-readable (JSON) sin anti-HTML para uso cívico reproducible |
| nso-2026-02-bdns-autonomico-antihtml | 2026-02-17T00:00:00Z | 2026-02-17T23:59:59Z | IGAE / Ministerio de Hacienda (BDNS/SNPSAP) | `bdns_autonomico` | `https://www.pap.hacienda.gob.es/bdnstrans/GE/es/convocatorias` | Payload HTML anti-scraping en endpoint esperado como JSON (`Respuesta HTML inesperada para BDNS feed`) | `docs/etl/sprints/AI-OPS-09/reports/bdns-apply-recompute.md`; `docs/etl/sprints/AI-OPS-09/evidence/bdns-apply-logs/bdns_autonomico__strict-network.stderr.log`; `docs/etl/sprints/AI-OPS-09/evidence/tracker-row-reconciliation.md` | `docs/etl/e2e-scrape-load-tracker.md:57` | OPEN |  | Solicitar canal técnico/API estable machine-readable (JSON) sin anti-HTML para uso cívico reproducible |

## Entry Template

Copy this row and fill all fields when a new incident appears:

| incident_id | first_seen_utc | last_seen_utc | organism | source_id | endpoint_or_page | failure_mode | evidence | tracker_rows_impacted | status | resolution_evidence | next_escalation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| nso-YYYY-MM-<organism>-<signal> | YYYY-MM-DDTHH:MM:SSZ | YYYY-MM-DDTHH:MM:SSZ |  | `` |  |  | `docs/etl/sprints/<SPRINT>/evidence/<file>.log` | `docs/etl/e2e-scrape-load-tracker.md:<line>` | OPEN |  |  |

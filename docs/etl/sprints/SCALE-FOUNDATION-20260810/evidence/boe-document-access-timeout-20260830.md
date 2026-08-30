# BOE document endpoint access timeout — 2026-08-30

Status: `OPEN`

This incident records a bounded transport failure against official BOE XML document URLs. It does not claim intent, a permanent outage, or failure of every BOE service.

## Durable worker evidence

- First durable failure: `2026-08-30T03:08:08Z`.
- Endpoint: `https://www.boe.es/diario_boe/xml.php?id=BOE-A-2022-13616`.
- Worker checkpoint: `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-document-fetch.json`.
- Before route degradation, same bounded batch completed `63` official XML documents.
- Batch telemetry: `85` requests, `63` successes, `22` `network` failures, `1,246,052` received bytes.
- Exact terminal signal: `URLError: <urlopen error timed out>` after `3` attempts for `BOE-A-2022-13616`.
- Queue impact at checkpoint: `100,051` succeeded, `1` dead, `815` unfinished of `100,867` document jobs.
- Current corpus status: `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/boe-document-corpus.json`.

Reproducible bounded worker command:

```bash
env BOE_DOCUMENT_START_DATE=2022-08-01 BOE_DOCUMENT_END_DATE=2026-03-31 BOE_DOCUMENT_MAX_ITEMS=0 BOE_DOCUMENT_HOST_REQUEST_BUDGET=500000 just etl-scale-boe-document-fetch
```

## One-shot direct control

After stopping the stalled next batch, one bounded direct control targeted the exact failed URL:

```bash
curl --connect-timeout 5 --max-time 10 --output /dev/null --write-out 'http=%{http_code} bytes=%{size_download} total=%{time_total}\n' 'https://www.boe.es/diario_boe/xml.php?id=BOE-A-2022-13616'
```

Observed result: connect timeout, HTTP `000`, `0` bytes, `5.003s` total.

## Scope and next action

- BOE daily-summary discovery is terminal for this cohort: `1,166` successful captures plus `191` exact official `404` responses.
- Document queue remains incomplete. Central readiness fails closed on BOE corpus checks.
- Do not repeat the same probe this sprint without a new lever or fresh upstream signal.
- Next accepted lever: documented stable bulk path, BOE confirmation of restored endpoint health, or another reproducible official channel.
- After a new lever, run one bounded control. If healthy, requeue the one telemetry-backed transient failure, reclaim expired leases through normal claiming, finish the tail, enforce corpus status, and rerun downstream inventory/provenance/text/OCR generations.

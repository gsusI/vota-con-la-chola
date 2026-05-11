# Live ETL Publish Tracker Truth Probe

Date: `2026-05-11`

Workflow:
- Run: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25685850865`
- Job: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25685850865/job/75409247234`
- Event: `workflow_dispatch`
- Input: `publish=true`

Live command:

```bash
just etl-live
```

Result:
- Live ETL completed.
- Total loaded: `78559/78655 registros validos`.
- Publish/deploy did not run because tracker truth gate failed first.
- HF/Cloudflare publish secrets were not exercised.

Tracker gate failure:

```text
mismatches: 3
done_zero_real: 0
```

Mismatches surfaced:

| source_id | tracker_before | live_sql | live evidence | decision |
|---|---:|---:|---|---|
| `asamblea_melilla_diputados` | `TODO` | `DONE` | Live ETL: `26/26`; local strict clean DB: `26/26 registros validos` | Promote tracker row to `DONE`. |
| `bde_series_api` | `TODO` | `DONE` | Live ETL: `58/58`; local strict clean DB: `58/58 registros validos` | Promote tracker row to `DONE`. |
| `eurostat_sdmx` | `TODO` | `PARTIAL` | Live ETL fallback: `2/2` after `HTTP Error 404`; local non-strict fallback reproduced `2/2` | Move tracker row to `PARTIAL`, not `DONE`. |

Local verification commands:

```bash
python3 scripts/ingestar_politicos_es.py ingest \
  --db /tmp/vclc-live-truth.db \
  --source asamblea_melilla_diputados \
  --snapshot-date 2026-05-11 \
  --strict-network \
  --timeout 30

python3 scripts/ingestar_politicos_es.py ingest \
  --db /tmp/vclc-live-truth-bde.db \
  --source bde_series_api \
  --snapshot-date 2026-05-11 \
  --strict-network \
  --timeout 30

python3 scripts/ingestar_politicos_es.py ingest \
  --db /tmp/vclc-live-truth-eurostat.db \
  --source eurostat_sdmx \
  --snapshot-date 2026-05-11 \
  --timeout 30
```

Next action:
- Patch tracker truth.
- Re-run PR/main tracker gate.
- Re-dispatch `Live ETL Publish` after merge.

## PR Gate Follow-up

PR:
- `https://github.com/gsusI/vota-con-la-chola/pull/12`

Run:
- `https://github.com/gsusI/vota-con-la-chola/actions/runs/25687905013`
- `tracker-gate` job: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25687905013/job/75416336420`

Result:
- `tracker-gate` failed in `Ingest DONE connectors (strict network)`.
- Most `DONE` sources loaded real records, including:
  - `asamblea_melilla_diputados`: `26/26`
  - `bde_series_api`: `58/58`
  - `municipal_concejales`: `66907/66907`

Strict-network failed sources:

| source_id | failure signal | tracker decision |
|---|---|---|
| `asamblea_extremadura_diputados` | `urllib.error.URLError: <urlopen error timed out>` | Move to `PARTIAL` until a current GitHub Actions strict run loads records. |
| `boe_api_legal` | `urllib.error.URLError: <urlopen error timed out>` | Move to `PARTIAL`; keep historical BOE rows as evidence, not live-clean proof. |
| `parlament_balears_diputats` | `urllib.error.URLError: <urlopen error timed out>` | Move to `PARTIAL` until a current GitHub Actions strict run loads records. |

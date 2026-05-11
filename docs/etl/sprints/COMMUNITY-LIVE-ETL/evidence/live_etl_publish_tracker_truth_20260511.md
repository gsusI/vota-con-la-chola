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

## Main Live Publish Follow-up

Run:
- `https://github.com/gsusI/vota-con-la-chola/actions/runs/25689554864`
- `live-etl` job: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25689554864/job/75422091834`

Result:
- `Run live ETL`: passed.
- `Enforce tracker truth`: passed with `mismatches=0` and `done_zero_real=0`.
- `Build public static artifacts`: failed before HF/Cloudflare publish.

Failure signal:

```text
ERROR: ledger entries below minimum
ERROR: dossier actors below minimum
ERROR: dossier issues below minimum
ERROR: evidence_api issue_clusters below minimum
```

Decision:
- Live politicos source DB can legitimately have zero accountability rows.
- Keep default accountability minimums for normal publish lanes.
- Override accountability minimums only in `Live ETL Publish` so live source catalog/static artifacts can build and publish.

## Main Live Publish Follow-up 2

Run:
- `https://github.com/gsusI/vota-con-la-chola/actions/runs/25691354880`
- `live-etl` job: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25691354880/job/75428278075`

Result:
- `Run live ETL`: passed.
- Total loaded: `78621/78717 registros validos`.
- `Enforce tracker truth`: passed with `mismatches=0` and `done_zero_real=0`.
- Accountability artifact validation passed with live-workflow zero thresholds.
- `Build public static artifacts`: failed before HF/Cloudflare publish.

Failure signal:

```text
publicar_hf_snapshot.py: error: argument --dataset-repo: expected one argument
```

Decision:
- Empty `HF_DATASET_REPO_ID`/`HF_USERNAME` workflow secrets must not erase the local dry-run default.
- Build dry-run will use `local/vota-con-la-chola-data` when publish secrets are absent.
- Real HF publish will still skip unless `HF_TOKEN` and a dataset repo target are configured.

## Main Live Publish Follow-up 3

Run:
- `https://github.com/gsusI/vota-con-la-chola/actions/runs/25693053312`
- `live-etl` job: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25693053312/job/75434199468`

Result:
- `Run live ETL`: passed.
- `Enforce tracker truth`: passed with `tracker_sources=37`, `sources_in_db=37`, `mismatches=0`, `done_zero_real=0`.
- `Build public static artifacts`: failed after source catalog, scrape queue, accountability artifact export, accountability validation, privacy scan, and HF dry-run packager start.

Failure signal:

```text
ERROR: No se encontró quality_report (votaciones-kpis) para snapshot 2026-05-11 en etl/data/published. Genera `votaciones-kpis-es-<snapshot>.json` o desactiva --require-quality-report.
```

Decision:
- The live source workflow builds a current official-source snapshot, not the parliamentary vote/liberty release package.
- Keep `HF_REQUIRE_QUALITY_REPORT=1` and `HF_REQUIRE_LIBERTY_ATLAS_RELEASE_LATEST=1` as normal publish defaults.
- Set both gates to `0` only in `Live ETL Publish`, so the scheduled source run is not blocked by unrelated parliamentary artifacts.

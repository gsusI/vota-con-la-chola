# Blocker Refresh (AI-OPS-26)

- probes_run: `4`
- blocked_sources: `4`
- retry_policy: `one strict-network retry per blocked source`

## Results
- `aemet_opendata_series`: status=`blocked`, return_code=`1`, lever_status=`no_new_lever`, failure_signal=`Error: Expecting value: line 1 column 1 (char 0)`
- `bde_series_api`: status=`blocked`, return_code=`1`, lever_status=`no_new_lever`, failure_signal=`error: [Errno 8] nodename nor servname provided, or not known`
- `parlamento_galicia_deputados`: status=`blocked`, return_code=`1`, lever_status=`no_new_lever`, failure_signal=`HTTP Error 403: Forbidden`
- `parlamento_navarra_parlamentarios_forales`: status=`blocked`, return_code=`1`, lever_status=`no_new_lever`, failure_signal=`HTTP Error 403: Forbidden`

## no_new_lever ledger
- `aemet_opendata_series`: no API/token lever introduced in this sprint context.
- `bde_series_api`: no DNS/network route lever introduced in this sprint context.
- `parlamento_galicia_deputados`: no cookie/session bypass lever approved; strict probe only.
- `parlamento_navarra_parlamentarios_forales`: no cookie/session bypass lever approved; strict probe only.

Evidence:
- `docs/etl/sprints/AI-OPS-26/evidence/blocker-probe-refresh.log`
- `docs/etl/sprints/AI-OPS-26/exports/unblock_feasibility_matrix.csv`

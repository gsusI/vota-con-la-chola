# AI-OPS-20 Shareable URL Matrix

Date: 2026-02-17  
Sprint: `AI-OPS-20`

Base path:
- GH Pages: `/citizen/`
- Local smoke server: `http://localhost:8000/citizen/` (see walkthrough)

Legend:
- `concern=<id>` is backward-compatible single concern selection (detail).
- `concerns_ids=<csv>` enables multi-concern selection (dashboard).
- `view=dashboard|detail`
- `party_id=<int>` focuses on a party (shareable).
- `method=votes|declared|combined` selects which dataset file to load (static).

## Citizen App URLs

| Scenario | URL | Expected |
|---|---|---|
| Default | `/citizen/` | Deterministic default concern (most-tagged) |
| Single concern | `/citizen/?concern=vivienda` | Active concern = vivienda |
| Topic focus | `/citizen/?concern=vivienda&topic_id=12` | Topic compare view for topic_id=12 (if belongs to concern tags; else clears topic) |
| Multi-concern selection | `/citizen/?concerns_ids=vivienda,sanidad` | Selected concerns persisted + shown as removable tags |
| Dashboard view | `/citizen/?concerns_ids=vivienda,sanidad&view=dashboard` | Party summary synthesizing both concerns |
| Party focus (dashboard) | `/citizen/?concerns_ids=vivienda,sanidad&view=dashboard&party_id=1` | Party focus enabled (chip + filtered items list) |
| Votes method | `/citizen/?concerns_ids=vivienda,sanidad&view=dashboard&method=votes` | Loads `citizen_votes.json` and shows `computed_method=votes` |
| Declared method | `/citizen/?concerns_ids=vivienda,sanidad&view=dashboard&method=declared` | Loads `citizen_declared.json` and shows `computed_method=declared` |
| Full state | `/citizen/?concerns_ids=vivienda,sanidad&concern=vivienda&topic_id=12&party_id=1&method=votes&view=dashboard` | Restores selected concerns + active concern + topic + party focus + view + method |

## Power-user Overrides (Keep)

| Scenario | URL | Notes |
|---|---|---|
| Override citizen dataset | `/citizen/?citizen=./data/citizen_votes.json` | Disables method select to avoid mismatched state |
| Override concerns config | `/citizen/?concerns=./data/concerns_v1.json` | Advanced; keep for experiments |


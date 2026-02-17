# AI-OPS-21 Shareable URL Matrix (Coverage + Coherence)

Date: 2026-02-17  
Sprint: `AI-OPS-21`

Base path:
- GH Pages: `/citizen/`
- Local smoke server: `http://localhost:8000/citizen/` (see walkthrough)

Legend:
- `concern=<id>` is backward-compatible single concern selection (detail).
- `concerns_ids=<csv>` enables multi-concern selection.
- `view=detail|dashboard|coherence`
- `party_id=<int>` focuses on a party (shareable).
- `method=votes|declared|combined` selects base dataset for detail/dashboard.

## Citizen URLs

| Scenario | URL | Expected |
|---|---|---|
| Default | `/citizen/` | Deterministic default concern |
| Single concern | `/citizen/?concern=vivienda` | Active concern = vivienda |
| Dashboard | `/citizen/?concerns_ids=vivienda,sanidad&view=dashboard` | Multi-concern party summary |
| Coherence | `/citizen/?concerns_ids=educacion,seguridad_justicia&view=coherence` | Coverage+coherence view (lazy loads votes+declared) |
| Coherence + party focus | `/citizen/?concerns_ids=educacion,seguridad_justicia&view=coherence&party_id=1` | Party focus restored; topic list shows v/d chips |
| Backward compatible topic focus | `/citizen/?concern=vivienda&topic_id=12` | Per-topic compare view |

## Power-user Overrides (Keep)
| Scenario | URL | Notes |
|---|---|---|
| Override citizen dataset | `/citizen/?citizen=./data/citizen_votes.json` | Disables method toggle; coherence still loads votes/declared from defaults |
| Override concerns config | `/citizen/?concerns=./data/concerns_v1.json` | Advanced |


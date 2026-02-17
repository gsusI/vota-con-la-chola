# Moncloa Dashboard Parity — AI-OPS-04

Date: 2026-02-16  
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`  
DB: `etl/data/staging/politicos-es.db`

## Objective
Refresh static `explorer-sources` export and verify live-vs-export parity for Moncloa KPIs.

## 1) Snapshot Refresh

Command executed:

```bash
python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/explorer-sources/data/status.json
```

Command output:

```text
OK sources status snapshot -> docs/gh-pages/explorer-sources/data/status.json
```

Sprint artifact copy created:
- `docs/etl/sprints/AI-OPS-04/exports/explorer-sources-status.json`

Canonical output refreshed:
- `docs/gh-pages/explorer-sources/data/status.json`

## 2) Live vs Export Evidence

### Live DB checks

```sql
SELECT source_id, name, is_active
FROM sources
WHERE source_id IN ('moncloa_referencias','moncloa_rss_referencias')
ORDER BY source_id;

SELECT COUNT(*) AS policy_events_moncloa
FROM policy_events
WHERE source_id LIKE 'moncloa_%';

SELECT COUNT(*) AS policy_events_total
FROM policy_events;
```

Observed live values:
- Moncloa sources present: `2`
  - `moncloa_referencias` (`is_active=1`)
  - `moncloa_rss_referencias` (`is_active=1`)
- `policy_events_moncloa = 28`
- `policy_events_total = 28`

### Export checks (`docs/gh-pages/explorer-sources/data/status.json`)

Observed export values:
- `generated_at = 2026-02-16T14:55:28+00:00`
- `analytics.action.policy_events_total = 28`
- Moncloa source entries found in export payload:
  - `moncloa_referencias` (state=`ok`)
  - `moncloa_rss_referencias` (state=`ok`)

## 3) Parity Outcome

| Check | Live | Export | parity |
|---|---:|---:|---|
| Moncloa source presence (`moncloa_referencias`, `moncloa_rss_referencias`) | 2/2 present | 2/2 present | `match` |
| `policy_events` total | 28 | 28 | `match` |
| Moncloa policy coverage consistency (`policy_events_moncloa` vs export total in this snapshot) | 28 | 28 | `match` |

Parity flags:
- `moncloa_source_presence_match = true`
- `policy_events_total_match = true`
- `all_match = true`

## 4) Escalation Rule

Rule: escalate to L2 only if parity fails and fix is in export code.

Result:
- parity did not fail (`all_match=true`)
- **No L2 escalation required**.

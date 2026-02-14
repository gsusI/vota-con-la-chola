# Senate voting data progress dashboard

**Scope:** Senado voting pipeline (`senado_votaciones`) + shared comparison to Congreso.
**Snapshot:** `2026-02-13`, DB `etl/data/staging/politicos-es.db`.

## 1) Data categories (what we try to scrape / obtain)
- `raw index`: vote-event list XMLs (`tipoFich=12`).
- `event records`: `parl_vote_events` rows + voting totals/date/theme metadata.
- `nominal votes`: `parl_vote_member_votes` rows per senator per vote.
- `identity link`: `parl_vote_member_votes.person_id` normalization.
- `raw artifacts`: local cache of raw XML needed for reproducibility and replays.

## 2) Progress by category

| Category | Target | Done | Pending | Progress | Status |
|---|---:|---:|---:|---|---|
| Raw index XML files available | - | 796 files | (target unknown) | `██████████████████████`  100.0% | ✅ baseline cache exists |
| Event records loaded (`parl_vote_events`) | 5534 | 5534 | 0 | `██████████████████████`  100.0% | ✅ complete |
| Events with totals | 5534 | 5442 | 92 | `██████████████████████`   98.3% | ✅ good |
| Events with nominal votes | 5534 | 5436 | 98 | `██████████████████████`   98.2% | 🔴 stalled (98) |
| Vote rows linked to `person_id` | 1225557 | 436202 | 789355 | `████████░░░░░░░░░░░░░░`   35.6% | 🔴 blocked by unresolved detail payloads |
| Congress control: `person_id` linkage (`congreso_votaciones`) | 557922 | 531812 | 26110 | `█████████████████████░`   95.3% | ✅ healthy reference |

## 3) Senate pending detail inventory
- Pending events without `member_votes`: **98**
- `vote_file_url` missing / not cached (404 / not found): **4**
- `vote_file_url` present but no `resultado/VotoSenador` data (flat/no-result shape): **94**
- Usable `vote_file_url` payloads with nominal rows: **0**

| Legislature | Missing events |
|---|---:|
| 10 | 61 |
| 12 | 7 |
| 14 | 26 |
| 15 | 4 |

## 4) Download artifacts collected
| Artifact | Count | Progress | Notes |
|---|---:|---|---|
| `etl/data/raw/senado_votaciones_xmls/*.xml` | 796 | n/a | raw event-list cache |
| `etl/data/raw/manual/senado_votaciones_ses/legis10/*.xml` | 71 | n/a | session/detail cache |
| `etl/data/raw/manual/senado_votaciones_ses/legis12/*.xml` | 143 | n/a | session/detail cache |
| `etl/data/raw/manual/senado_votaciones_ses/legis14/*.xml` | 69 | n/a | session/detail cache |
| `etl/data/raw/manual/senado_votaciones_ses/legis15/*.xml` | 1 | n/a | session/detail cache |
| Total manual cache files | 284 | n/a | includes reused session files and candidates |

## 5) Status legend
- ✅ done
- 🔴 blocked / unresolved
- ⚪ pending

## 6) What is next
- Keep a pinned blocker for the remaining 98 events until Senator-level payload mapping is fixed.
- Source options to unblock: alternative endpoint / official API / corrected parser for flat session format if reliably mappable.
- After recovery: re-run `backfill-senado-details` and then `backfill-member-ids`, validate with `quality-report`.

---

*This file is intended as a handoff dashboard; update it at each significant change in status or source behavior.*

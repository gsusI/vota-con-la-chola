# Sprint AI-OPS-05 Kickoff

Date: 2026-02-16  
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`  
Sprint focus: tracker reconciliation gates (before new implementation work)

## Objective (frozen)

Lock exact PASS/FAIL gates for reconciliation of tracker state vs live DB evidence, aligned to roadmap critical path and AI-OPS-04 closeout carryover.

## Inputs read

- `docs/roadmap.md`
- `docs/roadmap-tecnico.md`
- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/etl/sprints/AI-OPS-04/closeout.md`
- `docs/gh-pages/explorer-sources/data/status.json`
- `sqlite3 etl/data/staging/politicos-es.db`

Roadmap alignment used for this kickoff:
- `docs/roadmap.md` section 4.3: keep critical path on first non-parliament action source.
- `docs/roadmap-tecnico.md` section 4 (Fase 1): enforce reproducible "doble entrada" and quality gates.
- `docs/etl/sprints/AI-OPS-04/closeout.md`: AI-OPS-04 failed on tracker reconciliation gate; this is AI-OPS-05 entry point.

## Baseline Commands and Exact Outputs

### 1) Tracker status baseline

Command:
```bash
just etl-tracker-status
```

Exact gate-relevant output lines:
```text
moncloa_referencias                       | N/A       | PARTIAL | 2/2           | 0       | 20      | 20          | 0/2                  | OK
moncloa_rss_referencias                   | N/A       | PARTIAL | 3/4           | 0       | 8       | 4           | 0/3                  | OK
parlamento_galicia_deputados              | PARTIAL   | PARTIAL | 4/6           | 0       | 75      | 0           | 0/4                  | OK
parlamento_navarra_parlamentarios_forales | PARTIAL   | DONE    | 2/6           | 50      | 50      | 0           | 1/1                  | MISMATCH
tracker_sources: 28
sources_in_db: 32
mismatches: 1
done_zero_real: 0
```

### 2) FK integrity baseline

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM pragma_foreign_key_check;"
```

Output:
```text
0
```

Equivalent named metric command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```

Output:
```text
0
```

### 3) Moncloa policy events baseline

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM policy_events WHERE source_id LIKE 'moncloa_%';"
```

Output:
```text
28
```

Equivalent named metric command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_moncloa FROM policy_events WHERE source_id LIKE 'moncloa_%';"
```

Output:
```text
28
```

### 4) Tracker row scan baseline

Command:
```bash
rg -n "Accion ejecutiva \(Consejo de Ministros\)|Parlamento de Navarra|Parlamento de Galicia" docs/etl/e2e-scrape-load-tracker.md
```

Output:
```text
44:| Representantes y mandatos (Parlamento de Galicia) | Autonomico | Parlamento de Galicia: deputados (fichas HTML) | PARTIAL | Bloqueado por WAF/403 en `--strict-network`; requiere captura manual Playwright + `--from-file <dir>` |
52:| Representantes y mandatos (Parlamento de Navarra) | Autonomico | Parlamento de Navarra: parlamentarios forales (fichas HTML) | PARTIAL | Bloqueado por Cloudflare challenge/403 en `--strict-network`; requiere captura manual Playwright + `--from-file <dir>` |
61:| Accion ejecutiva (Consejo de Ministros) | Ejecutivo | La Moncloa: referencias + RSS | TODO | Scraper + normalizacion; validar acuerdos y normas contra BOE cuando exista publicacion |
```

## Baseline Metrics (frozen)

- `fk_violations = 0`
- `policy_events_moncloa = 28`
- `mismatches = 1`
- `tracker_row_moncloa_status = TODO` (line 61)
- `tracker_row_navarra_status = PARTIAL` while SQL status reports `DONE` (mismatch source)

## Must-Pass Gates (AI-OPS-05)

| Gate | PASS condition (exact) | FAIL condition | Evidence command |
|---|---|---|---|
| Gate G1 `fk_violations` | `fk_violations = 0` | `fk_violations > 0` | `sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"` |
| Gate G2 `policy_events_moncloa` | `policy_events_moncloa >= 28` (no regression from baseline) | `< 28` | `sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_moncloa FROM policy_events WHERE source_id LIKE 'moncloa_%';"` |
| Gate G3 Tracker consistency | `mismatches = 0` in `just etl-tracker-status` | `mismatches > 0` | `just etl-tracker-status` |
| Gate G4 Moncloa tracker reconciliation | Row `Accion ejecutiva (Consejo de Ministros)` is not `TODO`; includes done + blocker + one next command | row remains `TODO` or missing blocker/next command | `rg -n "Accion ejecutiva \\(Consejo de Ministros\\)" docs/etl/e2e-scrape-load-tracker.md` |
| Gate G5 Blocked CCAA rows clarity | Galicia and Navarra rows each include one blocker + one next command, and wording matches evidence pack | generic/non-reproducible text or no next command | `rg -n "Parlamento de Navarra|Parlamento de Galicia" docs/etl/e2e-scrape-load-tracker.md` |
| Gate G6 Publish parity sanity | `docs/gh-pages/explorer-sources/data/status.json` remains aligned on Moncloa (`policy_events_total` and source presence) after tracker edits | parity mismatch introduced | `python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json` + parity check |

## Dependency Order (frozen)

1. T1 Baseline freeze (this kickoff file with command evidence).
2. T2 Reconcile Moncloa tracker row (`TODO -> PARTIAL` with done+blocker+next command from AI-OPS-04 evidence).
3. T3 Reconcile Navarra/Galicia tracker row text with reproducible evidence wording and next command.
4. T4 Re-run `just etl-tracker-status`; resolve until `mismatches = 0`.
5. T5 Re-run integrity/no-regression checks (`fk_violations`, `policy_events_moncloa`).
6. T6 Refresh/export parity check for explorer-sources and attach evidence.
7. T7 Closeout decision for AI-OPS-05 (PASS only if G1-G6 all green).

## PASS/FAIL Rule (locked)

- **PASS** only if all gates `G1..G6` pass in the same sprint evidence run.
- **FAIL** if any gate fails; carryover must include owner and first command.

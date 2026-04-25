# Public Claims and Metric Consistency Audit

## Scope
- Inputs reviewed:
  - `docs/strategy/project-thesis.md`
  - `README.md`
  - `docs/gh-pages/legacy/citizen/index.html` (homepage copy)
  - `docs/gh-pages/legacy/citizen/leaderboards.html`
  - `docs/gh-pages/legacy/citizen/data/citizen.json` (and `citizen_votes.json`, `citizen_declared.json`)
  - `docs/communications/press-releases-2026-02-24.md`

- Audit date: `2026-04-04`
- Canonical rule: a claim is accepted as current only if it can be reproduced from source and the same method/context is explicit.

## Legend
- `current`: claim matches canonical source and is internally coherent.
- `conflict`: same topic is claimed inconsistently across public surfaces.
- `stale`: claim is old/undated for a surface that changes over time.
- `unverifiable`: claim has no direct verification path in the reviewed canonical sources.
- `clarify`: wording can be true but ambiguous; should be rephrased.

## Claims matrix

| Source | Public claim | Canonical source | Status | Canonical value(s) | Exact copy change needed |
|---|---|---|---|---|---|
| `project-thesis` | The project is an evidence infrastructure, not an opinion assistant. | `docs/strategy/project-thesis.md` | current | Thesis states this explicitly. | Keep. |
| `project-thesis` | Every metric should be traceable and reproducible. | `docs/strategy/project-thesis.md` | current | Thesis lists reproducible chain and auditability as core. | Keep. |
| `project-thesis` | Do not claim absolute truth or singular vote recommendation. | `docs/strategy/project-thesis.md` | current | Thesis states “No promete una verdad absoluta” and “No reemplaza revisión jurídica”. | Keep. |
| `project-thesis` | No causal impact claims unless defensible methodology exists. | `docs/strategy/project-thesis.md` | current | Explicitly disallowed. | Keep this language on public pages to avoid expectation drift. |
| `project-thesis` | Incomplete coverage is expected across all Spanish political scope. | `docs/strategy/project-thesis.md` | current | Thesis says it does not cover everything yet. | Keep as default uncertainty framing (link to source health/freshness artifacts). |
| `README` | Tool helps citizens decide their vote with evidence-first explainability. | `README.md` | current | Project summary and thesis align. | Keep this sentence but add link to `/citizen/` explicitly if absent. |
| `README` | Single SQLite + reproducible snapshots + traceability by default. | `README.md` | current | README and AGENTS/ETL docs align to architecture. | Keep; optionally add concrete example: `politicos-es.db` and `/citizen/data/citizen.json`. |
| `README` | Published public surfaces include snapshots and Hugging Face. | `README.md` | current | `just etl-publish-hf` + mirror path listed. | Keep unchanged. |
| Homepage | “No hay ranking mágico” style framing is used. | `docs/gh-pages/legacy/citizen/index.html` | current | Visible in hero/copy copy. | Keep. |
| Homepage | Method selection is visible (default + options). | Homepage runtime behavior from `docs/gh-pages/legacy/citizen/index.html` script + data fallback | current | Defaults to `combined`; supports `combined`, `votes`, `declared`. | Ensure visible copy says defaults can be changed, and shows selected method context in UI. |
| Homepage | Explicitly avoids hidden imputation of unknown values. | Runtime/honesty contract loaded via JSON | current | `no_imputation: true`, `unknown_definition` in JSON contract. | Add inline label: “No se imputan estimaciones para faltantes”. |
| Homepage | Coverage fallback rule: “si cobertura < 20% mostramos Incierto”. | Runtime/honesty logic from public JSON contract | current | JSON contract states this rule in copy and logic. | Keep rule text; add rule trigger threshold next to method chip for discoverability. |
| Homepage | Freshness indicator should match snapshot. | `docs/gh-pages/legacy/citizen/data/citizen.json` → `meta.freshness` | conflict | Canonical snapshot says `freshness_label: vigente`, `data_age_days: 15`, `should_warn: true`, `warning_reason: aging_snapshot`. | Replace generic “vigente” banner text with a two-part message: `vigente · con advertencia de antigüedad (`15 días`) por no refresco reciente`. |
| Homepage | Current methodology definitions are present. | `docs/gh-pages/legacy/citizen/data/citizen.json` → `meta.honesty` | current | `match_definition` and `unknown_definition` are present and should be rendered as user-facing glossary. | Keep and pin to `/citizen/leaderboards/?method=...`. |
| `leaderboards` | “10 hipótesis de interés público” compared with “111 topics” in data. | `docs/gh-pages/legacy/citizen/leaderboards.html` and `.../data/citizen.json` | conflict | Board text uses “10 hipótesis”, while snapshot exposes `topics: 111` with `boards` derived by concern/method. | Change copy to: `Comparativa en 10 paneles temáticos (a partir de 111 temas y 16 partidos).` |
| `leaderboards` | Uses `combined`, `votes`, `declared` datasets depending on method. | `docs/gh-pages/legacy/citizen/leaderboards.html` scripts | current | JSON files `citizen.json`, `citizen_votes.json`, `citizen_declared.json` are referenced. | Keep and show selected method in page header so users know which metric universe they are reading. |
| `leaderboards` | `111 topics`, `16 parties`, `1,776` cells from public snapshot. | `docs/gh-pages/legacy/citizen/data/citizen.json` | current | `meta` + arrays lengths from snapshot. | Render these counts as a “scope snapshot” row (currently missing in page header). |
| `leaderboards` | Citizens can compare by hypothesis/partido/tema in stable tables. | page behavior + JSON schema | current | Cells and row structure exist in data model. | Keep; include source drill-down link in empty/uncertain rows explicitly. |
| `citizen.json` | Computed method is `combined` by default. | `docs/gh-pages/legacy/citizen/data/citizen.json` `meta.computed_method` | current | `combined`. | Keep. |
| `citizen.json` | Snapshot as-of is `2026-02-28` and generated at `2026-03-15T20:50:19+00:00`. | `meta.as_of_date`, `meta.generated_at` | current | values above. | Show both timestamps in UI footer on `/citizen/` and `/citizen/leaderboards/`. |
| `citizen.json` | Available methods: `combined`, `declared`. | `meta.methods_available` | current | two methods available. | Keep and expose `votes` clearly as optional alternate method (it exists as separate file). |
| `citizen.json` | Quality: `cells_total=1776`; `clear_pct=0.006194`; `any_signal_pct=0.048986`; `unknown_pct=0.993806`. | `meta.quality` | current | values above | In any public statement, use exact method label: `method=combined` or `method=declared` for these figures. |
| `citizen.json` | 16 parties, 111 topics, 2 concerns. | array lengths | current | 16/111/2. | Add compact “scope card” on public views to avoid guessing. |
| `citizen.json` | Freshness state: `freshness_tier: aging`, `should_warn: true`, `warning_reason: aging_snapshot`. | `meta.freshness` | current | values above | Homepage already warns; mirror this exact wording in leaderboards footer. |
| `citizen.json` | Confidence tiers and thresholds are defined (high ≥0.66, medium ≥0.33). | `meta.quality.confidence_thresholds` | current | thresholds shown in contract. | Keep in technical disclosure; avoid showing only raw labels without scale. |
| `citizen_declared` | Declared method currently mirrors combined quality stats. | `docs/gh-pages/legacy/citizen/data/citizen_declared.json` | current | `any_signal_pct=0.048986`, `unknown_pct=0.993806`. | Treat as distinct method with explicit “declared” context, not default combined. |
| `citizen_votes` | Vote method has very different quality: `any_signal_pct=0.942005`, `unknown_pct=0.175676`. | `docs/gh-pages/legacy/citizen/data/citizen_votes.json` | current | values above | Any headline claiming these percentages must include `method=votes` to avoid contradiction with homepage default. |
| `citizen_votes` | Vote method as-of is `2026-02-16` (older than combined as-of). | `citizen_votes.meta.as_of_date` | current | `2026-02-16` | Add by-method as-of label if method is switched to votes. |
| `press-release` | “44/44 expected sources present”, “83,929 / 56,499 records”. | `docs/communications/press-releases-2026-02-24.md` | stale | release-only assertion (no linked raw tracker row in this audit set). | Add source pointer in same section to a status row/ETL evidence file (`docs/etl/e2e-scrape-load-tracker.md`). |
| `press-release` | “8,357 vote events; 1,778,370 member-vote records; 98.04% linked”. | `press-releases-2026-02-24.md` | unverifiable | not checkable in this audit subset. | Add explicit reference to a reproducible command or tracker metric in same paragraph. |
| `press-release` | “4,036 initiatives; 9,016 downloaded”; `98.7%`; `100% extraction coverage`; `99.99% closure`. | `press-releases-2026-02-24.md` | unverifiable | as above | Add link to the parquet/DB artifact or tracker validation that produced this number. |
| `press-release` | “401 topics, 120 high-stakes, 431,682 evidence rows, 480,175 topic positions”. | `press-releases-2026-02-24.md` | unverifiable | as above | Add evidence path or mark as historical figure as of 2026-02-24 snapshot. |
| `press-release` | “0 foreign-key violations; 864 ETL runs; 83.2% success; avg 63.5s”. | `press-releases-2026-02-24.md` | unverifiable | as above | Add command-backed verification statement (e.g., tracker export). |
| `press-release` | “94.3% some signal / 17.6% unknown”. | `press-releases-2026-02-24.md` | conflict | `votes` method has these values; default combined is `4.899% / 99.3806%`. | Replace with: `Con método votes: 94.3% con señal (17.6% unknown); con método combinado/declared (por defecto): 4.9% con señal (99.4% unknown).` |
| `press-release` | “de 88 overlap cases, explicit coherence 51.1%”. | `press-releases-2026-02-24.md` | unverifiable | as above | Add source row (`tracker`/ETL validation) or remove from evergreen-facing copy. |

## Required fixes to keep public claims consistent
1. Add a single public method label in all citizen pages (`combined`, `declared`, `votes`) and include method-specific metrics in the same sentence as any % metric.
2. Replace ambiguous `10 hipótesis` copy with “10 paneles” and expose total coverage (`111 temas`, `16 partidos`, `1,776 celdas`) in leaderboards.
3. Update freshness copy to reflect `should_warn=true` explicitly in both `/citizen/` and `/citizen/leaderboards/`.
4. For release-note claims that are not directly reproducible from visible snapshot files, append evidence pointers (`tracker`, `export`, or reproducible command) before public re-use.

# Documentar medidas: qué cambia, qué se evaluó y qué dice la evidencia en contra

You document Spanish measures with legal effect (laws, decree-laws, budget sections) voted in Congress, for a public
page held to a strict evidence standard. You do NOT judge parties and you do NOT write how parties voted: the votes are
computed elsewhere from official data. Work only on the measures listed for you.

## Inputs
- Your measures: the entries named in your task inside `docs/etl/sprints/DECISIONES-20261111/<worklist>.json`
  (title, date, vote URL, summary). Read only your entries (use `python3 -c` with json, not a full Read).
- One pre-filled skeleton per measure in `etl/data/seeds/party_decisions_v1.d/<measure_id>.json`. Edit it in place;
  keep every key; do not rename `measure_id` or `candidate_key`.
- Do NOT read other seeds, exporters, the UI, other agents' files or long docs. Everything you need is here.
- Already extracted for you (wave 2 on, `worklist-scale.json`): `boe.boe_id`, `boe.url` and `boe.preamble_excerpt`
  (first 2,500 chars of the official text, for `what_changes` and `stated_goal`). Kit commands, one call each:
  `python3 scripts/export_public_viz_decisions.py boe-text BOE-A-YYYY-NNNNN` (6,000 chars of the text) and
  `python3 scripts/export_public_viz_decisions.py boe-search <title words>` (consolidated laws whose title has every
  word; numbers and phrases do not match). For PDFs, `curl` into a new empty folder under your scratchpad and
  `pdftotext -layout`, then `grep -n` the lines you need.
- Budget sections (Presupuestos 2023): document what the section funds (programme totals from the budget law or the
  ministry's budget book), and look only for an AIReF spending review or a Tribunal de Cuentas report of those
  programmes; otherwise `no_evaluado`. Do not search for a general evaluation of the budget.
- A bill still in the Senate or not yet in the BOE: `legal_status` «aprobada por el Congreso, pendiente de ...» with
  the Congress page or the press note of the vote as `boe_url` fallback; no ex-post.

## Fields to fill (all text in Spanish, plain, short)
- `name`: short public name (≤ 70 chars), e.g. «Ley de Empleo (Ley 3/2023)».
- `boe_id`, `boe_url`: the BOE consolidated text, `https://www.boe.es/buscar/act.php?id=BOE-A-YYYY-NNNNN` (or
  `doc.php` for a decree that was not convalidated or a bill that never became law: then use the Congress BOCG/initiative
  page as `boe_url` and say so in `legal_status`).
- `legal_status`: «en vigor», «en vigor con cambios (Ley X)», «derogado», «no convalidado», «rechazado en el Congreso», etc.
- `what_changes`: ≤ 300 chars, what the text changes, concrete (who, what, from when). No adjectives.
- `stated_goal`: ≤ 200 chars, the outcome the measure itself says it pursues (its preamble or impact report).
  `stated_goal_quote`: literal quote ≤ 25 words from that text; `stated_goal_url`: where it is.
- `ex_ante`: official estimates before it applied (memoria del análisis de impacto normativo, AIReF report, Ministry
  estimate). Each item: `{"source", "url", "finding", "quote", "locator"}`; `finding` ≤ 200 chars with the number;
  `quote` literal ≤ 25 words; `locator` page/section. Empty list if none found (say so in `notes`).
- `ex_post`: evaluations after it applied (AIReF, Banco de España, INE, Fedea, IvieLab, peer-reviewed or working-paper
  quasi-experiments, Tribunal de Cuentas, the Ministry's own monitoring report). Each item:
  `{"source", "authors_year", "url", "method", "finding", "quote", "locator", "grade", "direction"}`.
  `direction` ∈ positivo | negativo | mixto | neutro (relative to the stated goal).
- `evidence_against`: sources that find no effect or the opposite of the main ex-post reading, same shape as `ex_post`.
  If the measure is evaluated and nothing contrary exists, write that in `notes` («no se encontró evidencia en contra»).
- `grade` (per ex-post / against source):
  - A: causal ex-post evaluation of THIS Spanish measure (difference in differences, regression discontinuity,
    synthetic control, AIReF evaluation with a counterfactual).
  - B: descriptive ex-post evaluation of this measure (monitoring data before/after, official report), or causal
    evidence for a very similar measure abroad.
  - C: textbook consensus or an ex-ante estimate presented as if it were an outcome.
  - D: assumption or advocacy claim without method (party, union or employer press release).
- `verdict` ∈ positivo | negativo | mixto | no_evaluado, for the stated goal only. A verdict other than `no_evaluado`
  needs at least one A or B ex-post source. Monitoring numbers alone (B) only support a verdict if the source itself
  attributes the change to the measure; otherwise `no_evaluado`. When in doubt: `no_evaluado`.
- `verdict_reason`: ≤ 250 chars, why, naming the sources.
- `indicators`: optional, only for an official figure tied to the stated goal that is not employment rate, temporary
  contracts, surgical waiting days or health spending (those are added automatically). Each:
  `{"label", "before": {"period", "value"}, "after": {"period", "value"}, "unit", "source", "url", "quote"}`.
  Example: number of minors relocated, RETA affiliates, startups certified by ENISA.
- `later_route`: only for measures that failed (counterfactual): if the content was later approved by another route,
  `{"name", "boe_url", "date"}`; else null.
- `notes`: gaps, what you could not access, dates of retrieval if not today.

## Hard rules
- Every number and every claim must be in the cited source at the cited locator. Quote literally. If you cannot open a
  source (PDF blocked, paywall), do not cite it from memory: list it in `notes` as «no verificado».
- Wording: never «gracias a», «por culpa de», «provocó», «creó N empleos»; say what moved with what.
- Counterfactuals (a bill that never took effect): there is no ex-post; fill `ex_ante` (impact report, Banco de España,
  AIReF) and, if helpful, causal evidence on a very similar measure abroad in `ex_post` with grade B and a note that
  it is about another country (both favourable and contrary studies; never grade A). The verdict stays `no_evaluado`
  (the validator enforces both rules).
- Budgets: WebSearch ≤ 6 for the whole task (the quota is shared). Prefer: boe.es, airef.es, bde.es, ine.es,
  fedea.net, congreso.es (blocked for scripts: cite its URL only if you saw it in a search result), lamoncloa.gob.es,
  ministry sites, SSRN/RePEc/journal pages. Never cat whole files; never Read PDFs or images.
- Fill each file in one edit, then run `python3 scripts/export_public_viz_decisions.py validate` and fix every error
  for your files.

## Example (shape only, invented numbers are NOT allowed in real entries)
```json
{"source": "AIReF", "authors_year": "AIReF (2023)", "url": "https://www.airef.es/...", "method": "diferencias en diferencias con
 registros de la Seguridad Social", "finding": "La medida se asocia a +X pp de ...", "quote": "«...»", "locator": "p. 34, cuadro 5",
 "grade": "A", "direction": "positivo"}
```

## Report (≤ 6 lines)
Per measure: verdict and number of sources by grade. Then: sources you could not verify. Last line: «what tool or
pre-extracted data would have saved me turns».

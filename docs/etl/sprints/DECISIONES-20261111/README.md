# DECISIONES-20261111: what each party decided in Congress on employment, the self-employed, healthcare and immigration

Slice 1b of the party-quality programme. Page: `/visualizaciones/decisiones/`. Seed:
`etl/data/seeds/party_decisions_v1.json` (+ part files in `etl/data/seeds/party_decisions_v1.d/`). Exporter, candidate
builder and validator: `scripts/export_public_viz_decisions.py`. Published:
`ui/site/public/visualizaciones/data/decisiones.json` and `decisiones.csv`.

What this page does not publish (decided by the coordinator): "party X created or destroyed N jobs". It is not
measurable. What it publishes: what each party voted on measures with legal effect, whether its vote was decisive, what
the evaluations say each measure did (graded A-D, with the evidence against), and what the official indicator did
afterwards, worded as "moved with", never "because of". "Not evaluated" is a valid output.

## Method (fixed 2026-11-11, before any measure was documented)

### 1. Domains

| Domain | Atlas axis (any confidence) | Title keywords (votes of kind `final`/`rdl`) |
|---|---|---|
| `empleo` | `empleo_derechos`; also `proteccion_social` or `fiscalidad` when title or summary matches the keywords | `empleo`, `laboral`, `trabajo`, `trabajador`, `desempleo`, `jornada`, `salari`, `despido`, `ERTE`, `subsidio` |
| `autonomos` | `autonomos_empresa` | `trabajo autónomo`, `trabajador(es/as) autónom`, `emprend`, `pyme`, `empresas emergentes`, `morosidad` |
| `sanidad` | `sanidad_publica` | `sanidad`, `sanitari`, `salud`, `medicament`, `farmac`, `hospital` |
| `inmigracion` | `inmigracion` | `extranjer`, `migra`, `asilo`, `no acompañad`, `nacionalidad`, `regularizaci`, `protección internacional` |

A measure can sit in two domains. Keywords are regular expressions in `DOMAIN_RULES` of the exporter (case-insensitive).
Axis membership uses the classification only to find the vote, never its direction or confidence: binding laws mix
several measures and are often classified with confidence `baja`; dropping them would drop most laws.

### 2. Unit

- **Measure with legal effect**: final vote of a law (`final`: dictamen or votación de conjunto), convalidation of a
  decree-law (`rdl`), or a section of the State budget (`final` votes of the Presupuestos, domain by the ministry
  section: Trabajo for `empleo`, Sanidad for `sanidad`, Inclusión/Migraciones for `inmigracion`). Several votes on the
  same law collapse into one measure; the party vote shown is the vote that gave it legal effect (votación de conjunto
  for organic laws, otherwise the last final vote; for the budget, the domain section).
- **Counterfactual**: a binding vote that failed (decree-law not convalidated, law rejected in its final vote) or a
  government bill killed by an approved enmienda a la totalidad, when the margin was 10 votes or fewer. Labelled
  «contrafactual: no llegó a tener efecto». Its evaluation is the ex-ante estimate only (there is no ex-post of a
  measure that never applied), unless the measure was later approved by another route (then that route is noted).
- **Position, no legal effect**: motions and non-binding proposals (`mocion`, `mocion_punto`, `pnl`, `pnl_punto`) in the
  domain's axis with confidence `alta`/`media`, counted per party apart from the measures (how many it backed or
  opposed), with a link to the atlas. Tomas en consideración and rejected enmiendas a la totalidad are procedural
  stages and are not counted.

### 3. Selection rule (no hand-picking)

Universe: every vote in the published vote atlas (`ui/site/public/citizen/data/vote_atlas_v1.json`: Congress XV
complete, XIV from 2022-10-04) that matches §1 and §2. **Every** matching measure is included. If a domain exceeded 15
measures, the extra rule would be: rank by people affected (or budget) in the measure's official impact report and keep
the top 15; the 2026-11-11 run did not need it (counts below). The list is produced by
`python3 scripts/export_public_viz_decisions.py candidates` and committed as `worklist.json`; nothing is added by hand.

Known gap, stated on the page and not filled by hand: our vote data starts on 2022-10-04, so the XIV measures voted
before that (among them the 2021 labour reform, RDL 32/2021, convalidated 2022-02-03, and the self-employed
contribution reform, RDL 13/2022) are outside the universe. Congress open data answers HTTP 403 to non-browser
clients (incidents `nso-2026-02-congreso-votaciones-403` and `nso-2026-03-congreso-voteevent-403-ai-ops-553` in
`docs/etl/name-and-shame-access-blockers.md`); loading the earlier XIV votes is a separate ETL refresh of the vote DB,
not done in this slice.

### 4. Per measure

- What it changes (official text, BOE link) and the outcome the measure itself states (its preamble or impact report).
- How each party voted and whether its vote was decisive: computed from our per-deputy votes
  (`vote_atlas_people_v1.json`), never typed by hand. Decisive = the result flips if that party's deputies had stayed
  out (their Sí/No removed); also reported: flips if they had voted the other way. Organic laws need 176 Sí in the
  votación de conjunto. Ties are rejections.
- The official ex-ante estimate (memoria del análisis de impacto normativo, AIReF) when one exists.
- Ex-post evaluations (AIReF, Banco de España, INE, Fedea, peer-reviewed quasi-experiments), each with a grade and the
  evidence against. Grades follow the simulator catalogue (`docs/etl/sprints/SISTEMA-COMPLEJO-20261019/README.md` §4),
  adapted to a measure: **A** causal ex-post evaluation of this Spanish measure (quasi-experiment, difference in
  differences, AIReF evaluation with a counterfactual); **B** descriptive ex-post evaluation of this measure, or causal
  evidence for a very similar measure abroad; **C** official ex-ante estimate or textbook consensus only; **D**
  assumption or advocacy claim without method.
- Verdict for the outcome the measure itself stated: `positivo`, `negativo`, `mixto` (evaluations disagree or the
  result is positive on one stated goal and negative on another) or `no_evaluado` (no ex-post of grade A or B). A verdict
  other than `no_evaluado` needs at least one A or B source.
- The official indicator before and after, from the published vertical data where it exists (`empleo.json`:
  temporary-contract share, employment rate with EU peers; `sanidad.json`: surgical waiting days, public health
  spending per person with EU peers). Where the vertical has no series (RETA affiliates, foreign population) the figure
  is cited from the official source with URL, or marked missing. Always «se movió con», never «por».

### 5. Per party and domain

Measures it backed (Sí) and opposed (No) or abstained on, split by verdict (positivo / negativo / mixto / no evaluado),
with counts and the list behind each count. Never one "jobs created" number, never a ranking of parties by quality.
Parties that never governed only have votes on measures others proposed; that is said next to their row.

### 6. Consolidated figure

One figure near the top: per domain, the indicator over time (Spain and EU peers, zero-based axis) with every measure
marked at its date; below, the 12 parties × measures matrix of votes (colour = vote, marker = verdict, ring =
decisive). A party that backed a measure whose indicator then improved cannot claim it without the verdict next to it,
and a party that opposed it cannot deny the vote. Table view and CSV/JSON download.

### 7. What the data cannot say

Causality (indicators move with the cycle, EU funds, migration and many measures at once); parties outside government
only cast votes on others' measures; healthcare is run by the autonomous communities, so the page shows what share of
public health spending the State decides and the dispersion between communities (from `sanidad.json`).

## Quality gates (fixed before collection)

1. **Pilot**: 5 measures of different domains, fully documented by one agent. Then an independent reviewer subagent,
   given only each item and its URLs, checks every figure and claim against the source. **Decision rule: at least 4 of
   5 measures with every claim verified; otherwise stop and report instead of scaling.**
2. **After scaling**: a random sample of 10 measures (seeded `random.Random(20261111)`) reviewed the same way. Publish
   only measures that pass or are corrected; failing ones go back to `no_evaluado` with the reason.
3. **Mechanical validator** (`export_public_viz_decisions.py validate`): schema, URLs present, vote ids exist in our
   data, grades in A-D, verdict consistent with grades, no causal wording in the copy.

## Where we are / where we are going / what is next

See the status section at the end (updated as gates pass).

## Status (2026-11-11)

### Where we are

- Selection rule applied mechanically (`candidates`, committed as `worklist.json`): **22 measures** (empleo 12,
  inmigración 4, sanidad 4, autónomos 2; 3 counterfactuals). Below the 8-15 target for autónomos and sanidad: not
  padded. Every party vote and decisiveness flag is recounted deputy by deputy and matches the published totals of all
  22 votes (test `tests/test_export_public_viz_decisions.py`).
- Page `/visualizaciones/decisiones/` (local, not deployed): consolidated figure (indicator per domain with every
  measure marked + parties × measures matrix: colour = vote, ring = decisive, symbol = verdict), party ledger per
  domain, one card per measure, non-binding positions counted apart, «lo que no dicen» (causality, never-governed
  parties, health spending 93.6 % autonomous communities in 2024 from the EGSP raw PDF with sha256, regional
  dispersion, data window). CSV/JSON at `visualizaciones/data/decisiones.{csv,json}`.
- **Pilot gate failed: 3 of 5** measures with every claim verified (rule: ≥ 4 of 5). Per the brief, documentation was
  **not scaled**. Review files: `review/pilot/*.json`.
  - `lo-1-2023-salud-sexual`: menstrual leave in force on 1-6-2023 (deferred disposición final), not 2-3-2023; the
    IVE statistics were graded B but do not evaluate the reform.
  - `rdl-2-2025-menores`: before/after indicator mixed two different series (574 voluntary transfers vs 877
    contingency relocations).
  - Both corrected exactly as the reviewer said and published with `review.status = corrected`; the other three
    `pass`. All 5 verdicts are `no_evaluado` (no A/B evaluation found for any).
- The other 17 measures are published with their votes and decisiveness only, marked «pendiente de documentar»; no
  evidence claims are shown for them. Their BOE ids and preamble excerpts are pre-extracted in `worklist-scale.json`
  (15 of 17; the Agencia de Salud Pública never became law and the Saharawi nationality law is not in the BOE yet).
- Cost of the pilot: drafting agent 77 turns, 9.6 M input tokens (~1.9 M per measure); reviewer ~0.16 M output
  tokens, 43 tool calls.

### Where we are going

Document the remaining 17 with the same gates, then a random 10-measure review (`random.Random(20261111)`), publish
only pass/corrected.

### What is next (fix the wheel before a second pilot)

1. Prompt rules from the two failures: official statistics that do not evaluate the measure go to `indicators`, never
   to `ex_post` with grade B; before/after needs the same series and scope; entry into force must be checked against
   the disposiciones finales (deferred dates). Validator: reject `indicators` whose before/after `source` differ unless
   flagged `same_series: true`.
2. Kit: `boe-search`, `boe-text` and `enrich` (done in `scripts/export_public_viz_decisions.py`); add a BOE helper that
   returns entry-into-force dates per disposición and later amendments in one call, and a shared text cache of fetched
   PDFs (both agents asked for it).
3. Second pilot of 5 (different measures) with those fixes; scale only if it reaches ≥ 4 of 5.
4. Data gap: load the XIV votes before 2022-10-04 (labour reform RDL 32/2021, RDL 13/2022 on the self-employed) with
   the ETL's own Congress client; then re-run `candidates`.

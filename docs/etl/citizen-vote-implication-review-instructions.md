# Citizen Vote Implication Review Instructions

Version: `v1`

## Where We Are Now

- The repo already resolves `vote_event_id -> initiative_id -> official docs`.
- The current weak point is semantic translation for citizens: official vote titles are often procedural wrappers (`Proposiciones no de Ley.`, `Enmiendas del Senado.`, `Votación separada por puntos.`).
- Result: many politically important votes remain hard to explain in plain language even when the raw evidence is present.

## Where We Are Going

- Create a reproducible review lane for **citizen-facing implications** of a parliamentary vote.
- The review unit is one queue row from `parl_vote_implication_reviews`, normally one `vote_event_id + initiative_id`.
- The goal is not ideology or scoring. The goal is a **factual translation**:
  - what was really at stake,
  - whether it was binding or only declarative/procedural,
  - what changes if it passes,
  - what stays blocked if it fails.

## What Is Next

1. Export batches from `parl_vote_implication_reviews`.
2. Review the highest-priority rows first:
   - `split_vote_point`
   - narrow margins
   - high-salience areas: vivienda, energía, transporte, coste de vida, sanidad
3. Apply adjudicated decisions back into SQLite.
4. Use resolved rows later in `/citizen` and other explainability surfaces.

## 1) What Reviewers/Agents See

Each queue row includes:

- `review_key`
- `vote_event_id`
- `initiative_id`
- `vote_date`
- `official_vote_title`
- `official_subject`
- `subgroup_title`
- `initiative_title`
- `initiative_type`
- `procedure_type`
- `totals_yes`, `totals_no`, `totals_abstain`, `totals_no_vote`, `margin`
- heuristic hints:
  - `heuristic_subject`
  - `heuristic_implication_kind`
  - `heuristic_binding_strength`
- evidence links:
  - `vote_source_url`
  - `initiative_source_url`

## 2) Strict Reviewer Task

Reviewers must produce:

- `review_status`: `resolved|ignored|pending`
- `final_implication_kind`
- `final_binding_strength`
- `citizen_title`
- `citizen_question`
- `citizen_summary`
- `impact_if_approved`
- `impact_if_rejected`
- `affected_groups`
- `evidence_quote`
- `final_confidence`
- `review_note`
- `reviewer`

## 3) Label Definitions

### `final_implication_kind`

- `binding_law`: creates or modifies binding law.
- `budget_tax`: materially changes spending, taxes, or budget powers.
- `regulation`: binding regulatory/administrative change without being the main law artifact.
- `non_binding_motion`: political direction or parliamentary urging with no direct legal force.
- `oversight`: control, reproach, reporting, or pressure on Government.
- `authorization`: authorization/ratification case (for example treaty/constitutional authorization).
- `procedural`: mainly procedural sequencing, wrapper vote, admissibility, internal chamber step.
- `unknown`: cannot be determined from the provided evidence.

### `final_binding_strength`

- `binding`
- `non_binding`
- `authorization`
- `procedural`
- `unknown`

## 4) Decision Tree

1. Is the row intelligible from the official subject/title and linked source?
2. If not, keep `review_status=pending` and explain the missing piece in `review_note`.
3. Is the vote mostly a wrapper/procedural step?
4. If yes, use `procedural` or `authorization` and explain what step it controls.
5. If it is substantive, rewrite the stake in citizen language.
6. Distinguish clearly:
   - what happens if approved
   - what remains blocked if rejected
7. If the text is too vague to support a safe citizen translation, use `ignored` or `pending`; do not guess.

## 5) Hard Rules

- Do not infer from party ideology alone.
- Do not use external political commentary as evidence.
- Prefer official chamber text and initiative wording.
- If the vote is split by points, describe the **specific point** being voted if the row makes that possible.
- `citizen_title` should be short and scannable.
- `citizen_question` should be answerable as “sí/no/depende”.
- `citizen_summary`, `impact_if_approved`, and `impact_if_rejected` should be plain Spanish, not parliamentary jargon.
- `evidence_quote` must be a short exact fragment from the provided official wording; if not available, leave it empty and explain in `review_note`.

## 6) Good Output Shape

Example:

- `review_status=resolved`
- `final_implication_kind=non_binding_motion`
- `final_binding_strength=non_binding`
- `citizen_title=Más compras públicas para vivienda asequible`
- `citizen_question=¿Debe el Estado usar medidas fiscales, regulatorias y de compra pública para ampliar el acceso a vivienda?`
- `citizen_summary=La votación no crea una ley por sí sola, pero fija una posición parlamentaria clara a favor o en contra de intervenir más en vivienda.`
- `impact_if_approved=El Congreso respalda pedir al Gobierno más intervención pública y fiscal en vivienda.`
- `impact_if_rejected=El Congreso rechaza esa dirección política y deja sin apoyo parlamentario esa presión específica.`
- `affected_groups=Hogares con problemas de acceso a vivienda, arrendatarios, compradores, administraciones públicas`
- `evidence_quote=medidas fiscales, regulatorias y de adquisición pública para asegurar el derecho a la vivienda`

## 7) Bad Output Shape

- Copiar el título oficial sin traducirlo.
- Escribir “izquierda” o “derecha” como resumen.
- Confundir una PNL o moción con una ley vinculante.
- Inventar efectos concretos que no estén respaldados por el texto oficial.

## 8) Export / Apply Commands

Export queue:

```bash
python3 scripts/export_vote_implication_review_queue.py \
  --db etl/data/staging/politicos-es.db \
  --source-id congreso_votaciones \
  --only-pending \
  --limit 100 \
  --out etl/data/raw/manual/vote_implication_reviews/batch-001/tasks_input.csv
```

Apply decisions:

```bash
python3 scripts/apply_vote_implication_reviews.py \
  --db etl/data/staging/politicos-es.db \
  --in etl/data/raw/manual/vote_implication_reviews/batch-001/decisions_adjudicated.csv \
  --source-id congreso_votaciones
```

## 9) Audit Contract

- Never overwrite worker raw exports.
- Keep a stable `review_key` per row.
- Every applied decision must preserve a `review_history` entry in `raw_payload_json`.
- If a row cannot be translated safely, leave it unresolved instead of fabricating certainty.

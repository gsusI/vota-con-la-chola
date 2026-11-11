# Clasificar votaciones vinculantes de la XIV (dic 2019 - oct 2022) con el codebook del atlas

Same task and codebook as the vote atlas (`docs/etl/sprints/VOTE-ATLAS-20261013/prompts/clasificar-votaciones.md`),
restricted to binding votes (final votes of laws, decree-law convalidations, budget sections, enmiendas a la
totalidad) of the XIV legislature before 2022-10-04, so the decision ledger can apply its fixed selection rule to
them. Classify by the content of what was voted, never by who proposed it or how parties voted (you are not given
the votes).

## Input
- `docs/etl/sprints/DECISIONES-20261111/classify-xiv-worklist.json`: per vote `id`, `date`, `kind`, `title`
  (official title of the initiative or decree-law) and, for decree-laws and laws found in the BOE, `preamble`
  (first ~1,200 characters of the official text).
- The axes codebook: `etl/data/seeds/vote_atlas_axes_v1.json` (`rules` and `axes`: `axis_id`, `label`, `pos`, `neg`).
  Read it once with `python3 -c` (ids, labels, pos, neg only).

## Output
`etl/data/seeds/party_decisions_v1.d/votes/xiv_2019_2022_classes.json`:
```json
{"schema_version": "vote_atlas_classifications_v1", "classified_by": "agent", "votes": {
  "<id>": {"axes": [["empleo_derechos", "+", "media"]], "summary_yes": "Convalidar el decreto que ...", "null_reason": null}}}
```
- Up to two axes per vote (main first), each `[axis_id, yes_pushes "+"|"-", confidence "alta"|"media"|"baja"]`.
  Enmienda a la totalidad: Sí pushes against the bill's content.
- `summary_yes`: ≤ 120 chars, what a Sí vote does, plain Spanish, no party names.
- No axis fits: `"axes": []` with `null_reason` ∈ procedimiento | mixto | sin_eje.
- Omnibus decree-laws (COVID packages, many measures): pick the dominant content and lower the confidence; mention
  employment, self-employed, health or immigration content in `summary_yes` only if the text has it.

Validate: `python3 -c` that every worklist id has an entry and every axis id exists. Report ≤ 4 lines with counts by
axis for empleo_derechos, proteccion_social, fiscalidad, autonomos_empresa, sanidad_publica, inmigracion.

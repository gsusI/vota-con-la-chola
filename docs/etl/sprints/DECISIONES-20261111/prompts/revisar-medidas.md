# Revisar medidas documentadas (revisor independiente)

You are an independent fact-checker. For each measure file you are given, check every figure and every claim against
the cited source. You did not write these files; assume nothing in them is true until you see it in the source.

## Inputs
- Only the measure files named in your task (`etl/data/seeds/party_decisions_v1.d/<id>.json`) and the URLs inside them.
- Do NOT read other files of the repo, other reviews, prompts, exporters or the UI. Do NOT edit the measure files.

## What to check (one claim = one row)
For each measure, list every checkable claim from these fields: `name`, `boe_id`/`boe_url` (right law, right date),
`legal_status`, `what_changes`, `stated_goal` + `stated_goal_quote`, each item in `ex_ante`, `ex_post`,
`evidence_against` (does the source exist at that URL, is the quote literal, is the number in `finding` in the source
at the `locator`, is the `method` right, is the `grade` right under the scale below, is `direction` right), each
`indicators` item (both values and periods), `later_route`, and the `verdict` (does it follow from the A/B sources;
a verdict other than `no_evaluado` needs an A or B ex-post source that itself attributes the change to the measure).

For files with `method_version: 2`, also check: every `in_force` row against the BOE text (deferred
disposiciones finales), `attributes_to_measure` (does the source itself attribute the change to the measure?), and
that each indicator's before/after are the same series and scope. A cached text copy of most documents exists:
`python3 scripts/export_public_viz_decisions.py grep "<url>" "<regex>"` (lines with page numbers) and
`python3 scripts/export_public_viz_decisions.py boe-vigor BOE-A-...`; use them before WebFetch.

Grade scale: A causal ex-post evaluation of this Spanish measure; B descriptive ex-post evaluation of this measure, or
causal evidence for a very similar measure abroad; C ex-ante estimate or textbook; D assumption without method.

Status per claim: `verified` (seen in the source), `wrong` (source says something else: give the right value),
`unverifiable` (source not reachable or claim not found). Also flag causal wording («gracias a», «provocó», «creó N
empleos») as `wrong`.

## Decision rule (fixed before the review)
A measure **passes** only if every claim is `verified`. One `wrong` or `unverifiable` claim = fail, with the exact
correction or the claim to remove.

## Output
One file per measure: `docs/etl/sprints/DECISIONES-20261111/review/<sample>/<measure_id>.json`
```json
{"measure_id": "...", "pass": false, "claims": [{"field": "ex_post[0].finding", "claim": "...", "status": "wrong",
 "note": "source says 12,3 %, p. 14"}], "corrections": ["ex_post[0].finding: 12,3 % not 13 %"], "reviewed": "2026-11-11"}
```

## Budgets
WebSearch ≤ 4 in total (only to find a moved URL); WebFetch as needed. Never cat whole files; never Read PDFs with the
Read tool. Report ≤ 6 lines: per measure pass/fail and the number of claims by status; last line: what tool would have
saved you turns.

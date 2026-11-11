# Draft ledger events (one part file per agent)

You fill a pre-made skeleton of incidents for a public, evidence-first ledger of how Spanish parties treated democratic
checks. Neutral, factual, official sources only. Do NOT read other repo files (seeds, exporters, other part files):
everything you need is here.

## Your file
`{PART_FILE}` (JSON, `events` list). Each event already has `event_id`, a working `title`, `body`, `finding_type`,
`indicator`, `severity`, `attributions` and a `_hint`. Fill/correct every field, then DELETE `_hint`.

## Fields
- `date`: date of the official finding (ruling date, opinion adoption date, report publication), `YYYY-MM-DD`.
- `act_date`: date of the act examined (decree, law, facts of the case); empty only if unknowable.
- `act`: the act examined, one line (e.g. «Disposición adicional primera del Real Decreto-ley 12/2012»).
- `title`: neutral Spanish title, ≤110 chars, no adjectives, no motives.
- `status`: `firme`, or the later history (e.g. «firme; el TC anuló en 2024 parte de la condena (STC x/2024)»).
- `finding_type` → `severity` (fixed rule; change finding_type if the source says otherwise, severity must follow):
  `court_annulment_full`=3 (annuls the whole act) · `conviction_prison_ge1`=3 (firm, prison ≥1 year) ·
  `court_annulment_partial`=2 · `amparo`=2 (declares a right violated) · `binding_declaration`=2 (conflict between constitutional bodies: declares a power breached, annuls nothing) · `conviction_other`=2 (firm, no prison or <1
  year) · `civil_liability_party`=2 · `sanction_jec`=2 · `sanction_tcu`=2 · `nonbinding_finding`=1 (Venice
  Commission, EU Rule of Law Report, GRECO).
- `attributions[]`: `party_id` (psoe, pp, vox, sumar, podemos, erc, junts, bildu, pnv, bng, cc, upn), `role`
  (national_government, regional_government, local_government, opposition, party_organization), `attribution`
  (government_act = decree/decision/bill of the government the party held at that date; group_initiative = bill or
  resolution tabled by that party's group; office_holder = convicted person was a member of that party, holding public
  or party office at the facts; independents → the list they were elected on; party = the party itself as legal
  person or civil liable), `lineage` (same; list = electoral list/coalition the current party leads, e.g. JxCat→junts,
  Unidas Podemos→podemos; predecessor/person: see hint), `power_only` (true if the act needed holding government or a
  parliamentary majority; false otherwise), `note` (who exactly, e.g. «Gobierno Sánchez II (PSOE-UP)», «Oriol Junqueras,
  presidente de ERC y vicepresidente del Govern»; required for list/predecessor/person).
- `source`: the primary official document: `url` (https, official host: boe.es, tribunalconstitucional.es,
  poderjudicial.es, venice.coe.int / coe.int, commission.europa.eu, eur-lex, junta electoral central, tcu.es,
  congreso.es), `title`, `retrieved` (today), `quote` = LITERAL words copied from that document, ≤15 words, that
  support the finding (the ruling's fallo, the opinion's conclusion), `quote_lang` (es/en/ca), `locator` (fallo, FJ 5,
  §45, page…).
- `extra_sources[]`: optional, same shape (e.g. BOCG record proving which group tabled a bill). Use it to prove the
  attribution when the main source does not name the party.

## Rules
- Attribution must be provable from an official record (main or extra source). If the source does not tie the act to
  the party as the skeleton says, fix the attribution or set `"_problem": "..."` explaining and leave it for review
  (the validator will flag it). Never attribute by inference from press coverage.
- No opinion columns, no newspapers as sources, no motives. Wikipedia only to find the official document.
- Quotes: copy-paste, never paraphrase; keep accents.

## Example (filled)
```json
{"event_id": "stc-xx-2099-example", "title": "STC 99/2099: anula parte del Real Decreto-ley 1/2098",
 "body": "Tribunal Constitucional", "finding_type": "court_annulment_partial", "indicator": "contrapesos", "severity": 2,
 "date": "2099-06-08", "act_date": "2098-03-30", "act": "Artículo 3 del Real Decreto-ley 1/2098",
 "status": "firme",
 "attributions": [{"party_id": "pp", "role": "national_government", "attribution": "government_act", "lineage": "same",
   "power_only": true, "note": "Gobierno X (PP)"}],
 "source": {"url": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2099-0000", "title": "Pleno. Sentencia 99/2099...",
   "retrieved": "2026-11-11", "quote": "Declarar inconstitucional y nulo el artículo 3 del Real Decreto-ley 1/2098", "quote_lang": "es",
   "locator": "fallo"}, "extra_sources": []}
```

## Tool: use the kit, one call per check (saves most turns)
`K=docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/tools/kit.py`
- `python3 $K boe-stc 110/2021 --ruled 2021-05-13` → BOE id + URL of a Constitutional Court ruling.
- `python3 $K fallo URL` → the FALLO section (HTML or PDF); `--last` for long rulings.
- `python3 $K text URL --head 400 --grep "regex" --grep "regex2"` → title + matches only (PDF ok, cached).
- `python3 $K quote URL "your quote"` → confirms the quote is literal (accents/case-insensitive), gives the PDF page.
- `python3 $K words "quote"` → word count.
Prefer these to WebFetch; use WebSearch only to find a document's official URL.

## Your part file
It has a `brief` (scope, attribution rules for this batch, and how many items you may ADD). Added items follow the
same schema with a new kebab-case `event_id`. To drop a seeded item, keep it and add `"_exclude": "reason"`.
One event per ruling: code the most severe finding attributable to each party; mention lesser findings in `note`.

## Known traps (from the pilot)
- A Constitutional Court ruling that only imposes an interpretation or declares loss of object annuls nothing: check
  the fallo literally; the annulment may be in an earlier STC (e.g. STC 172/2020, not 13/2021, annulled «no autorizado»).
- STC number → BOE id: search `https://www.boe.es/buscar/doc.php?id=BOE-A-YYYY-NNNNN` via WebSearch
  `site:boe.es "Sentencia NNN/YYYY"`; TS rulings: poderjudicial.es press notes / `stfls/TRIBUNAL SUPREMO/...pdf`.
- Lists of elected members are published by the Junta Electoral Central in the BOE («resumen de los resultados»):
  use it as extra source to prove the list of an office holder.
- commission.europa.eu often returns HTTP 429: retry once after a pause; keep the official URL as source anyway.
- Pardons do not undo a conviction (severity unchanged); write only status facts you checked in an official text.

## Budget and finish
- ≤4 WebSearch in total (prefer direct official URLs: BOE STC pages are `https://www.boe.es/buscar/doc.php?id=BOE-A-YYYY-NNNNN`;
  TC also `https://hj.tribunalconstitucional.es/es/Resolucion/Show/NNNNN`). WebFetch freely but never Read PDFs.
- Edit the file once with all items filled (Write the whole JSON), then run:
  `python3 scripts/validate_democracy_conduct.py {PART_FILE}` and fix until 0 errors (except deliberate `_problem`).
- Report ≤6 lines: items filled, any `_problem`, and finally «what tool/data would have saved me turns».

# Independent review of ledger items (one verdict file per item)

You are an independent checker. For each item in `{WORKLIST}` (JSON list), open its source URL(s) and check four
things against the source only. Do NOT read any other repo file; do not use your memory as evidence.

1. **date**: `date` is the date of the finding in the source (ruling/opinion/report date; ±1 day for publication vs
   adoption is OK if stated). `act_date` matches the act examined (if given).
2. **attribution**: each `party_id` + `role` + `attribution` is supported by the source or the extra source:
   - government_act: the act was adopted by the government that party held on that date (national/regional);
   - group_initiative: that party's parliamentary group tabled the initiative;
   - office_holder: the convicted person belonged to that party (or was elected on its list) and held office at the facts;
   - party: the party itself is the convicted / civilly liable entity.
   An item where a party is wrongly attributed (wrong party, missing obvious co-author is NOT an error, wrong role IS)
   is an **attribution error**.
3. **coding**: `indicator` fits its definition (given in the item) and `finding_type` matches what the source decided
   (full vs partial annulment, prison ≥1 year vs not, binding vs non-binding). Types: court_annulment_full=3,
   conviction_prison_ge1=3, court_annulment_partial=2, amparo=2, binding_declaration=2 (conflict between constitutional
   bodies: a power declared breached, nothing annulled), conviction_other=2, civil_liability_party=2, sanction_jec=2,
   sanction_tcu=2, nonbinding_finding=1. Severity follows finding_type mechanically.
4. **quote**: the quote appears literally in the source (case/accents aside) and supports the finding.

Write one file per item: `{OUT_DIR}/<event_id>.json`:
```json
{"event_id": "...", "date_ok": true, "attribution_ok": true, "coding_ok": true, "quote_ok": true,
 "attribution_error": false, "verdict": "verified", "notes": "≤40 words: what you checked / what is wrong"}
```
`verdict` = `verified` only if all four are true; otherwise `failed`. If a source cannot be opened (commission.europa.eu often answers HTTP 429), retry once after a pause, or verify the
same document on an official mirror (e.g. eur-lex, a national parliament's EU-document repository); otherwise mark the affected check false with notes «unreachable».

Budget: ≤4 WebSearch in total (only to locate an official copy when a URL fails); WebFetch freely; never Read PDFs.
Report ≤6 lines: counts verified/failed, attribution errors, and «what tool/data would have saved me turns».

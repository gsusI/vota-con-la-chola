# Notes for the full-coverage review (append to prompts/events-review.md)

- Items of "kind": "pending" are findings excluded from counts because they are not firm: check date, that the person
  belonged to the party (or the party itself), that an official record shows it is NOT firm (appealed/appealable), quote.
- `lineage`: "same"; "list" = electoral list or federated party the current party runs with (Unidas Podemos → Podemos;
  JxCat → Junts; PSC → PSOE); "predecessor" = legally distinct earlier party (CDC, PDeCAT, CiU: shown, not counted);
  "person" = predecessor-party member who leads the current party today (source required).
- Government composition is public record: Zapatero = PSOE; Rajoy = PP; Sánchez I = PSOE; Sánchez II = PSOE + Unidas
  Podemos (13-1-2020..21-11-2023); Sánchez III = PSOE + Sumar; Aragonès Govern = ERC (alone from Oct 2022); García-Page =
  PSOE; Ayuso, Mañueco, López Miras = PP. For government_act items check that the act was that government's on that date.
- Census rules: a Constitutional Court ruling counts as `court_annulment_full` only if it annuls the whole norm; one
  provision of a decree-law is partial. Electoral-board sanctions are coded `reglas` (use of public office in a
  campaign). GRECO compliance reports are attributed to the government of the day by the codebook (GRECO addresses «the
  authorities»); coded `contrapesos`. Pardons and amnesty do not undo a firm finding.
- Host traps: commission.europa.eu answers 429 (use the Austrian Parliament copies on parlament.gv.at); tribunalconstitucional.es
  PDFs answer 403 (use the BOE text); tcu.es and some regional hosts fail TLS (curl -k for that host only); JEC pages take
  30-60 s; rm.coe.int PDFs work directly.
- Batch efficiency: fetch each URL once with the kit (`text URL --grep A --grep B`), check all claims of the item in that
  call, then `quote`. Report ≤6 lines.

# AI-OPS-24 Kickoff

Objective:
- Download and index the primary source texts of what is being voted (initiative documents) so votes can be audited end-to-end.

Scope:
- Congreso + Senado initiative documents referenced by votes (BOCG / Diario de Sesiones / initiative detail pages).

Notes:
- This sprint is evidence-first: every doc must map to `initiative_id` and be stored as `text_documents` metadata with raw bytes on disk.
- If upstream blocks reproducible access (e.g. HTTP 403/WAF), we do not fake DONE: we log blockers with evidence and provide a manual capture kit.

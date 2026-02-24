# AI-OPS-172 — Diagnostico reproducible de gap residual de voto

## Objetivo
Materializar un diagnostico determinista del gap residual de cobertura de voto en `Responsabilidad por fragmento normativo` para decidir si procede nuevo matcher o si falta linkage upstream.

## Entregado
- Script nuevo: `scripts/report_sanction_norms_vote_gap_diagnosis.py`.
- Test nuevo: `tests/test_report_sanction_norms_vote_gap_diagnosis.py`.
- Lane `just`: `parl-report-sanction-norms-vote-gap-diagnosis`.
- Export operativo CSV de responsabilidades sin voto para backlog accionable.

## Resultado de corrida (20260224T094824Z)
- `responsibilities_missing_vote_total=2`.
- Ambas responsabilidades pertenecen a `BOE-A-2000-15060` (`approve`, `enforce`).
- Sin candidatos por titulo ni por docs de votacion (`missing_with_vote_title_candidates_total=0`, `missing_with_vote_doc_candidates_total=0`).
- Diagnostico final en ambos casos: `no_vote_event_link_for_parliamentary_initiatives`.

## Conclusion operativa
No hay nuevo lever de matching conservador en el corpus actual. El bloqueo es de linkage/upstream para iniciativa senatorial historica (`senado:leg5:exp:621/000026`).

## Evidencia
- `docs/etl/sprints/AI-OPS-172/evidence/sanction_norms_vote_gap_diagnosis_20260224T094824Z.json`
- `docs/etl/sprints/AI-OPS-172/evidence/responsibility_vote_gap_20260224T094824Z.csv`
- `docs/etl/sprints/AI-OPS-172/evidence/sanction_norms_seed_status_20260224T094824Z.json`
- `docs/etl/sprints/AI-OPS-172/evidence/just_parl_report_sanction_norms_vote_gap_diagnosis_20260224T094824Z.txt`
- `docs/etl/sprints/AI-OPS-172/evidence/just_parl_test_sanction_norms_seed_20260224T094824Z.txt`
- `docs/etl/sprints/AI-OPS-172/evidence/just_parl_test_liberty_restrictions_20260224T094824Z.txt`

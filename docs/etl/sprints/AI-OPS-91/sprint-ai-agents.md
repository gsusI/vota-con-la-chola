# AI-OPS-91 Prompt Pack

Objective:
- Ship Tailwind+MD3 component parity v2 for `/citizen`: normalize `card/chip/button/tab` primitives across summary, compare, and onboarding flows with strict marker-count contract checks.

Acceptance gates:
- Extend generated MD3 primitives with tabs and button variants in `scripts/build_citizen_tailwind_md3_css.py`.
- Normalize `/citizen` markup/template classes so controls and dynamic cards consistently use MD3 primitives (`md3-card`, `md3-chip`, `md3-button`, `md3-tab`).
- Harden `scripts/report_citizen_tailwind_md3_contract.py` with strict minimum marker counts (cards/chips/buttons/tabs).
- Keep `just citizen-test-tailwind-md3` green and maintain release-regression + GH Pages build parity.
- Publish sprint evidence under `docs/etl/sprints/AI-OPS-91/evidence/`.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`status=ok`, `md3_card=10`, `md3_chip=16`, `md3_button=28`, `md3_tab=9`).

# AI-OPS-77 Prompt Pack

Objective:
- Ship share-flow clarity v2 for `/citizen` by hardening `#preset` decode/recovery and making canonicalization/remediation explicit in UI.

Acceptance gates:
- Extend preset codec to recover malformed but salvageable hashes (legacy no-version payload, unencoded payload, double-encoded payload, case-insensitive `#preset=`).
- Emit canonical hash + recovery metadata from codec (`canonical_hash`, `recovered_from`) without changing snapshot/backend contracts.
- Update citizen UI banner/actions to surface recovery status, canonical link copy, and clear-hash remediation.
- Expand fixture matrix and strict tests for recovery/canonicalization behavior.
- Keep existing citizen regression checks green (preset suite, mobile-performance, first-answer).
- Publish sprint evidence and closeout under `docs/etl/sprints/AI-OPS-77/`.

Status update (2026-02-23):
- Implemented and validated with reproducible sprint evidence.

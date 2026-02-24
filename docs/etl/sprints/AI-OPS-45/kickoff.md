# AI-OPS-45 Kickoff

Date:
- 2026-02-22

Objective:
- Add a strict publish-sync contract that reports whether `docs/gh-pages/citizen/preset_codec.js` is stale versus `ui/citizen/preset_codec.js`, with machine-readable before/after hash evidence in local and CI loops.

Why now:
- AI-OPS-44 enforces direct parity and first-diff checks.
- We still need explicit sync-state semantics (`would_change`, before/after hash) for triage and release readiness.

Primary lane (controllable):
- Ship `scripts/report_citizen_preset_codec_sync_state.js` + tests + `just` target + CI artifact upload.

Acceptance gates:
- Reporter emits JSON with `would_change`, `published_before_sha256`, `published_after_sha256`, byte deltas, and first-diff metadata.
- `--strict` exits non-zero when published asset is stale.
- `just citizen-test-preset-codec` includes sync-state tests.
- CI job uploads `citizen-preset-codec-sync` artifact.
- `just citizen-report-preset-contract`, `just citizen-report-preset-codec-parity`, `just citizen-report-preset-codec-sync`, `just explorer-gh-pages-build`, and `just etl-tracker-gate` pass.

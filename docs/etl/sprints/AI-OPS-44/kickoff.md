# AI-OPS-44 Kickoff

Date:
- 2026-02-22

Objective:
- Add a strict parity contract between source citizen preset codec and published GH Pages codec, with machine-readable artifact output locally and in CI.

Why now:
- AI-OPS-43 already validates fixture behavior in CI.
- We still need a hard gate that catches source/published asset drift (`ui/citizen` vs `docs/gh-pages/citizen`) before release.

Primary lane (controllable):
- Ship `scripts/report_citizen_preset_codec_parity.js` + tests + `just` target + CI artifact wiring.

Acceptance gates:
- Reporter emits JSON (`sha256`, bytes, first-diff metadata, `failed_ids`) and supports `--strict`.
- `just citizen-test-preset-codec` includes parity reporter tests.
- CI job uploads parity artifact (`citizen-preset-codec-parity`).
- `just citizen-report-preset-contract`, `just citizen-report-preset-codec-parity`, `just explorer-gh-pages-build`, and `just etl-tracker-gate` pass.

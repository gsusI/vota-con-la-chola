# AI-OPS-43 Kickoff

Date:
- 2026-02-22

Objective:
- Add a CI-native citizen preset contract job that always publishes a machine-readable drift artifact.

Why now:
- AI-OPS-42 introduced the local strict reporter and tests.
- We still need remote CI evidence attached to runs so collaborators can inspect drift without reproducing locally.

Primary lane (controllable):
- Extend `.github/workflows/etl-tracker-gate.yml` with `citizen-preset-contract` job.

Acceptance gates:
- Workflow has a `citizen-preset-contract` job.
- Job runs Node preset tests + strict reporter.
- Job uploads JSON artifact (`citizen-preset-contract`).
- `just citizen-test-preset-codec`, `just citizen-report-preset-contract`, `just explorer-gh-pages-build`, and `just etl-tracker-gate` pass.

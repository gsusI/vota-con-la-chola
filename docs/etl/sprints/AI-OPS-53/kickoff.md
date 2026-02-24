# AI-OPS-53 Kickoff

Date:
- 2026-02-22

Objective:
- Add an append-only NDJSON heartbeat stream from the preset SLO digest so long-horizon monitoring can ingest one compact row per run without reparsing full SLO artifacts.

Why now:
- AI-OPS-52 introduced a compact digest (`status`, `risk_level`, key metrics).
- We still lacked a persistent, low-cost trend feed optimized for polling/stream ingestion.

Primary lane (controllable):
- Ship `scripts/report_citizen_preset_contract_bundle_history_slo_digest_heartbeat.js` + tests + just/CI wiring + sprint evidence/docs.

Acceptance gates:
- New reporter appends deduplicated heartbeat rows to JSONL:
  - `run_at`, `status`, `risk_level`, key metrics, reason counts, stable `heartbeat_id`
- Strict mode fails on invalid heartbeat shape or failed status.
- `just citizen-test-preset-codec` remains green.
- CI publishes `citizen-preset-contract-bundle-history-slo-digest-heartbeat` artifact (JSON + JSONL).

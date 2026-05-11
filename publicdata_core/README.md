# publicdata_core

Reusable public-data ETL primitives extracted from Vota con La Chola.

Current scope:
- source metadata contract: `SourceDefinition`
- five-step workflow contract: `WorkflowPlan`
- connector contract: `BaseConnector`
- extraction result contract: `Extracted`
- HTTP fetch with retry/Retry-After handling and strict payload guardrails
- raw/fallback provenance helpers
- reusable JSON/CSV parser helpers
- content hashing and stable JSON helpers
- generic `fetch_payload` flow that does not depend on Vota config paths

Contract shape:

1. Register source metadata outside the package.
2. Acquire network or file payload.
3. Persist raw bytes with hashes.
4. Return typed payload metadata.
5. Let project-specific pipelines normalize/publish.

Workflow plans enforce the same abstraction boundary:

1. register
2. acquire
3. normalize
4. enrich
5. publish

Runtime shapes such as strict network, sample replay, archive fallback, queue runtime and static publish are metadata on the plan, not extra conceptual steps.

This package is intentionally small. Domain connectors, SQLite schema modules, document recovery, evidence modeling and publishers should depend on it instead of importing Vota UI/product code.

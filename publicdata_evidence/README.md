# publicdata_evidence

Reusable evidence and review-loop helpers extracted from Vota con La Chola.

Current scope:

- `review_queue.py`: report/apply helpers for topic-evidence review queues over SQLite evidence tables.
- `initdoc_review.py`: initiative-document extraction review helpers, CSV round trips, and Label Studio task import/export.
- `quality.py`: reusable SQLite KPI/gate engine for parliamentary votes, initiatives, documents, and declared evidence.

The package owns review mechanics and adjudication plumbing. Vota keeps product copy, default DB paths, citizen-facing priorities, and UI orchestration.

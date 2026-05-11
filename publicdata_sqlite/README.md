# publicdata_sqlite

Reusable SQLite helpers for public-data ETL projects.

Current scope:
- DB opener with row mapping and FK enforcement
- schema introspection helpers
- additive column helper
- source registry seeding
- source record provenance upserts

Contract shape:

1. Open a SQLite DB with foreign keys enabled.
2. Seed declared public-data sources into a `sources` table.
3. Store raw source records with stable IDs, payloads and hashes.
4. Resolve source-record primary keys for domain tables.
5. Leave domain-specific tables and product-specific schema ownership to the caller.

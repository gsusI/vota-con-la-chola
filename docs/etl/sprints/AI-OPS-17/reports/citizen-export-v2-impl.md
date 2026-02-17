# Citizen Export v2 Implementation Notes

Date: 2026-02-17  
Sprint: `AI-OPS-17`

## What Changed

### Exporter (`scripts/export_citizen_snapshot.py`)
- Implemented **optional v2** keys (additive, backward compatible):
  - `topics[].concern_ids` (server-side deterministic tagging using `ui/citizen/concerns_v1.json`)
  - `meta.methods_available` (methods present for the exported scope/as_of_date)
- Implemented **bounded selection** semantics for `--max-items-per-concern`:
  - when `> 0`, exporter selects up to N topics per concern (stable order) and exports the union, then applies `--max-topics` global cap.

Behavior note:
- Because `--max-items-per-concern` defaults to `60`, the exporter will now preferentially export topics that match at least one concern keyword (untagged topics are excluded under this mode). This should not reduce visible UI coverage, since untagged topics were not navigable via concerns anyway.

### Validator (`scripts/validate_citizen_snapshot.py`)
- Added validation for optional v2 keys when present:
  - `meta.methods_available`: list[str], sorted unique, includes `meta.computed_method`
  - `topics[].concern_ids`: list[str], sorted unique (when present)

## Tests
Added a deterministic unittest:
- `tests/test_export_citizen_snapshot.py`

It seeds a minimal SQLite DB, runs the exporter with `--max-items-per-concern 1`, asserts:
- topics are filtered as expected
- `meta.methods_available` is emitted
- validator accepts the optional v2 keys

Run in Docker:
```bash
just etl-test
```


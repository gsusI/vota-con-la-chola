# AI-OPS-22 Preferences + Alignment Contract (v1)

Date: 2026-02-17  
Owner: L2 Specialist Builder

## Goals
- Local-first preference capture (no server).
- Transparent alignment summary per party:
  - `match`, `mismatch`, `unknown`, `coverage`
- Conservative comparability rules (never impute).
- Optional sharing via URL **fragment** only (opt-in).

## Preference Model (`prefs_v1`)

### Domain
Per `topic_id`, a user preference is one of:
- `support` (yo estaria a favor)
- `oppose` (yo estaria en contra)
- `skip` (implicit: no preference stored for this topic)

### Local Storage
- Key: `vclc_citizen_prefs_v1`
- Value: JSON string, schema:
```json
{
  "version": "v1",
  "updated_at": "ISO timestamp",
  "items": {
    "1": "support",
    "5": "oppose"
  }
}
```

Notes:
- `items` keys are `topic_id` as strings (JSON limitation), values are `support|oppose`.
- Unknown/missing topics in the current snapshot should be dropped on load with a warning banner.

## Alignment Metrics (per party)
Given:
- user prefs set `P` over topics (size `N`)
- party stances `S(topic_id)` from the currently loaded citizen dataset (`combined|votes|declared`)

Rules:
- comparable only when party stance is in `{support, oppose}`.
- `mixed`, `unclear`, `no_signal` are always treated as **unknown** for alignment.

Metrics:
- `match_count`: number of topics where comparable and `S == pref`
- `mismatch_count`: number of topics where comparable and `S != pref`
- `comparable_count`: `match_count + mismatch_count`
- `unknown_count`: `N - comparable_count`
- `coverage_pct`: `comparable_count / N` (if `N>0`, else `0`)
- Optional (transparent) helper:
  - `net = match_count - mismatch_count` (displayed only as derived count, not as a single ranking score)

Sorting (default intent):
- coverage is first-class (unknown should be visible, not hidden).
- when sorting by "net", use tie-breakers: higher coverage, then name.

## Share Link Contract (Opt-In, Fragment Only)

### Precedence
When opening the citizen app:
1. If a URL fragment contains prefs (`#prefs=...`), load those prefs and store them locally.
2. Else, load prefs from localStorage.
3. Else, start empty.

### Format
- Fragment key: `prefs`
- Versioned value:
  - `#prefs=v1:<payload>`
- Payload is ASCII and URL-encoded by the UI.
- Payload encoding (compact v1):
  - CSV of `topic_id=<s|o>` pairs
  - Example: `1=s,5=o,12=s`
  - Where `s` => `support`, `o` => `oppose`

### Privacy rule
- Never write preferences into URL query params automatically.
- Share link generation must be an explicit user action (button).

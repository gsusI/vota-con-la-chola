# AI-OPS-22 URL/State Contract (Citizen)

Date: 2026-02-17  
Owner: L2 Specialist Builder

## Query Params (Shareable, Non-Sensitive)
These remain the canonical share mechanism for view state (no preferences):
- `view`: `detail|dashboard|coherence|alignment`
- `method`: `combined|votes|declared`
- `concerns_ids`: CSV list of concern ids (max 6)
- `concern`: active concern id
- `topic_id`: active topic id (optional)
- `party_id`: focused party id (optional)

Rule:
- The app may write these params automatically via `history.pushState/replaceState`.

## Preferences (Sensitive-ish, Local-First)
User preferences are never written into query params automatically.

Storage:
- localStorage key `vclc_citizen_prefs_v1` is the default persistence.

## URL Fragment (Opt-In Sharing Only)
Share links that include preferences must use the URL fragment:
- `#prefs=v1:<payload>`

Precedence on load:
1. If fragment contains prefs, use them and store locally.
2. Else use localStorage prefs.
3. Else empty.

Payload format:
- compact CSV: `topic_id=<s|o>` pairs (URL-encoded)
- example: `#prefs=v1:1=s,5=o,12=s`

## Compatibility Notes
- Existing shareable query params continue to work for old links.
- Preferences share is additive and opt-in.


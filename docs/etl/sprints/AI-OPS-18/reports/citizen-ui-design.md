# Citizen UI Design (Static GH Pages)

Sprint: `AI-OPS-18`  
Date: `2026-02-17`

## Goal
Turn existing topic/position data into a citizen-first experience:
- start from a *concern* (navigational tag over topics)
- show relevant high-stakes items (topics)
- compare party stances with explicit uncertainty and coverage
- always provide a drill-down path to evidence via existing explorers

## UX Structure
Single-page app (`ui/citizen/index.html`) with three primary zones:
- **Concern picker**: deterministic tag groups (from `concerns_v1.json`)
- **Topic list**: filtered by concern, high-stakes first
- **Party comparison**: aggregated party stance per topic with coverage + confidence

## Honesty Rules (Non-negotiable)
- `no_signal`: show as “Sin senal” (0 evidence / 0 members with signal), never impute.
- `unclear`: show as “Incierto” when signal exists but coverage/consensus is insufficient.
- Mixed stances are explicit (`mixed`), not collapsed.

## Drill-down Links
Every topic/stance card includes links to:
- `../explorer-temas/?topic_set_id=...&topic_id=...` (topic-level view)
- `../explorer/?t=topic_positions...` (raw positions rows behind the aggregation)
- `../explorer/?t=topic_evidence...` (evidence rows for the topic/scope)
- party navigation: `../explorer-politico/?party_id=...`

## Data Inputs (Static)
- Snapshot: `./data/citizen.json` (exported by `scripts/export_citizen_snapshot.py`)
- Concern taxonomy: `./data/concerns_v1.json`

Dev override (for local experiments):
- `?citizen=<path>` overrides snapshot path
- `?concerns=<path>` overrides concerns config path

## URL State
The app encodes navigation state into the URL querystring:
- `concern=<concern_id>`
- `topic_id=<int>`

This enables shareable links and keeps the app usable under GH Pages constraints.

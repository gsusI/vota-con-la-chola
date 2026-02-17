# AI-OPS-22 Query Pack (Baseline + Prefs Sample)

Date: 2026-02-17  
Owner: L2 Specialist Builder

Goal: produce deterministic baseline metrics + a small preference sample artifact for walkthrough/QA.

## Inputs
- Citizen artifacts (built by `just explorer-gh-pages-build`):
  - `docs/gh-pages/citizen/data/citizen.json` (combined)
  - `docs/gh-pages/citizen/data/citizen_votes.json`
  - `docs/gh-pages/citizen/data/citizen_declared.json`
- Concerns:
  - `docs/gh-pages/citizen/data/concerns_v1.json`

## Output Contract
- `docs/etl/sprints/AI-OPS-22/evidence/baseline_metrics.json`
- `docs/etl/sprints/AI-OPS-22/exports/prefs_sample_v1.json`

## Commands

1) Baseline metrics (topics/parties/pairs + stance distribution + topics-per-concern)
```bash
python3 - <<'PY'
import json
from collections import Counter, defaultdict

DATASETS = {
  "combined": "docs/gh-pages/citizen/data/citizen.json",
  "votes": "docs/gh-pages/citizen/data/citizen_votes.json",
  "declared": "docs/gh-pages/citizen/data/citizen_declared.json",
}

def load(path):
  with open(path, "r", encoding="utf-8") as f:
    return json.load(f)

out = {
  "generated_at": "2026-02-17",
  "datasets": {},
  "topics_per_concern": {},
}

base = load(DATASETS["combined"])

# topics per concern_id (from snapshot-provided tags)
per = defaultdict(int)
for t in base.get("topics") or []:
  for cid in (t.get("concern_ids") or []):
    per[str(cid)] += 1
out["topics_per_concern"] = dict(sorted(per.items(), key=lambda kv: (-kv[1], kv[0])))

for name, path in DATASETS.items():
  d = load(path)
  meta = d.get("meta") or {}
  st = Counter()
  for r in d.get("party_topic_positions") or []:
    st[str(r.get("stance") or "no_signal")] += 1
  out["datasets"][name] = {
    "path": path,
    "as_of_date": meta.get("as_of_date"),
    "computed_method": meta.get("computed_method"),
    "topic_set_id": meta.get("topic_set_id"),
    "topics_total": len(d.get("topics") or []),
    "parties_total": len(d.get("parties") or []),
    "pairs_total": len(d.get("party_topic_positions") or []),
    "stance_counts": dict(st),
  }

with open("docs/etl/sprints/AI-OPS-22/evidence/baseline_metrics.json", "w", encoding="utf-8") as f:
  json.dump(out, f, ensure_ascii=True, indent=2, sort_keys=True)
print("WROTE docs/etl/sprints/AI-OPS-22/evidence/baseline_metrics.json")
PY
```

2) Deterministic prefs sample (5 topics, mixed support/oppose)
```bash
python3 - <<'PY'
import json

with open("docs/gh-pages/citizen/data/citizen.json", "r", encoding="utf-8") as f:
  d = json.load(f)

topics = list(d.get("topics") or [])

def key(t):
  hs = 1 if t.get("is_high_stakes") else 0
  rk = t.get("stakes_rank")
  rk = int(rk) if rk is not None else 999999
  tid = int(t.get("topic_id") or 0)
  return (-hs, rk, tid)

topics.sort(key=key)
picked = topics[:5]

items = []
for i, t in enumerate(picked):
  tid = int(t.get("topic_id") or 0)
  pref = "support" if i % 2 == 0 else "oppose"
  items.append({"topic_id": tid, "pref": pref, "label": t.get("label", "")})

out = {
  "version": "prefs_sample_v1",
  "generated_at": "2026-02-17",
  "notes": "Sample preferences for walkthrough/QA. prefs are illustrative, not normative.",
  "items": items,
}

with open("docs/etl/sprints/AI-OPS-22/exports/prefs_sample_v1.json", "w", encoding="utf-8") as f:
  json.dump(out, f, ensure_ascii=True, indent=2, sort_keys=True)
print("WROTE docs/etl/sprints/AI-OPS-22/exports/prefs_sample_v1.json")
PY
```

## Acceptance Checks
```bash
python3 -c "import json; json.load(open('docs/etl/sprints/AI-OPS-22/evidence/baseline_metrics.json'))"
python3 -c "import json; json.load(open('docs/etl/sprints/AI-OPS-22/exports/prefs_sample_v1.json'))"
```


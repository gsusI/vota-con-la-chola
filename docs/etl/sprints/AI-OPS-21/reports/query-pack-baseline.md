# AI-OPS-21 Query Pack (Baseline Coverage + Coherence)

Date:
- `2026-02-17`

Sprint:
- `AI-OPS-21`

Goal:
- Produce a deterministic baseline evidence packet for:
  - coverage by concern and method (`combined|votes|declared`)
  - conservative coherence between `votes` and `declared` (only when comparable)

## Inputs
- Citizen artifacts (static):
  - `docs/gh-pages/citizen/data/citizen.json`
  - `docs/gh-pages/citizen/data/citizen_votes.json`
  - `docs/gh-pages/citizen/data/citizen_declared.json`
- Concerns config:
  - `ui/citizen/concerns_v1.json`

## Commands (Baseline Evidence)

Generate coverage + coherence JSON under sprint evidence:
```bash
python3 - <<'PY'
import json
from pathlib import Path
from datetime import datetime, timezone

OUT_DIR = Path('docs/etl/sprints/AI-OPS-21/evidence')
OUT_DIR.mkdir(parents=True, exist_ok=True)

def read(p: Path):
    return json.loads(p.read_text(encoding='utf-8'))

def stance_bucket(s: str) -> str:
    k = str(s or 'no_signal')
    if k in ('support','oppose','mixed','unclear','no_signal'):
        return k
    return 'unclear'

def is_comparable(s: str) -> bool:
    return s in ('support','oppose')

concerns_cfg = read(Path('ui/citizen/concerns_v1.json'))
concerns = concerns_cfg.get('concerns') or []
concerns = [c for c in concerns if isinstance(c, dict) and str(c.get('id') or '').strip()]

paths = {
    'combined': Path('docs/gh-pages/citizen/data/citizen.json'),
    'votes': Path('docs/gh-pages/citizen/data/citizen_votes.json'),
    'declared': Path('docs/gh-pages/citizen/data/citizen_declared.json'),
}

data = {k: read(p) for k,p in paths.items()}

methods = {}
for k,obj in data.items():
    meta = obj.get('meta') or {}
    methods[k] = {
        'path': str(paths[k]),
        'computed_method': meta.get('computed_method'),
        'as_of_date': meta.get('as_of_date'),
        'topics': len(obj.get('topics') or []),
        'parties': len(obj.get('parties') or []),
        'ptp': len(obj.get('party_topic_positions') or []),
    }

def ids(obj, key):
    return [int(x.get(key) or 0) for x in (obj or []) if int(x.get(key) or 0) > 0]

base_topics = ids(data['combined'].get('topics') or [], 'topic_id')
base_parties = ids(data['combined'].get('parties') or [], 'party_id')

def diff(a, b):
    sa, sb = set(a), set(b)
    return {
        'missing_in_b': sorted(sa - sb)[:50],
        'extra_in_b': sorted(sb - sa)[:50],
    }

consistency = {
    'topics': {
        'combined_vs_votes': diff(base_topics, ids(data['votes'].get('topics') or [], 'topic_id')),
        'combined_vs_declared': diff(base_topics, ids(data['declared'].get('topics') or [], 'topic_id')),
    },
    'parties': {
        'combined_vs_votes': diff(base_parties, ids(data['votes'].get('parties') or [], 'party_id')),
        'combined_vs_declared': diff(base_parties, ids(data['declared'].get('parties') or [], 'party_id')),
    },
}

by_topic = {int(t.get('topic_id') or 0): t for t in (data['combined'].get('topics') or [])}
def topic_concerns(tid: int):
    t = by_topic.get(int(tid)) or {}
    cids = t.get('concern_ids')
    if isinstance(cids, list):
        return [str(x) for x in cids if str(x).strip()]
    return []

def build_pos_map(obj):
    m = {}
    for r in obj.get('party_topic_positions') or []:
        tid = int(r.get('topic_id') or 0)
        pid = int(r.get('party_id') or 0)
        if tid <= 0 or pid <= 0:
            continue
        m[(tid,pid)] = stance_bucket(r.get('stance'))
    return m

pos = {k: build_pos_map(obj) for k,obj in data.items()}
party_ids = base_parties

def agg_for_topics(topic_ids, method_key):
    counts = { 'support':0,'oppose':0,'mixed':0,'unclear':0,'no_signal':0 }
    total = 0
    for tid in topic_ids:
        for pid in party_ids:
            total += 1
            s = pos[method_key].get((tid,pid),'no_signal')
            counts[s] += 1
    clear = counts['support'] + counts['oppose'] + counts['mixed']
    any_signal = total - counts['no_signal']
    return {
        'cells_total': total,
        'cells_any_signal': any_signal,
        'cells_any_signal_pct': (any_signal / total) if total else 0,
        'cells_clear': clear,
        'cells_clear_pct': (clear / total) if total else 0,
        'cells_by_stance': counts,
    }

def coherence_for_topics(topic_ids):
    total = 0
    comparable = 0
    match = 0
    mismatch = 0
    not_comp = 0
    for tid in topic_ids:
        for pid in party_ids:
            total += 1
            sv = pos['votes'].get((tid,pid),'no_signal')
            sd = pos['declared'].get((tid,pid),'no_signal')
            if is_comparable(sv) and is_comparable(sd):
                comparable += 1
                if sv == sd:
                    match += 1
                else:
                    mismatch += 1
            else:
                not_comp += 1
    return {
        'cells_total': total,
        'comparable_cells': comparable,
        'comparable_pct': (comparable / total) if total else 0,
        'match_cells': match,
        'mismatch_cells': mismatch,
        'mismatch_pct_of_comparable': (mismatch / comparable) if comparable else 0,
        'not_comparable_cells': not_comp,
    }

coverage_rows = []
coherence_rows = []
for c in concerns:
    cid = str(c.get('id') or '').strip()
    label = str(c.get('label') or cid)
    topic_ids = [tid for tid in base_topics if cid in set(topic_concerns(tid))]
    topic_ids = sorted(set(topic_ids))

    coverage_rows.append({
        'concern_id': cid,
        'label': label,
        'topics_total': len(topic_ids),
        'methods': {
            'combined': agg_for_topics(topic_ids, 'combined'),
            'votes': agg_for_topics(topic_ids, 'votes'),
            'declared': agg_for_topics(topic_ids, 'declared'),
        },
    })

    coherence_rows.append({
        'concern_id': cid,
        'label': label,
        'topics_total': len(topic_ids),
        **coherence_for_topics(topic_ids),
    })

all_tagged = [tid for tid in base_topics if topic_concerns(tid)]
all_tagged = sorted(set(all_tagged))
generated_at = datetime.now(timezone.utc).isoformat(timespec='seconds')

baseline = {
    'generated_at': generated_at,
    'inputs': {
        'concerns_path': 'ui/citizen/concerns_v1.json',
        **{k: str(v) for k,v in paths.items()},
    },
    'methods': methods,
    'consistency': consistency,
    'parties_total': len(party_ids),
    'topics_total': len(base_topics),
    'topics_tagged_total': len(all_tagged),
    'coverage_by_concern': coverage_rows,
    'coverage_overall_tagged': {
        'topics_total': len(all_tagged),
        'methods': {
            'combined': agg_for_topics(all_tagged, 'combined'),
            'votes': agg_for_topics(all_tagged, 'votes'),
            'declared': agg_for_topics(all_tagged, 'declared'),
        },
    },
}

coh_out = {
    'generated_at': generated_at,
    'inputs': baseline['inputs'],
    'parties_total': len(party_ids),
    'topics_total': len(base_topics),
    'topics_tagged_total': len(all_tagged),
    'coherence_by_concern': coherence_rows,
    'coherence_overall_tagged': {
        'topics_total': len(all_tagged),
        **coherence_for_topics(all_tagged),
    },
}

(OUT_DIR / 'baseline_coverage.json').write_text(json.dumps(baseline, indent=2, ensure_ascii=True), encoding='utf-8')
(OUT_DIR / 'baseline_coherence.json').write_text(json.dumps(coh_out, indent=2, ensure_ascii=True), encoding='utf-8')
print('WROTE', OUT_DIR / 'baseline_coverage.json')
print('WROTE', OUT_DIR / 'baseline_coherence.json')
PY
```

Outputs:
- `docs/etl/sprints/AI-OPS-21/evidence/baseline_coverage.json`
- `docs/etl/sprints/AI-OPS-21/evidence/baseline_coherence.json`

## Baseline Summary (current snapshot)
Use these as a reality check for UI empty-states:
- `declared` has low signal density (most cells are `no_signal`).
- Coherence comparable cells (votes vs declared, only `support/oppose`) are very sparse; coherence UI must treat this as expected, not as an error.


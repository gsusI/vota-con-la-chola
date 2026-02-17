# AI-OPS-08 Kickoff

Date: 2026-02-16  
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

## Sprint Focus

Tracker-contract reconciliation and waiver burn-down for operational gate determinism.

## Objective

Freeze PASS/FAIL conditions and execution order so L2/L1 can execute without gate ambiguity.

## Inputs Reviewed

- `docs/roadmap.md`
- `docs/roadmap-tecnico.md`
- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/etl/sprints/AI-OPS-07/closeout.md`
- `docs/gh-pages/explorer-sources/data/status.json`
- `sqlite3 etl/data/staging/politicos-es.db`

## Baseline Commands (Exact Outputs)

### 1) Tracker status baseline

Command:
```bash
just etl-tracker-status
```

Output:
```text
docker compose run --rm --build etl "python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md"
 Image vota-con-la-chola-etl:local Building 
#1 [internal] load local bake definitions
#1 reading from stdin 690B done
#1 DONE 0.0s

#2 [internal] load build definition from Dockerfile
#2 transferring dockerfile: 604B done
#2 DONE 0.0s

#3 [internal] load metadata for docker.io/library/python:3.12-slim
#3 DONE 0.6s

#4 [internal] load .dockerignore
#4 transferring context: 336B done
#4 DONE 0.0s

#5 [1/6] FROM docker.io/library/python:3.12-slim@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab
#5 resolve docker.io/library/python:3.12-slim@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab done
#5 DONE 0.0s

#6 [internal] load build context
#6 transferring context: 2.93MB 0.8s done
#6 DONE 0.8s

#7 [4/6] COPY requirements.txt /tmp/requirements.txt
#7 CACHED

#8 [5/6] RUN if [ -s /tmp/requirements.txt ]; then pip install --no-cache-dir -r /tmp/requirements.txt; fi
#8 CACHED

#9 [2/6] RUN apt-get update && apt-get install -y --no-install-recommends     ca-certificates     curl     sqlite3   && rm -rf /var/lib/apt/lists/*
#9 CACHED

#10 [3/6] WORKDIR /workspace
#10 CACHED

#11 [6/6] COPY . /workspace
#11 CACHED

#12 exporting to image
#12 exporting layers done
#12 exporting manifest sha256:cae626c39b90522d0c6515af49463a0992bc4b4317f3ab9f8d0af7c273d3d8a0 done
#12 exporting config sha256:a75c149700be89f5af079e05bcd2e69dfa4addb9013b58f9f8a6efa6d5e04fe9 done
#12 exporting attestation manifest sha256:7df1b0660edbd4fc16f544b8c889d1a772ce9e970ccc341a477bb91582163bcd done
#12 exporting manifest list sha256:535331e8ea74fbcd6fe23fb2de82ca415b0b854b23b95de91609e87fb4f43809 done
#12 naming to docker.io/library/vota-con-la-chola-etl:local done
#12 unpacking to docker.io/library/vota-con-la-chola-etl:local done
#12 DONE 0.0s

#13 resolving provenance for metadata file
#13 DONE 0.0s
 Image vota-con-la-chola-etl:local Built 
 Container vota-con-la-chola-etl-run-7cf6a7a9653e Creating 
 Container vota-con-la-chola-etl-run-7cf6a7a9653e Created 
source_id                                 | checklist | sql     | runs_ok/total | max_net | max_any | last_loaded | net/fallback_fetches | result  
------------------------------------------+-----------+---------+---------------+---------+---------+-------------+----------------------+---------
asamblea_ceuta_diputados                  | DONE      | DONE    | 2/3           | 25      | 25      | 25          | 1/0                  | OK      
asamblea_extremadura_diputados            | DONE      | DONE    | 1/1           | 65      | 65      | 65          | 1/0                  | OK      
asamblea_madrid_ocupaciones               | DONE      | DONE    | 3/3           | 9188    | 9188    | 9188        | 1/0                  | OK      
asamblea_melilla_diputados                | DONE      | DONE    | 3/3           | 26      | 26      | 26          | 1/1                  | OK      
asamblea_murcia_diputados                 | DONE      | DONE    | 1/1           | 54      | 54      | 54          | 1/0                  | OK      
boe_api_legal                             | N/A       | DONE    | 3/3           | 298     | 298     | 298         | 1/2                  | OK      
congreso_diputados                        | DONE      | DONE    | 6/7           | 350     | 350     | 350         | 1/1                  | OK      
congreso_iniciativas                      | N/A       | DONE    | 4/4           | 491     | 491     | 491         | 1/1                  | OK      
congreso_intervenciones                   | N/A       | DONE    | 1/2           | 614     | 614     | 614         | 1/0                  | OK      
congreso_votaciones                       | N/A       | DONE    | 12/20         | 300     | 300     | 40          | 8/1                  | OK      
cortes_aragon_diputados                   | DONE      | DONE    | 5/10          | 75      | 75      | 75          | 1/1                  | OK      
cortes_clm_diputados                      | DONE      | DONE    | 1/1           | 33      | 33      | 33          | 1/0                  | OK      
cortes_cyl_procuradores                   | DONE      | DONE    | 1/1           | 81      | 81      | 81          | 1/0                  | OK      
corts_valencianes_diputats                | DONE      | DONE    | 2/2           | 99      | 99      | 99          | 1/1                  | OK      
europarl_meps                             | DONE      | DONE    | 4/4           | 60      | 60      | 60          | 1/1                  | OK      
infoelectoral_descargas                   | DONE      | DONE    | 3/3           | 263     | 263     | 263         | 1/1                  | OK      
infoelectoral_procesos                    | DONE      | DONE    | 5/6           | 257     | 257     | 257         | 1/1                  | OK      
jgpa_diputados                            | DONE      | DONE    | 1/1           | 45      | 45      | 45          | 1/0                  | OK      
moncloa_referencias                       | DONE      | DONE    | 8/10          | 2       | 20      | 2           | 2/6                  | OK      
moncloa_rss_referencias                   | DONE      | DONE    | 9/12          | 8       | 8       | 4           | 2/7                  | OK      
municipal_concejales                      | DONE      | DONE    | 2/2           | 66895   | 66895   | 66895       | 2/0                  | OK      
parlament_balears_diputats                | DONE      | DONE    | 1/1           | 59      | 59      | 59          | 1/0                  | OK      
parlament_catalunya_diputats              | DONE      | DONE    | 1/1           | 135     | 135     | 135         | 1/0                  | OK      
parlamento_andalucia_diputados            | DONE      | DONE    | 1/1           | 109     | 109     | 109         | 1/0                  | OK      
parlamento_canarias_diputados             | DONE      | DONE    | 1/1           | 79      | 79      | 79          | 1/0                  | OK      
parlamento_cantabria_diputados            | DONE      | DONE    | 2/2           | 35      | 35      | 35          | 1/0                  | OK      
parlamento_galicia_deputados              | PARTIAL   | PARTIAL | 5/8           | 0       | 75      | 75          | 0/5                  | OK      
parlamento_larioja_diputados              | DONE      | DONE    | 1/1           | 33      | 33      | 33          | 1/0                  | OK      
parlamento_navarra_parlamentarios_forales | PARTIAL   | DONE    | 3/8           | 50      | 50      | 50          | 1/2                  | MISMATCH
parlamento_vasco_parlamentarios           | DONE      | DONE    | 1/1           | 75      | 75      | 75          | 1/0                  | OK      
senado_iniciativas                        | N/A       | DONE    | 4/5           | 3607    | 3607    | 3607        | 2/1                  | OK      
senado_senadores                          | DONE      | DONE    | 6/8           | 1560    | 1560    | 1560        | 3/1                  | OK      
senado_votaciones                         | N/A       | DONE    | 28/43         | 5534    | 5534    | 1           | 16/1                 | OK      

tracker_sources: 27
sources_in_db: 33
mismatches: 1
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0
```

### 2) Strict gate probe (non-blocking)

Command:
```bash
just etl-tracker-gate || true
```

Output:
```text
docker compose run --rm --build etl "python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-mismatch --fail-on-done-zero-real"
 Image vota-con-la-chola-etl:local Building 
#1 [internal] load local bake definitions
#1 reading from stdin 690B done
#1 DONE 0.0s

#2 [internal] load build definition from Dockerfile
#2 transferring dockerfile: 604B done
#2 DONE 0.0s

#3 [internal] load metadata for docker.io/library/python:3.12-slim
#3 DONE 0.3s

#4 [internal] load .dockerignore
#4 transferring context: 336B done
#4 DONE 0.0s

#5 [1/6] FROM docker.io/library/python:3.12-slim@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab
#5 resolve docker.io/library/python:3.12-slim@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab 0.0s done
#5 DONE 0.0s

#6 [internal] load build context
#6 transferring context: 2.93MB 0.7s done
#6 DONE 0.8s

#7 [5/6] RUN if [ -s /tmp/requirements.txt ]; then pip install --no-cache-dir -r /tmp/requirements.txt; fi
#7 CACHED

#8 [2/6] RUN apt-get update && apt-get install -y --no-install-recommends     ca-certificates     curl     sqlite3   && rm -rf /var/lib/apt/lists/*
#8 CACHED

#9 [3/6] WORKDIR /workspace
#9 CACHED

#10 [4/6] COPY requirements.txt /tmp/requirements.txt
#10 CACHED

#11 [6/6] COPY . /workspace
#11 CACHED

#12 exporting to image
#12 exporting layers done
#12 exporting manifest sha256:cae626c39b90522d0c6515af49463a0992bc4b4317f3ab9f8d0af7c273d3d8a0 done
#12 exporting config sha256:a75c149700be89f5af079e05bcd2e69dfa4addb9013b58f9f8a6efa6d5e04fe9 done
#12 exporting attestation manifest sha256:aace071e0462ccd19bd5a634d9a92e6daeab5e6bb6a7f4443f50ab7c5f454ab9 done
#12 exporting manifest list sha256:690fddba123df67575104d489820df37fb08a2d0ad0181343283efe196e85a0f done
#12 naming to docker.io/library/vota-con-la-chola-etl:local done
#12 unpacking to docker.io/library/vota-con-la-chola-etl:local done
#12 DONE 0.0s

#13 resolving provenance for metadata file
#13 DONE 0.0s
 Image vota-con-la-chola-etl:local Built 
 Container vota-con-la-chola-etl-run-8278e2c17963 Creating 
 Container vota-con-la-chola-etl-run-8278e2c17963 Created 
FAIL: checklist/sql mismatches detected.
source_id                                 | checklist | sql     | runs_ok/total | max_net | max_any | last_loaded | net/fallback_fetches | result  
------------------------------------------+-----------+---------+---------------+---------+---------+-------------+----------------------+---------
asamblea_ceuta_diputados                  | DONE      | DONE    | 2/3           | 25      | 25      | 25          | 1/0                  | OK      
asamblea_extremadura_diputados            | DONE      | DONE    | 1/1           | 65      | 65      | 65          | 1/0                  | OK      
asamblea_madrid_ocupaciones               | DONE      | DONE    | 3/3           | 9188    | 9188    | 9188        | 1/0                  | OK      
asamblea_melilla_diputados                | DONE      | DONE    | 3/3           | 26      | 26      | 26          | 1/1                  | OK      
asamblea_murcia_diputados                 | DONE      | DONE    | 1/1           | 54      | 54      | 54          | 1/0                  | OK      
boe_api_legal                             | N/A       | DONE    | 3/3           | 298     | 298     | 298         | 1/2                  | OK      
congreso_diputados                        | DONE      | DONE    | 6/7           | 350     | 350     | 350         | 1/1                  | OK      
congreso_iniciativas                      | N/A       | DONE    | 4/4           | 491     | 491     | 491         | 1/1                  | OK      
congreso_intervenciones                   | N/A       | DONE    | 1/2           | 614     | 614     | 614         | 1/0                  | OK      
congreso_votaciones                       | N/A       | DONE    | 12/20         | 300     | 300     | 40          | 8/1                  | OK      
cortes_aragon_diputados                   | DONE      | DONE    | 5/10          | 75      | 75      | 75          | 1/1                  | OK      
cortes_clm_diputados                      | DONE      | DONE    | 1/1           | 33      | 33      | 33          | 1/0                  | OK      
cortes_cyl_procuradores                   | DONE      | DONE    | 1/1           | 81      | 81      | 81          | 1/0                  | OK      
corts_valencianes_diputats                | DONE      | DONE    | 2/2           | 99      | 99      | 99          | 1/1                  | OK      
europarl_meps                             | DONE      | DONE    | 4/4           | 60      | 60      | 60          | 1/1                  | OK      
infoelectoral_descargas                   | DONE      | DONE    | 3/3           | 263     | 263     | 263         | 1/1                  | OK      
infoelectoral_procesos                    | DONE      | DONE    | 5/6           | 257     | 257     | 257         | 1/1                  | OK      
jgpa_diputados                            | DONE      | DONE    | 1/1           | 45      | 45      | 45          | 1/0                  | OK      
moncloa_referencias                       | DONE      | DONE    | 8/10          | 2       | 20      | 2           | 2/6                  | OK      
moncloa_rss_referencias                   | DONE      | DONE    | 9/12          | 8       | 8       | 4           | 2/7                  | OK      
municipal_concejales                      | DONE      | DONE    | 2/2           | 66895   | 66895   | 66895       | 2/0                  | OK      
parlament_balears_diputats                | DONE      | DONE    | 1/1           | 59      | 59      | 59          | 1/0                  | OK      
parlament_catalunya_diputats              | DONE      | DONE    | 1/1           | 135     | 135     | 135         | 1/0                  | OK      
parlamento_andalucia_diputados            | DONE      | DONE    | 1/1           | 109     | 109     | 109         | 1/0                  | OK      
parlamento_canarias_diputados             | DONE      | DONE    | 1/1           | 79      | 79      | 79          | 1/0                  | OK      
parlamento_cantabria_diputados            | DONE      | DONE    | 2/2           | 35      | 35      | 35          | 1/0                  | OK      
parlamento_galicia_deputados              | PARTIAL   | PARTIAL | 5/8           | 0       | 75      | 75          | 0/5                  | OK      
parlamento_larioja_diputados              | DONE      | DONE    | 1/1           | 33      | 33      | 33          | 1/0                  | OK      
parlamento_navarra_parlamentarios_forales | PARTIAL   | DONE    | 3/8           | 50      | 50      | 50          | 1/2                  | MISMATCH
parlamento_vasco_parlamentarios           | DONE      | DONE    | 1/1           | 75      | 75      | 75          | 1/0                  | OK      
senado_iniciativas                        | N/A       | DONE    | 4/5           | 3607    | 3607    | 3607        | 2/1                  | OK      
senado_senadores                          | DONE      | DONE    | 6/8           | 1560    | 1560    | 1560        | 3/1                  | OK      
senado_votaciones                         | N/A       | DONE    | 28/43         | 5534    | 5534    | 1           | 16/1                 | OK      

tracker_sources: 27
sources_in_db: 33
mismatches: 1
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0

error: Recipe `etl-tracker-gate` failed on line 544 with exit code 1
```

### 3) Policy-aware strict checker

Command:
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/sprints/AI-OPS-07/evidence/mismatch-policy-applied.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real
```

Output:
```text
source_id                                 | checklist | sql     | runs_ok/total | max_net | max_any | last_loaded | net/fallback_fetches | result         
------------------------------------------+-----------+---------+---------------+---------+---------+-------------+----------------------+----------------
asamblea_ceuta_diputados                  | DONE      | DONE    | 2/3           | 25      | 25      | 25          | 1/0                  | OK             
asamblea_extremadura_diputados            | DONE      | DONE    | 1/1           | 65      | 65      | 65          | 1/0                  | OK             
asamblea_madrid_ocupaciones               | DONE      | DONE    | 3/3           | 9188    | 9188    | 9188        | 1/0                  | OK             
asamblea_melilla_diputados                | DONE      | DONE    | 3/3           | 26      | 26      | 26          | 1/1                  | OK             
asamblea_murcia_diputados                 | DONE      | DONE    | 1/1           | 54      | 54      | 54          | 1/0                  | OK             
boe_api_legal                             | N/A       | DONE    | 3/3           | 298     | 298     | 298         | 1/2                  | OK             
congreso_diputados                        | DONE      | DONE    | 6/7           | 350     | 350     | 350         | 1/1                  | OK             
congreso_iniciativas                      | N/A       | DONE    | 4/4           | 491     | 491     | 491         | 1/1                  | OK             
congreso_intervenciones                   | N/A       | DONE    | 1/2           | 614     | 614     | 614         | 1/0                  | OK             
congreso_votaciones                       | N/A       | DONE    | 12/20         | 300     | 300     | 40          | 8/1                  | OK             
cortes_aragon_diputados                   | DONE      | DONE    | 5/10          | 75      | 75      | 75          | 1/1                  | OK             
cortes_clm_diputados                      | DONE      | DONE    | 1/1           | 33      | 33      | 33          | 1/0                  | OK             
cortes_cyl_procuradores                   | DONE      | DONE    | 1/1           | 81      | 81      | 81          | 1/0                  | OK             
corts_valencianes_diputats                | DONE      | DONE    | 2/2           | 99      | 99      | 99          | 1/1                  | OK             
europarl_meps                             | DONE      | DONE    | 4/4           | 60      | 60      | 60          | 1/1                  | OK             
infoelectoral_descargas                   | DONE      | DONE    | 3/3           | 263     | 263     | 263         | 1/1                  | OK             
infoelectoral_procesos                    | DONE      | DONE    | 5/6           | 257     | 257     | 257         | 1/1                  | OK             
jgpa_diputados                            | DONE      | DONE    | 1/1           | 45      | 45      | 45          | 1/0                  | OK             
moncloa_referencias                       | DONE      | DONE    | 8/10          | 2       | 20      | 2           | 2/6                  | OK             
moncloa_rss_referencias                   | DONE      | DONE    | 9/12          | 8       | 8       | 4           | 2/7                  | OK             
municipal_concejales                      | DONE      | DONE    | 2/2           | 66895   | 66895   | 66895       | 2/0                  | OK             
parlament_balears_diputats                | DONE      | DONE    | 1/1           | 59      | 59      | 59          | 1/0                  | OK             
parlament_catalunya_diputats              | DONE      | DONE    | 1/1           | 135     | 135     | 135         | 1/0                  | OK             
parlamento_andalucia_diputados            | DONE      | DONE    | 1/1           | 109     | 109     | 109         | 1/0                  | OK             
parlamento_canarias_diputados             | DONE      | DONE    | 1/1           | 79      | 79      | 79          | 1/0                  | OK             
parlamento_cantabria_diputados            | DONE      | DONE    | 2/2           | 35      | 35      | 35          | 1/0                  | OK             
parlamento_galicia_deputados              | PARTIAL   | PARTIAL | 5/8           | 0       | 75      | 75          | 0/5                  | OK             
parlamento_larioja_diputados              | DONE      | DONE    | 1/1           | 33      | 33      | 33          | 1/0                  | OK             
parlamento_navarra_parlamentarios_forales | PARTIAL   | DONE    | 3/8           | 50      | 50      | 50          | 1/2                  | WAIVED_MISMATCH
parlamento_vasco_parlamentarios           | DONE      | DONE    | 1/1           | 75      | 75      | 75          | 1/0                  | OK             
senado_iniciativas                        | N/A       | DONE    | 4/5           | 3607    | 3607    | 3607        | 2/1                  | OK             
senado_senadores                          | DONE      | DONE    | 6/8           | 1560    | 1560    | 1560        | 3/1                  | OK             
senado_votaciones                         | N/A       | DONE    | 28/43         | 5534    | 5534    | 1           | 16/1                 | OK             

tracker_sources: 27
sources_in_db: 33
mismatches: 0
waived_mismatches: 1
waivers_active: 1
waivers_expired: 0
done_zero_real: 0
```

### 4) Data integrity

Command:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
```

Output:
```text
fk_violations
-------------
0            
```

### 5) Review queue health

Command:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS topic_evidence_reviews_pending FROM topic_evidence_reviews WHERE lower(status)='pending';"
```

Output:
```text
topic_evidence_reviews_pending
------------------------------
0                             
```

### 6) Moncloa policy events baseline

Command:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_moncloa FROM policy_events WHERE source_id LIKE 'moncloa_%';"
```

Output:
```text
policy_events_moncloa
---------------------
28                   
```

### 7) BOE policy events baseline

Command:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS policy_events_boe FROM policy_events WHERE source_id LIKE 'boe_%';"
```

Output:
```text
policy_events_boe
-----------------
298              
```

### 8) Payload summary for Moncloa/BOE/Navarra mismatch_state

Command:
```bash
python3 - <<'PY'
import json
from pathlib import Path
from collections import Counter

p = Path('docs/gh-pages/explorer-sources/data/status.json')
obj = json.loads(p.read_text(encoding='utf-8'))
sources = obj.get('sources', [])

print('sources_total', len(sources))
print('mismatch_counts', dict(Counter((s.get('mismatch_state') or 'UNKNOWN') for s in sources)))
for sid in [
    'moncloa_referencias',
    'moncloa_rss_referencias',
    'boe_api_legal',
    'parlamento_navarra_parlamentarios_forales',
]:
    row = next((s for s in sources if s.get('source_id') == sid), None)
    if not row:
        print('missing', sid)
        continue
    tracker = row.get('tracker') or {}
    print(
        sid,
        {
            'tracker_status': tracker.get('status', ''),
            'sql_status': row.get('sql_status', ''),
            'mismatch_state': row.get('mismatch_state', ''),
            'mismatch_waived': row.get('mismatch_waived', False),
            'waiver_expiry': row.get('waiver_expiry', ''),
        },
    )
PY
```

Output:
```text
sources_total 33
mismatch_counts {'MATCH': 26, 'MISMATCH': 1, 'UNTRACKED': 6}
moncloa_referencias {'tracker_status': 'DONE', 'sql_status': 'DONE', 'mismatch_state': 'MATCH', 'mismatch_waived': False, 'waiver_expiry': ''}
moncloa_rss_referencias {'tracker_status': 'DONE', 'sql_status': 'DONE', 'mismatch_state': 'MATCH', 'mismatch_waived': False, 'waiver_expiry': ''}
boe_api_legal {'tracker_status': '', 'sql_status': 'DONE', 'mismatch_state': 'UNTRACKED', 'mismatch_waived': False, 'waiver_expiry': ''}
parlamento_navarra_parlamentarios_forales {'tracker_status': 'PARTIAL', 'sql_status': 'DONE', 'mismatch_state': 'MISMATCH', 'mismatch_waived': False, 'waiver_expiry': ''}
```

## Baseline Snapshot (Locked)

- `fk_violations = 0`
- `topic_evidence_reviews_pending = 0`
- `policy_events_moncloa = 28`
- `policy_events_boe = 298`
- `strict mismatches = 1`
- `waiver-aware mismatches = 0`
- `waived_mismatches = 1`
- `waivers_active = 1`
- `waivers_expired = 0`
- `done_zero_real = 0`
- payload `mismatch_counts = {'MATCH': 26, 'MISMATCH': 1, 'UNTRACKED': 6}`
- payload focus rows:
- `moncloa_referencias => MATCH`
- `moncloa_rss_referencias => MATCH`
- `boe_api_legal => UNTRACKED`
- `parlamento_navarra_parlamentarios_forales => MISMATCH`

## Must-Pass Gates (AI-OPS-08)

| Gate | PASS condition | Evidence command |
|---|---|---|
| Gate G1 Data integrity | `fk_violations = 0` | `sqlite3 ... "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"` |
| Gate G2 Queue health | `topic_evidence_reviews_pending = 0` | `sqlite3 ... "SELECT COUNT(*) AS topic_evidence_reviews_pending ..."` |
| Gate G3 Strict policy behavior | Unwaived `mismatches = 0`, `waivers_expired = 0`, `done_zero_real = 0` in strict policy path | `python3 scripts/e2e_tracker_status.py ... --waivers ... --fail-on-mismatch --fail-on-done-zero-real` |
| Gate G4 Tracker-contract alignment | `boe_api_legal` must no longer be `UNTRACKED`; Moncloa rows stay `MATCH` | payload summary script + `just etl-tracker-status` |
| Gate G5 Coverage non-regression | `policy_events_moncloa >= 28` and `policy_events_boe >= 298` at closeout | SQL counts on `policy_events` |
| Gate G6 Tracker wording reconciliation | Tracker rows (`Marco legal electoral`, `Accion ejecutiva`, `Navarra`, `Galicia`) reflect evidence + blocker + next command semantics | `rg` over `docs/etl/e2e-scrape-load-tracker.md` + sprint evidence note |
| Gate G7 Workload balance | L1 delivers majority throughput artifacts for prep/apply/reconcile/evidence | sprint artifact existence checks |

## Ordered Execution Sequence (Locked)

| Task | Owner | depends_on | parallel_group | model_lane |
|---|---|---|---|---|
| T1 Kickoff baseline freeze (this doc) | L3 | none | P1 | HI |
| T2 BOE tracker mapping hardening | L2 | T1 | P2 | HI |
| T3 Default gate waiver registry hardening | L2 | T1 | P2 | HI |
| T4 Waiver/tracker contract batch prep | L1 | T2,T3 | P3 | FAST |
| T5 Apply/recompute + strict vs waiver-aware deltas | L1 | T2,T3 | P4 | FAST |
| T6 Tracker row reconciliation update | L1 | T4,T5 | P5 | FAST |
| T7 Final evidence packet + payload parity | L1 | T5,T6 | P6 | FAST |
| T8 Closeout PASS/FAIL | L3 | T7 | P7 | HI |

Critical dependency path:
- `T1 -> T2 -> T5 -> T6 -> T7 -> T8`

Queue waves (locked):
1. `HI` wave: `T1, T2, T3`
2. `FAST` wave: `T4, T5, T6, T7`
3. `HI` wave: `T8`

Lane switches:
- `2` (`HI -> FAST -> HI`)

## PASS/FAIL Policy Lock

- `PASS` only if `Gate G1..G7` are all green in the same AI-OPS-08 evidence set.
- `FAIL` if any Gate is red; carryover must include owner (`L3/L2/L1`), blocker evidence, and first command.
- Waiver use is temporary and auditable: expired waivers fail the gate by policy.

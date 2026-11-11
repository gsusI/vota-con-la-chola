#!/usr/bin/env python3
"""Validate the democratic-conduct ledger (etl/data/seeds/democracy_conduct_v1.json and its .d/ part files).

Mechanical gate only (schema, sources, codebook): it proves shape, not truth. Truth is the reviewer sample
documented in docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/README.md.

    python3 scripts/validate_democracy_conduct.py                       # seed + every part file
    python3 scripts/validate_democracy_conduct.py etl/data/seeds/democracy_conduct_v1.d/events_pilot.json
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = REPO_ROOT / "etl/data/seeds/democracy_conduct_v1.json"
PARTS_DIR = REPO_ROOT / "etl/data/seeds/democracy_conduct_v1.d"

PARTIES = {"psoe", "pp", "vox", "sumar", "podemos", "erc", "junts", "bildu", "pnv", "bng", "cc", "upn"}
INDICATORS = {"reglas", "legitimidad", "violencia", "libertades", "minorias", "justicia", "corrupcion", "medios", "contrapesos"}
ROLES = {"national_government", "regional_government", "local_government", "opposition", "party_organization"}
ATTRIBUTIONS = {"government_act", "group_initiative", "office_holder", "party"}
LINEAGES = {"same", "list", "predecessor", "person"}
# Severity rule (README 1.3): the legal force of the finding fixes the severity.
FINDING_SEVERITY = {
    "court_annulment_full": 3,
    "conviction_prison_ge1": 3,
    "court_annulment_partial": 2,
    "amparo": 2,
    "binding_declaration": 2,
    "conviction_other": 2,
    "civil_liability_party": 2,
    "sanction_jec": 2,
    "sanction_tcu": 2,
    "nonbinding_finding": 1,
}
WINDOW_START = "2011-12-21"
ALLOWED_HOSTS = (
    "boe.es", "tribunalconstitucional.es", "poderjudicial.es", "venice.coe.int", "coe.int", "commission.europa.eu",
    "ec.europa.eu", "eur-lex.europa.eu", "junta-electoral-central.es", "juntaelectoralcentral.es", "tcu.es",
    "congreso.es", "senado.es", "parlament.gv.at", "parcan.es", "junts.cat", "esquerra.cat", "ohchr.org", "cnmc.es", "gob.es", "hudoc.echr.coe.int", "parlament.cat", "dogc.gencat.cat", "europa.eu",
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def words(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def check_event(ev: dict, where: str, today: str) -> list[str]:
    errs: list[str] = []
    eid = ev.get("event_id") or "?"
    p = f"{where}:{eid}"
    if not re.match(r"^[a-z0-9][a-z0-9-]{3,80}$", eid):
        errs.append(f"{p}: event_id must be kebab-case")
    for k in ("title", "body", "act"):
        if not str(ev.get(k) or "").strip():
            errs.append(f"{p}: {k} empty")
    d = str(ev.get("date") or "")
    if not DATE_RE.match(d):
        errs.append(f"{p}: date must be YYYY-MM-DD")
    elif not (WINDOW_START <= d <= today):
        errs.append(f"{p}: date {d} outside window {WINDOW_START}..{today}")
    ad = str(ev.get("act_date") or "")
    if ad and not DATE_RE.match(ad):
        errs.append(f"{p}: act_date must be YYYY-MM-DD or empty")
    if ad and d and DATE_RE.match(ad) and ad > d:
        errs.append(f"{p}: act_date after finding date")
    if ev.get("indicator") not in INDICATORS:
        errs.append(f"{p}: indicator {ev.get('indicator')!r} not in codebook")
    ft = ev.get("finding_type")
    if ft not in FINDING_SEVERITY:
        errs.append(f"{p}: finding_type {ft!r} invalid")
    elif ev.get("severity") != FINDING_SEVERITY[ft]:
        errs.append(f"{p}: severity {ev.get('severity')} != {FINDING_SEVERITY[ft]} required by finding_type {ft}")
    atts = ev.get("attributions") or []
    if not atts:
        errs.append(f"{p}: no attributions")
    seen = set()
    for a in atts:
        pid = a.get("party_id")
        if pid not in PARTIES:
            errs.append(f"{p}: party {pid!r} invalid")
        if pid in seen:
            errs.append(f"{p}: party {pid} attributed twice")
        seen.add(pid)
        if a.get("role") not in ROLES:
            errs.append(f"{p}: role {a.get('role')!r} invalid")
        if a.get("attribution") not in ATTRIBUTIONS:
            errs.append(f"{p}: attribution {a.get('attribution')!r} invalid")
        if a.get("lineage") not in LINEAGES:
            errs.append(f"{p}: lineage {a.get('lineage')!r} invalid")
        if not isinstance(a.get("power_only"), bool):
            errs.append(f"{p}: power_only must be true/false")
        if a.get("lineage") in ("predecessor", "person", "list") and not str(a.get("note") or "").strip():
            errs.append(f"{p}: lineage {a.get('lineage')} needs a note naming the predecessor/list/person")
        if a.get("attribution") == "party" and a.get("role") != "party_organization":
            errs.append(f"{p}: attribution 'party' requires role party_organization")
    for s in [ev.get("source") or {}] + list(ev.get("extra_sources") or []):
        url = str(s.get("url") or "")
        if not url.startswith("https://"):
            errs.append(f"{p}: source url must be https ({url!r})")
        elif not any(h in url.split("/")[2] for h in ALLOWED_HOSTS):
            errs.append(f"{p}: source host not in the official allow-list: {url.split('/')[2]}")
        q = str(s.get("quote") or "")
        if not q.strip():
            errs.append(f"{p}: quote empty")
        elif words(q) > 15:
            errs.append(f"{p}: quote has {words(q)} words (max 15)")
        if not DATE_RE.match(str(s.get("retrieved") or "")):
            errs.append(f"{p}: retrieved date missing")
    if any(k.startswith("_") for k in ev):
        errs.append(f"{p}: remove helper keys starting with '_'")
    return errs


def check_pending(x: dict, where: str) -> list[str]:
    errs = []
    p = f"{where}:pending:{x.get('pending_id')}"
    if x.get("party_id") not in PARTIES:
        errs.append(f"{p}: party {x.get('party_id')!r} invalid")
    if x.get("role") not in ROLES:
        errs.append(f"{p}: role {x.get('role')!r} invalid")
    if not DATE_RE.match(str(x.get("date") or "")):
        errs.append(f"{p}: date")
    for k in ("finding", "body", "appeal"):
        if not str(x.get(k) or "").strip():
            errs.append(f"{p}: {k} empty")
    s = x.get("source") or {}
    url = str(s.get("url") or "")
    if not url.startswith("https://") or not any(h in url.split("/")[2] for h in ALLOWED_HOSTS):
        errs.append(f"{p}: source url must be https on an official host ({url[:60]})")
    q = str(s.get("quote") or "")
    if not q.strip() or words(q) > 15:
        errs.append(f"{p}: quote empty or > 15 words")
    return errs


def check_census(c: dict, where: str) -> list[str]:
    errs = []
    rows = c.get("rows") or []
    if not c.get("family") or not c.get("scope") or not (c.get("list_source") or {}).get("url"):
        errs.append(f"{where}: census needs family, scope and list_source.url")
    if c.get("n_listed") != len(rows):
        errs.append(f"{where}: census n_listed {c.get('n_listed')} != {len(rows)} rows")
    if c.get("n_in_scope") != sum(1 for r in rows if r.get("in_scope")):
        errs.append(f"{where}: census n_in_scope does not match rows")
    for r in rows:
        if not r.get("ref") or not str(r.get("reason") or "").strip():
            errs.append(f"{where}: census row without ref/reason: {r}")
    return errs


def load_events(paths: list[Path]) -> list[tuple[str, dict]]:
    out = []
    for path in paths:
        doc = json.loads(path.read_text(encoding="utf-8"))
        for ev in doc.get("events") or []:
            if ev.get("_exclude"):
                continue  # dropped by the drafter with a reason; kept in the part file for the record
            out.append((path.name, ev))
    return out


def main(argv: list[str]) -> int:
    today = date.today().isoformat()
    if argv:
        paths = [Path(a) for a in argv]
    else:
        paths = sorted(PARTS_DIR.glob("events_*.json")) + sorted(PARTS_DIR.glob("pending_*.json"))
    errs: list[str] = []
    events = load_events(paths)
    ids: dict[str, str] = {}
    for path in paths:
        doc = json.loads(path.read_text(encoding="utf-8"))
        for x in doc.get("pending") or []:
            errs += check_pending(x, path.name)
        if doc.get("census"):
            errs += check_census(doc["census"], path.name)
    for where, ev in events:
        errs += check_event(ev, where, today)
        eid = ev.get("event_id")
        if eid in ids:
            errs.append(f"{where}:{eid}: duplicate event_id (also in {ids[eid]})")
        ids[eid] = where
    if not argv and SEED.exists():
        seed = json.loads(SEED.read_text(encoding="utf-8"))
        codebook = {i["id"] for i in seed.get("codebook", {}).get("indicators", [])}
        if codebook != INDICATORS:
            errs.append(f"seed codebook indicators {sorted(codebook)} != validator {sorted(INDICATORS)}")
        for ev in seed.get("system_findings") or []:
            if not str((ev.get("source") or {}).get("url") or ev.get("url") or "").startswith("https://"):
                errs.append(f"system:{ev.get('event_id')}: url")
    for e in errs:
        print("ERROR", e)
    print(f"{len(events)} events, {len(errs)} errors")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

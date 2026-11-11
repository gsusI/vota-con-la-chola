#!/usr/bin/env python3
"""Validate the democracy safeguard seed and the published /visualizaciones/democracia/ artifact.

Checks
- every safeguard file in etl/data/seeds/democracy_safeguards_v1.d/safeguards/: schema, classification in the three
  values, links present (http/https), ISO dates ordered, government ids known, peers DE/FR/IT/PT present;
- raw payloads: sha256 matches the manifest;
- published JSON (unless --seed-only): every series recomputed from the raw payloads equals what is published.

Usage: python3 scripts/validate_democracy_safeguards.py [--only id1,id2] [--seed-only] [--check-links]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import export_public_viz_democracy as exp  # noqa: E402

CLASSES = {"tercero_a_tiempo", "tercero_tarde", "buena_voluntad"}
PEER_CLASSES = CLASSES | {"no_aplica", "no_signal"}
KINDS = {"incumplimiento_declarado", "plazo_vencido", "tension", "remedio", "aval"}
POWERS = {"obliga", "anula", "sustituye", "automatica", "declara", "nadie"}
GROUPS = {"legislar", "nombramientos", "control", "justicia", "excepcion", "transparencia"}
PEERS = ("DEU", "FRA", "ITA", "PRT")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL = re.compile(r"^https?://\S+$")
PLACEHOLDER = re.compile(r"(TODO|TBD|…|\.\.\.|XXX)")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")


def check_sources(rep: Report, where: str, sources, required: bool = True) -> list[str]:
    urls = []
    if not isinstance(sources, list) or (required and not sources):
        rep.err(where, "sources must be a non-empty list")
        return urls
    for i, s in enumerate(sources):
        if not isinstance(s, dict) or not s.get("label") or not URL.match(str(s.get("url", ""))):
            rep.err(where, f"source {i} needs label and http(s) url")
        else:
            urls.append(s["url"])
    return urls


def check_date(rep: Report, where: str, value, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str) or not ISO.match(value):
        rep.err(where, f"bad ISO date {value!r}")


def text_ok(rep: Report, where: str, value) -> None:
    if not isinstance(value, str) or not value.strip():
        rep.err(where, "missing text")
    elif PLACEHOLDER.search(value):
        rep.err(where, f"placeholder left in text: {value[:60]!r}")


def validate_safeguard(rep: Report, doc: dict, gov_ids: set[str]) -> list[str]:
    sid = doc.get("id", "?")
    urls: list[str] = []
    for key in ("name", "obligated", "sanction", "classification_reason", "limits"):
        text_ok(rep, f"{sid}.{key}", doc.get(key))
    if doc.get("group") not in GROUPS:
        rep.err(sid, f"group {doc.get('group')!r} not in {sorted(GROUPS)}")
    rule = doc.get("rule") or {}
    text_ok(rep, f"{sid}.rule.text", rule.get("text"))
    if not rule.get("articles"):
        rep.err(sid, "rule.articles empty")
    if not URL.match(str(rule.get("url", ""))):
        rep.err(sid, "rule.url missing")
    else:
        urls.append(rule["url"])
    enforcer = doc.get("enforcer") or {}
    text_ok(rep, f"{sid}.enforcer.who", enforcer.get("who"))
    text_ok(rep, f"{sid}.enforcer.short", enforcer.get("short"))
    text_ok(rep, f"{sid}.sanction_short", doc.get("sanction_short"))
    if len(enforcer.get("short") or "") > 60 or len(doc.get("sanction_short") or "") > 70:
        rep.err(sid, "enforcer.short > 60 or sanction_short > 70 characters")
    if enforcer.get("power") not in POWERS:
        rep.err(sid, f"enforcer.power {enforcer.get('power')!r} not in {sorted(POWERS)}")
    if doc.get("classification") not in CLASSES:
        rep.err(sid, f"classification {doc.get('classification')!r} not in {sorted(CLASSES)}")
    delay = doc.get("remedy_delay") or {}
    if delay.get("days") is not None and not isinstance(delay.get("days"), int):
        rep.err(sid, "remedy_delay.days must be int or null")
    text_ok(rep, f"{sid}.remedy_delay.basis", delay.get("basis"))
    if delay.get("days") is not None:
        urls += check_sources(rep, f"{sid}.remedy_delay", delay.get("sources"))
    episodes = doc.get("episodes")
    if not isinstance(episodes, list):
        rep.err(sid, "episodes must be a list")
        episodes = []
    seen = set()
    for ep in episodes:
        eid = f"{sid}/{ep.get('id', '?')}"
        if ep.get("id") in seen:
            rep.err(eid, "duplicate episode id")
        seen.add(ep.get("id"))
        check_date(rep, eid + ".start", ep.get("start"))
        check_date(rep, eid + ".end", ep.get("end"), nullable=True)
        if ep.get("end") and ep.get("start") and ep["end"] < ep["start"]:
            rep.err(eid, "end before start")
        if ep.get("start", "") > exp.SNAPSHOT_LIMIT:
            rep.err(eid, "start after snapshot date")
        if ep.get("kind") not in KINDS:
            rep.err(eid, f"kind {ep.get('kind')!r} not in {sorted(KINDS)}")
        text_ok(rep, eid + ".summary", ep.get("summary"))
        ph = ep.get("power_holder") or {}
        if ph.get("government") is not None and ph.get("government") not in gov_ids:
            rep.err(eid, f"unknown government {ph.get('government')!r}")
        if ph.get("government") is not None and ep.get("start"):
            gov = exp.government_at(ep["start"], exp.load_seed()["governments"])
            # the act may precede a change of government by days (caretaker); allow a mismatch only if noted
            if gov and gov["id"] != ph["government"] and not ph.get("note"):
                rep.err(eid, f"government {ph['government']} but {gov['id']} governed on {ep['start']} (add a note if intended)")
        text_ok(rep, eid + ".power_holder.body", ph.get("body"))
        maj = ph.get("majority")
        if maj is not None:
            if maj.get("rule") not in ("3/5", "2/3") or not set(maj.get("chambers") or []) <= {"Congreso", "Senado"} or not maj.get("chambers"):
                rep.err(eid, "power_holder.majority needs rule 3/5|2/3 and chambers Congreso/Senado")
            if ph.get("indispensable_parties"):
                rep.err(eid, "with a qualified majority, indispensable parties are computed from seats.json: leave null")
        rem = ep.get("remedy")
        if rem is not None:
            check_date(rep, eid + ".remedy.date", rem.get("date"))
            check_date(rep, eid + ".remedy.act_date", rem.get("act_date"), nullable=True)
            if rem.get("act_date") and rem.get("date") and rem["date"] < rem["act_date"]:
                rep.err(eid, "remedy before act")
            text_ok(rep, eid + ".remedy.by", rem.get("by"))
        urls += check_sources(rep, eid, ep.get("sources"))
    peers = doc.get("peers") or {}
    for code in PEERS:
        peer = peers.get(code)
        if not isinstance(peer, dict):
            rep.err(sid, f"peer {code} missing")
            continue
        text_ok(rep, f"{sid}.peers.{code}.mechanism", peer.get("mechanism"))
        if peer.get("classification") not in PEER_CLASSES:
            rep.err(sid, f"peers.{code}.classification {peer.get('classification')!r}")
        if peer.get("classification") != "no_signal":
            urls += check_sources(rep, f"{sid}.peers.{code}", peer.get("sources"))
    for i, term in enumerate(doc.get("mandate_terms") or []):
        where = f"{sid}.mandate_terms[{i}]"
        for key in ("mandate_start", "mandate_end"):
            check_date(rep, f"{where}.{key}", term.get(key))
        check_date(rep, f"{where}.successor_took_office", term.get("successor_took_office"), nullable=True)
        if term.get("successor_took_office") and term.get("mandate_end") and term["successor_took_office"] < term["mandate_start"]:
            rep.err(where, "successor before mandate start")
        if term.get("mandate_end") and term.get("mandate_start") and term["mandate_end"] < term["mandate_start"]:
            rep.err(where, "mandate_end before mandate_start")
        urls += check_sources(rep, where, term.get("sources"))
    return urls


def validate_context(rep: Report, ids: set[str]) -> list[str]:
    path = exp.SEED_DIR / "context.json"
    if not path.exists():
        return []
    ctx = json.loads(path.read_text())
    urls: list[str] = []
    for key in ("title", "intro", "conclusion"):
        text_ok(rep, f"context.{key}", ctx.get(key))
    if not ctx.get("erosion"):
        rep.err("context", "erosion rows missing")
    for row in ctx.get("erosion") or []:
        where = f"context.erosion.{row.get('id')}"
        text_ok(rep, where + ".what", row.get("what"))
        for code in ("POL", "HUN"):
            text_ok(rep, f"{where}.{code}.text", (row.get(code) or {}).get("text"))
            urls += check_sources(rep, f"{where}.{code}", (row.get(code) or {}).get("sources"))
        esp = row.get("ESP") or {}
        text_ok(rep, where + ".ESP.text", esp.get("text"))
        if esp.get("safeguard") and esp["safeguard"] not in ids:
            rep.err(where, f"ESP.safeguard {esp['safeguard']!r} has no file")
    for i, rec in enumerate(ctx.get("recommendations_spain") or []):
        if not URL.match(str(rec.get("url", ""))) or not rec.get("text") or not isinstance(rec.get("year"), int):
            rep.err(f"context.recommendations_spain[{i}]", "needs year, text and url")
        else:
            urls.append(rec["url"])
    return urls


def check_links(urls: list[str]) -> list[str]:
    bad = []
    for url in sorted(set(urls)):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="GET")
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status >= 400:
                    bad.append(f"{resp.status} {url}")
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{type(exc).__name__}: {str(exc)[:60]} {url}")
    return bad


def validate_published(rep: Report) -> None:
    if not exp.OUT_JSON.exists():
        rep.err("published", f"{exp.OUT_JSON.relative_to(exp.REPO_ROOT)} missing")
        return
    published = json.loads(exp.OUT_JSON.read_text())
    rebuilt = json.loads(json.dumps(exp.build_payload(exp.load_seed()), ensure_ascii=False))
    for key in exp.REPRODUCIBLE_KEYS:
        if published.get(key) != rebuilt.get(key):
            rep.err("published", f"series {key!r} differs from the recomputation from raw payloads")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--seed-only", action="store_true")
    ap.add_argument("--check-links", action="store_true")
    ap.add_argument("--published", action="store_true", help="check only the reviewed safeguards (the ones the page publishes) and the artifact")
    args = ap.parse_args(argv)
    rep = Report()
    seed = exp.load_seed()
    gov_ids = {g["id"] for g in seed["governments"]}
    only = {x for x in args.only.split(",") if x}
    if args.published:
        only = set(seed.get("reviews", {}).get("verified", {})) | {"context"}
    urls: list[str] = []
    files = sorted(exp.SAFEGUARD_DIR.glob("*.json"))
    for path in files:
        doc = json.loads(path.read_text())
        if only and doc.get("id") not in only:
            continue
        if doc.get("id") != path.stem:
            rep.err(path.name, "id must equal file name")
        urls += validate_safeguard(rep, doc, gov_ids)
    ctx_ready = bool(json.loads((exp.SEED_DIR / "context.json").read_text()).get("erosion")) if (exp.SEED_DIR / "context.json").exists() else False
    if (not only and ctx_ready) or ("context" in only and (ctx_ready or not args.published)):
        urls += validate_context(rep, {p.stem for p in files})
    for name, entry in exp.load_manifest().items():
        try:
            exp.read_raw(name)
        except Exception as exc:  # noqa: BLE001
            rep.err(f"raw/{name}", str(exc))
    if (args.published or not only) and not args.seed_only:
        validate_published(rep)
    if args.check_links:
        for line in check_links(urls):
            rep.err("link", line)
    for line in rep.errors:
        print(line)
    print(f"{len(files) if not only else len(only)} safeguards checked, {len(set(urls))} links, {len(rep.errors)} errors")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())

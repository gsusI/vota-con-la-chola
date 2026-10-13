#!/usr/bin/env python3
"""Vote atlas: every Congreso roll-call vote of the legislature, placed on topic axes.

Pipeline (each step writes a reviewable file; the published exports never depend on a live search):

1. ``link-texts``: for every motion (173/…) and non-binding motion (162/…) voted in plenary — whole or
   point by point — find its expediente in the Congreso initiative listing, confirm it because the
   initiative page lists the very roll-call vote, and extract the literal dispositive text and its numbered
   points from the BOCG. Writes ``etl/data/seeds/vote_atlas_texts_v1.json``.
2. ``units``: one classification unit per contested, non-amendment vote (title, kind, the point text or the
   law bullets already published for the voting aid). Writes batches for the classifiers (people or agents),
   who place each vote on the axes of ``vote_atlas_axes_v1.json`` without seeing how parties voted.
3. ``scripts/export_vote_atlas.py`` aggregates party and deputy directions per axis.

Amendment votes (committee report amendments, Senate amendments, votos particulares) are kept for the
per-deputy record but not classified: the vote data only gives the amendment number, not its text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
import urllib.parse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.export_voting_aid_snapshot import DEFAULT_SEED, majority_choice, party_resolver  # noqa: E402
from scripts.voting_aid_motion_texts import (  # noqa: E402
    CONGRESO,
    DEFAULT_CACHE,
    DETAIL_URL,
    SEARCH_URL,
    _request,
    cached,
    choose_documents,
    fold,
    initiative_page,
    motion_document,
    motion_object,
    parse_initiative_page,
    similarity,
    vote_path,
    voted_terms,
)

TEXTS_SCHEMA_VERSION = "vote_atlas_texts_v1"
DEFAULT_TEXTS = BASE_DIR / "etl/data/seeds/vote_atlas_texts_v1.json"
DEFAULT_AXES = BASE_DIR / "etl/data/seeds/vote_atlas_axes_v1.json"
DEFAULT_BULLETS = BASE_DIR / "ui/site/public/citizen/data/voting_aid_vote_bullets_v1.json"
DEFAULT_MOTION_SEED = BASE_DIR / "etl/data/seeds/voting_aid_motion_texts_v1.json"

# Kinds whose content can be read from the title, the motion points or the law text.
CLASSIFIABLE_KINDS = {
    "toma", "totalidad", "final", "rdl", "pnl", "pnl_punto", "mocion", "mocion_punto",
    "convenio", "comision_investigacion", "presupuesto", "reforma_reglamento", "veto_senado",
}
AMENDMENT_KINDS = {"enmienda", "enmienda_senado", "voto_particular"}
KIND_LABELS = {
    "toma": "Toma en consideración de una proposición de ley",
    "totalidad": "Enmienda a la totalidad",
    "final": "Votación final de una ley",
    "rdl": "Convalidación de un decreto ley",
    "rdl_tramitacion": "Tramitar un decreto ley como proyecto de ley",
    "pnl": "Proposición no de ley",
    "pnl_punto": "Proposición no de ley (votación por puntos)",
    "mocion": "Moción",
    "mocion_punto": "Moción (votación por puntos)",
    "enmienda": "Enmienda a una ley",
    "enmienda_senado": "Enmienda del Senado",
    "voto_particular": "Voto particular",
    "veto_senado": "Veto del Senado",
    "convenio": "Convenio internacional",
    "comision_investigacion": "Comisión de investigación",
    "presupuesto": "Estabilidad presupuestaria y cuentas",
    "reforma_reglamento": "Reglamento del Congreso",
    "procedimiento": "Trámite parlamentario",
    "otro": "Otra votación",
}


def clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def vote_kind(title: str, subgroup_title: str, subgroup_text: str, expediente_text: str) -> str:
    """Deterministic kind from the official vote headings (no semantics)."""
    t, sgt, sgx, exp = fold(title), fold(subgroup_title), fold(subgroup_text), fold(expediente_text)
    is_point = "punto" in sgt or "guion" in sgx or "resto de la mocion" in sgx or sgx.startswith("punto")
    amendment = ("enmienda" in sgt or "enmienda" in sgx) and "totalidad" not in sgt and "totalidad" not in sgx
    if "votos particulares" in sgt or "voto particular" in sgt:
        return "voto_particular"
    if "correcciones tecnicas" in sgt or "avocacion" in sgt:
        return "procedimiento"
    if t.startswith("presupuestos generales del estado"):
        return "enmienda" if amendment else "final"
    if "correccion tecnica" in sgt:
        return "procedimiento"
    if t.startswith("enmiendas del senado"):
        return "enmienda_senado" if amendment or sgt or sgx else "enmienda_senado"
    if t.startswith("veto del senado"):
        return "veto_senado"
    if "proposiciones no de ley" in t and "mociones" not in t:
        return "pnl_punto" if is_point else "pnl"
    if t.startswith("mociones consecuencia"):
        return "mocion_punto" if is_point else "mocion"
    if t.startswith("votacion de las proposiciones no de ley y mociones"):
        base = "mocion" if exp.startswith("mocion") else "pnl"
        return f"{base}_punto" if is_point else base
    if "convalidacion o derogacion" in t:
        return "rdl_tramitacion" if exp.startswith("tramitacion como proyecto de ley") else "rdl"
    if "comisiones de investigacion" in t:
        return "comision_investigacion" if t.startswith("solicitudes de creacion") else "procedimiento"
    if "estabilidad presupuestaria" in t or "plan de reequilibrio" in t or "cuenta general" in t:
        return "presupuesto"
    if "convenios internacionales" in t:
        return "convenio"
    if "debates de totalidad" in t or t.startswith("debate de totalidad"):
        if "avocacion" in sgt or "avocacion" in sgx:
            return "procedimiento"
        return "totalidad"
    if t.startswith("toma en consideracion"):
        return "reforma_reglamento" if "reglamento" in t else "toma"
    if amendment:
        return "enmienda"
    if (
        "votacion de conjunto" in exp or "votacion de conjunto" in sgt or "votacion del dictamen" in sgt or "votacion del nuevo dictamen" in sgt
        or "votacion de totalidad" in sgt
    ):
        return "reforma_reglamento" if "reglamento del congreso" in exp and "ley" not in exp[:40] else "final"
    if t.startswith("dictamenes de comisiones sobre iniciativas legislativas") and not sgt:
        return "final"
    if "lectura unica" in t or "tramitacion directa" in t:
        return "procedimiento"
    if any(k in t for k in ("subcomisiones", "propuestas de creacion", "prorroga", "estatuto de los diputados", "comision del estatuto", "avocacion", "informes de subcomisiones")):
        return "procedimiento"
    if "reglamento del congreso" in t:
        return "reforma_reglamento"
    return "otro"


POINT_NUM_RE = re.compile(r"\b(\d{1,2})\b")
ORDINALS = {"primer": 1, "segundo": 2, "tercer": 3, "cuarto": 4, "quinto": 5, "sexto": 6, "septimo": 7, "octavo": 8, "noveno": 9, "decimo": 10}


def point_numbers(subgroup_text: str) -> list[int]:
    s = fold(subgroup_text)
    if "resto" in s:
        return []
    nums = [int(n) for n in POINT_NUM_RE.findall(s)]
    if not nums:
        nums = [v for k, v in ORDINALS.items() if re.search(rf"\b{k}o?\b", s)]
    return nums


def motion_key(expediente_text: str) -> str:
    first = clean(str(expediente_text or "").split("\n")[0])
    return hashlib.sha1(fold(first).encode("utf-8")).hexdigest()[:16]


LEG_ROMAN = {"14": "XIV", "15": "XV"}
CURRENT_LEGISLATURE = "15"
# XIV groups that vote as one party; the Plural and Mixto groups mixed several parties, so no majority is used.
XIV_COHERENT_GROUPS = {"GS", "GP", "GVOX", "GR", "GEH Bildu", "GV (EAJ-PNV)", "GCUP-EC-GC", "GCs"}
# XIV groups that correspond to one ballot party of today (for the party chips on XIV votes).
XIV_GROUP_PARTY = {"GS": "psoe", "GP": "pp", "GVOX": "vox", "GR": "erc", "GEH Bildu": "bildu", "GV (EAJ-PNV)": "pnv"}


def text_key(legislature: str, expediente_text: str) -> str:
    """Motion text key; earlier legislatures are prefixed so equal titles never collide."""
    key = motion_key(expediente_text)
    return key if str(legislature) == CURRENT_LEGISLATURE else f"{legislature}:{key}"


def affiliation_resolver(seed: dict[str, Any], legislature: str):
    """Who a deputy votes with: the ballot party in the current legislature, the parliamentary group before."""
    if str(legislature) == CURRENT_LEGISLATURE:
        return party_resolver(seed)
    return lambda _name, group: f"g{legislature}:{group}" if group in XIV_COHERENT_GROUPS else None


def load_congreso_events(conn: sqlite3.Connection, legislature: str = "15", since: str | None = None) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT vote_event_id, legislature, session_number, vote_number, vote_date, title, expediente_text,
               subgroup_title, subgroup_text, totals_yes, totals_no, totals_abstain, totals_no_vote, source_url
        FROM parl_vote_events
        WHERE source_id = 'congreso_votaciones' AND legislature = ? AND vote_date >= ?
        ORDER BY vote_date, session_number, vote_number, vote_event_id
        """,
        (legislature, since or ""),
    ).fetchall()
    out = []
    for r in rows:
        ev = dict(zip(
            ("vote_event_id", "legislature", "session", "number", "vote_date", "title", "expediente_text",
             "subgroup_title", "subgroup_text", "yes", "no", "abstain", "no_vote", "source_url"), r))
        ev["kind"] = vote_kind(ev["title"], ev["subgroup_title"], ev["subgroup_text"], ev["expediente_text"])
        out.append(ev)
    return out


def party_majorities(conn: sqlite3.Connection, seed: dict[str, Any], vote_ids: list[str], legislature: str = CURRENT_LEGISLATURE) -> dict[str, dict[str, str | None]]:
    resolve = affiliation_resolver(seed, legislature)
    tallies: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    ids = set(vote_ids)
    for vid, name, group, choice in conn.execute(
        """
        SELECT m.vote_event_id, m.member_name, m.group_code, m.vote_choice
        FROM parl_vote_member_votes m JOIN parl_vote_events e USING (vote_event_id)
        WHERE e.source_id = 'congreso_votaciones'
        """
    ):
        if vid not in ids:
            continue
        pid = resolve(str(name or ""), str(group or ""))
        if pid:
            tallies[vid][pid][str(choice or "")] += 1
    return {vid: {pid: majority_choice(c) for pid, c in tallies[vid].items()} for vid in vote_ids}


def contested(majorities: dict[str, str | None]) -> bool:
    """At least one party voted Sí and another No (by majority of its deputies)."""
    values = set(majorities.values())
    return "Sí" in values and "No" in values


# ---------------------------------------------------------------------------
# Step 1: link motion texts.

LIST_HEADERS = {
    "X-Requested-With": "XMLHttpRequest", "Origin": CONGRESO, "Referer": f"{CONGRESO}/es/busqueda-de-iniciativas",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def list_type_fresh(tipo: str, cache_dir: Path, stamp: str, timeout: int, sleep: float, legislature: str = CURRENT_LEGISLATURE) -> list[dict[str, Any]]:
    """Every initiative of a type in a legislature; cached per listing date so later runs see new initiatives."""
    out: list[dict[str, Any]] = []
    page, total = 1, None
    leg_tag = "" if legislature == CURRENT_LEGISLATURE else f"L{legislature}_"
    while total is None or len(out) < total:
        path = cache_dir / "initiatives" / f"list_{tipo}_{leg_tag}{stamp}_p{page:03d}.json"

        def get(page=page) -> bytes:
            data = urllib.parse.urlencode({"_iniciativas_legislatura": legislature, "_iniciativas_tipo": tipo, "_iniciativas_paginaActual": str(page)}).encode()
            raw = _request(SEARCH_URL, data, LIST_HEADERS, timeout)
            time.sleep(sleep)
            return raw

        payload = json.loads(cached(path, get))
        total = int(payload.get("iniciativas_encontradas") or 0)
        items = list((payload.get("lista_iniciativas") or {}).values())
        if not items:
            break
        out.extend(items)
        page += 1
    return out


GROUP_ALIASES = {
    "popular": "popular", "vox": "vox", "socialista": "socialista", "sumar": "sumar", "republicano": "republicano",
    "junts": "junts", "vasco": "vasco", "bildu": "bildu", "mixto": "mixto",
}


def author_tokens(text: str) -> set[str]:
    f = fold(text)
    return {v for k, v in GROUP_ALIASES.items() if k in f}


def proposer_text(expediente_text: str) -> str:
    first = clean(str(expediente_text or "").split("\n")[0])
    m = re.search(r"\b(?:del|de los)\s+(Grupos? Parlamentari[oa]s?.*?)(?:,\s+(?:sobre|relativa|relativo|para|de |por |en |acerca|con |ante |que )|$)", first)
    return m.group(1) if m else ""


def rank_candidates(obj: str, proposer: str, listing: list[dict[str, Any]], top: int = 4) -> list[str]:
    want = author_tokens(proposer)

    def score(item: dict[str, Any]) -> float:
        s = similarity(obj, motion_object(item.get("titulo", "")) or item.get("titulo", ""))
        if want and author_tokens(item.get("autor", "")) & want:
            s += 0.15
        return s

    ranked = sorted(listing, key=lambda x: -score(x))
    return [x["id_iniciativa"] for x in ranked[:top] if score(x) > 0.15]


def detail_url(exp: str, legislature: str) -> str:
    url = DETAIL_URL.format(exp=urllib.parse.quote(exp, safe=""))
    return url.replace("_iniciativas_legislatura=XV", f"_iniciativas_legislatura={LEG_ROMAN[legislature]}")


def leg_initiative_page(exp: str, legislature: str, cache_dir: Path, timeout: int, refresh: bool = False) -> str:
    """Initiative page (cached). Earlier legislatures get their own cache names: expediente numbers repeat."""
    if legislature == CURRENT_LEGISLATURE and not refresh:
        return initiative_page(exp, cache_dir, timeout)
    prefix = "" if legislature == CURRENT_LEGISLATURE else f"L{legislature}_"
    path = cache_dir / "initiatives" / f"{prefix}{exp.replace('/', '_')}.html"
    if path.exists() and path.stat().st_size > 0 and not refresh:
        return path.read_text(encoding="utf-8", errors="replace")
    data = _request(detail_url(exp, legislature), timeout=timeout)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data.decode("utf-8", errors="replace")


def link_group(group: dict[str, Any], listings: dict[str, list[dict[str, Any]]], cache_dir: Path, timeout: int,
               previous: dict[str, Any] | None, legislature: str = CURRENT_LEGISLATURE) -> dict[str, Any]:
    kind = group["base_kind"]
    listing = listings["173" if kind == "mocion" else "162"]
    obj = motion_object(group["expediente_text"])
    candidates = [previous["expediente"]] if previous and previous.get("expediente") else []
    candidates += [c for c in rank_candidates(obj, proposer_text(group["expediente_text"]), listing) if c not in candidates]
    wanted = {p for p in (vote_path(u) for u in group["source_urls"]) if p}
    for refresh in (False, True):
        for exp in candidates:
            html = leg_initiative_page(exp, legislature, cache_dir, timeout, refresh=refresh)
            page = parse_initiative_page(html)
            if wanted & set(page["vote_paths"]):
                docs = choose_documents(page["boletines"])
                return {
                    "expediente": exp, "match": "vote_listed_on_initiative_page", "object": obj,
                    "initiative_url": detail_url(exp, legislature), "boletines": page["boletines"],
                    **{f"{k}_doc": d for k, d in docs.items()},
                }
    return {"expediente": None, "match": "not_found", "object": obj, "candidates": candidates}


def extract_points(entry: dict[str, Any], cache_dir: Path, *, by_points: bool, approved: bool, terms: str) -> dict[str, Any]:
    """Literal dispositive text. Point-by-point votes refer to the numbering of the text that was put to the
    vote, so they use the original publication (the approval notice renumbers the surviving points)."""
    doc_entry = {**entry, "approved": approved and not by_points, "voted_terms": terms}
    if by_points:
        doc_entry["approval_doc"] = None
    doc = motion_document(doc_entry, cache_dir)
    return {k: doc[k] for k in ("url", "sha256", "bocg", "text_status", "text_status_label", "voted_terms", "amendments_url", "intro", "points")}


def target_groups(events: list[dict[str, Any]], legislature: str = CURRENT_LEGISLATURE) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for ev in events:
        if ev["kind"] not in {"pnl", "pnl_punto", "mocion", "mocion_punto"}:
            continue
        key = text_key(legislature, ev["expediente_text"])
        g = groups.setdefault(key, {
            "base_kind": ev["kind"].split("_")[0], "expediente_text": ev["expediente_text"], "vote_ids": [],
            "source_urls": [], "by_points": False, "approved": False, "terms": voted_terms(ev["expediente_text"]),
        })
        g["vote_ids"].append(ev["vote_event_id"])
        g["source_urls"].append(ev["source_url"] or ev["vote_event_id"][4:])
        g["by_points"] = g["by_points"] or ev["kind"].endswith("_punto")
        g["approved"] = g["approved"] or (ev["yes"] or 0) > (ev["no"] or 0)
    return groups


def cmd_link_texts(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    events = load_congreso_events(conn, args.legislature, args.since)
    groups = target_groups(events, args.legislature)
    cache_dir = Path(args.cache_dir)
    stamp = args.listing_date or datetime.now(timezone.utc).strftime("%Y%m%d")
    listings = {t: list_type_fresh(t, cache_dir, stamp, args.timeout, args.sleep, args.legislature) for t in ("162", "173")}
    print(f"listings: 162={len(listings['162'])} 173={len(listings['173'])} groups={len(groups)}", flush=True)
    seed_path = Path(args.out)
    previous = json.loads(seed_path.read_text(encoding="utf-8")).get("motions", {}) if seed_path.exists() else {}
    # Reuse expedientes confirmed by the voting aid's own motion seed.
    legacy = json.loads(Path(args.motion_seed).read_text(encoding="utf-8")).get("votes", {}) if Path(args.motion_seed).exists() else {}
    hints: dict[str, dict[str, Any]] = {}
    for key, g in (groups.items() if args.legislature == CURRENT_LEGISLATURE else []):
        for vid in g["vote_ids"]:
            exp = (legacy.get(vid) or {}).get("expediente")
            if exp:
                hints[key] = {"expediente": exp}
                break

    def work(item: tuple[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
        key, g = item
        prev = previous.get(key) if (previous.get(key) or {}).get("expediente") else hints.get(key)
        try:
            r = link_group(g, listings, cache_dir, args.timeout, prev, args.legislature)
            if r.get("expediente"):
                try:
                    r["text"] = extract_points(r, cache_dir, by_points=g["by_points"], approved=g["approved"], terms=g["terms"])
                except Exception as exc:  # noqa: BLE001 - keep the link even when extraction fails
                    r["text_error"] = f"{type(exc).__name__}: {exc}"[:240]
        except Exception as exc:  # noqa: BLE001
            r = {"expediente": None, "match": "error", "error": f"{type(exc).__name__}: {exc}"[:240]}
        r.update({"legislature": args.legislature, "kind": g["base_kind"], "by_points": g["by_points"], "vote_ids": sorted(g["vote_ids"]),
                  "title": clean(str(g["expediente_text"]).split("\n")[0])})
        return key, r

    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for key, r in ex.map(work, sorted(groups.items())):
            results[key] = r
            status = "text" if r.get("text") else (r.get("text_error") and "noext") or r["match"]
            print(f"{r['kind']:6} {r.get('expediente') or '-':12} {status} {r['title'][:70]}", flush=True)
    # Entries of other legislatures (or not re-linked now) are kept: one seed for every legislature.
    merged = {**previous, **results}
    payload = {
        "meta": {
            "schema_version": TEXTS_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "listing_date": stamp,
            "method": (
                "Expediente elegido entre los listados de PNL (162) y mociones (173) de su legislatura por similitud de título y "
                "grupo autor, y confirmado porque la ficha de la iniciativa enlaza la misma votación nominal. Texto "
                "literal de la parte dispositiva extraído del BOCG serie D: el aprobado si la votación fue conjunta y "
                "salió adelante; el original si se votó por puntos (la numeración de los puntos es la del texto votado)."
            ),
            "motions": len(merged),
            "linked": sum(1 for r in merged.values() if r.get("expediente")),
            "with_text": sum(1 for r in merged.values() if r.get("text")),
            "by_legislature": dict(sorted(Counter(str(r.get("legislature") or CURRENT_LEGISLATURE) for r in merged.values()).items())),
        },
        "motions": dict(sorted(merged.items())),
    }
    seed_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    m = payload["meta"]
    print(f"OK texts -> {seed_path} (motions={m['motions']} linked={m['linked']} with_text={m['with_text']})")
    return 0


# ---------------------------------------------------------------------------
# Step 2: classification units.

def point_text(text: dict[str, Any] | None, subgroup_text: str) -> tuple[list[dict[str, str]], str]:
    """Points of the motion that this vote covers; ('', reason) when they cannot be located."""
    if not text:
        return [], "sin_texto_mocion"
    points = text.get("points") or []
    nums = point_numbers(subgroup_text)
    if "resto" in fold(subgroup_text):
        return [], "resto_de_la_mocion"
    if not nums:
        return [], "punto_no_identificado"
    by_n = {str(p.get("n")).strip(".) "): p for p in points}
    found = [by_n[str(n)] for n in nums if str(n) in by_n]
    if len(found) != len(nums):
        return found, "punto_no_encontrado"
    return found, ""


def build_units(events: list[dict[str, Any]], majorities: dict[str, dict[str, str | None]], texts: dict[str, Any],
                bullets: dict[str, Any], legislature: str = CURRENT_LEGISLATURE) -> list[dict[str, Any]]:
    units = []
    for ev in events:
        if ev["kind"] not in CLASSIFIABLE_KINDS or not contested(majorities.get(ev["vote_event_id"], {})):
            continue
        unit: dict[str, Any] = {
            "vote_event_id": ev["vote_event_id"],
            "vote_date": ev["vote_date"],
            "legislature": ev["legislature"],
            "kind": ev["kind"],
            "kind_label": KIND_LABELS[ev["kind"]],
            "title": clean(ev["expediente_text"]),
            "subgroup": clean(" ".join(x for x in (ev["subgroup_title"], ev["subgroup_text"]) if x)),
            "result": "aprobada" if (ev["yes"] or 0) > (ev["no"] or 0) else "rechazada",
        }
        if ev["kind"] in {"pnl", "pnl_punto", "mocion", "mocion_punto"}:
            entry = texts.get(text_key(legislature, ev["expediente_text"])) or {}
            text = entry.get("text")
            if text:
                unit["text_source"] = {"url": text["url"], "bocg": text["bocg"], "text_status": text["text_status"]}
                unit["intro"] = text.get("intro")
            if ev["kind"].endswith("_punto"):
                pts, issue = point_text(text, ev["subgroup_text"] or "")
                unit["points"] = [{"n": p["n"], "text": p["text"][:1800]} for p in pts]
                if issue:
                    unit["text_issue"] = issue
                if text:
                    unit["other_points"] = [f"{p['n']}. {p['text'][:220]}" for p in text.get("points") or [] if p not in pts][:20]
            elif text:
                unit["points"] = [{"n": p["n"], "text": p["text"][:900]} for p in (text.get("points") or [])][:25]
            else:
                unit["text_issue"] = "sin_texto_mocion"
        else:
            b = (bullets.get(ev["vote_event_id"]) or {}).get("bullets") or []
            if b:
                unit["law_bullets"] = [x.get("text") for x in b]
        units.append(unit)
    return units


def cmd_units(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    events = load_congreso_events(conn, args.legislature, args.since)
    majorities = party_majorities(conn, seed, [e["vote_event_id"] for e in events], args.legislature)
    texts = json.loads(Path(args.texts).read_text(encoding="utf-8")).get("motions", {}) if Path(args.texts).exists() else {}
    bullets = json.loads(Path(args.bullets).read_text(encoding="utf-8")).get("by_vote", {}) if Path(args.bullets).exists() else {}
    units = build_units(events, majorities, texts, bullets, args.legislature)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Batches keep a motion's points together so one reader sees the whole motion.
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for u in units:
        by_key[motion_key(u["title"])].append(u)
    batches: list[list[dict[str, Any]]] = [[]]
    for key in sorted(by_key, key=lambda k: by_key[k][0]["vote_date"]):
        if batches[-1] and len(batches[-1]) + len(by_key[key]) > args.batch_size:
            batches.append([])
        batches[-1].extend(by_key[key])
    for i, batch in enumerate(batches, 1):
        prefix = "" if args.legislature == CURRENT_LEGISLATURE else f"l{args.legislature}_"
        (out_dir / f"batch_{prefix}{i:03d}.json").write_text(json.dumps(batch, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    kinds = Counter(e["kind"] for e in events)
    issues = Counter(u.get("text_issue", "ok") for u in units)
    print(json.dumps({"events": len(events), "kinds": dict(kinds.most_common()), "units": len(units),
                      "batches": len(batches), "text_issues": dict(issues)}, ensure_ascii=False))
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    """Merge classifier outputs into the versioned seed; every unit must be covered exactly once."""
    units = {u["vote_event_id"]: u for d in args.units_dir for f in sorted(Path(d).glob("batch_*.json")) for u in json.loads(f.read_text(encoding="utf-8"))}
    merged: dict[str, Any] = {}
    classifiers: set[str] = set()
    for f in sorted(p for d in args.classified_dir for p in Path(d).glob("batch_*.out.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        classifiers.add(str(doc.get("classifier") or f.stem))
        for item in doc.get("items") or []:
            vid = item.get("vote_event_id")
            if vid not in units:
                print(f"ERROR: {f.name}: votación desconocida {vid}", file=sys.stderr)
                return 2
            if vid in merged:
                print(f"ERROR: {f.name}: votación repetida {vid}", file=sys.stderr)
                return 2
            merged[vid] = {
                "axes": [{k: a.get(k) for k in ("axis_id", "yes_pushes", "confidence")} for a in item.get("axes") or []],
                "null_reason": None if item.get("axes") else item.get("null_reason"),
                "summary_yes": clean(item.get("summary_yes")),
                **({"note": clean(item["note"])} if clean(item.get("note")) else {}),
                "classifier": str(doc.get("classifier") or f.stem),
            }
    missing = sorted(set(units) - set(merged))
    if missing and not args.allow_missing:
        print(f"ERROR: {len(missing)} votaciones sin clasificar, p. ej. {missing[:2]}", file=sys.stderr)
        return 3
    previous_review = (json.loads(Path(args.out).read_text(encoding="utf-8")).get("review") or {}) if Path(args.out).exists() else {}
    payload = {
        "schema_version": "vote_atlas_classifications_v1",
        "review": {
            # Quality checks measured on earlier merges stay attached to the seed.
            **{k: previous_review[k] for k in ("qa", "agreement", "qa_by_legislature") if k in previous_review},
            "status": "agent_classified",
            "classified_by": sorted(classifiers),
            "model": args.model,
            "prompt": "docs/etl/sprints/VOTE-ATLAS-20261013/prompts/clasificar-votaciones.md",
            "classified_at": datetime.now(timezone.utc).date().isoformat(),
            "human_reviewed": False,
            "note": "Clasificación con IA por lotes, sin ver los votos de los partidos; pendiente de revisión humana.",
        },
        "votes": dict(sorted(merged.items())),
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    axes = Counter(a["axis_id"] for v in merged.values() for a in v["axes"])
    nulls = Counter(v["null_reason"] for v in merged.values() if not v["axes"])
    print(f"OK merged -> {args.out} (votes={len(merged)} missing={len(missing)} with_axis={sum(1 for v in merged.values() if v['axes'])} nulls={dict(nulls)})")
    print("axes:", dict(axes.most_common()))
    return 0


def agreement(main: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """Agreement between the main classification and an independent second pass on the same votes."""
    c: Counter = Counter()
    disagreements = []
    for vid, b in second.items():
        a = main.get(vid)
        if not a:
            continue
        c["n"] += 1
        ax_a = {x["axis_id"]: x["yes_pushes"] for x in a.get("axes") or []}
        ax_b = {x["axis_id"]: x["yes_pushes"] for x in b.get("axes") or []}
        if bool(ax_a) == bool(ax_b):
            c["same_has_axis"] += 1
        if ax_a and ax_b:
            c["both_axis"] += 1
            pa, pb = a["axes"][0]["axis_id"], b["axes"][0]["axis_id"]
            c["same_primary"] += pa == pb
            shared = set(ax_a) & set(ax_b)
            if shared:
                c["overlap"] += 1
                c["overlap_same_sign"] += all(ax_a[k] == ax_b[k] for k in shared)
                if any(ax_a[k] != ax_b[k] for k in shared):
                    disagreements.append({"vote_event_id": vid, "type": "sign", "main": a["axes"], "second": b["axes"]})
            else:
                disagreements.append({"vote_event_id": vid, "type": "axis", "main": a["axes"], "second": b["axes"]})
        # Votes that count in the scores (primary axis, high/medium confidence in the main pass).
        if ax_a and a["axes"][0]["confidence"] in ("alta", "media"):
            c["scored"] += 1
            k = a["axes"][0]["axis_id"]
            if k in ax_b:
                c["scored_axis_found"] += 1
                c["scored_same_sign"] += ax_b[k] == ax_a[k]
    rate = lambda num, den: round(c[num] / c[den], 3) if c[den] else None  # noqa: E731
    return {
        "votes_compared": c["n"],
        "same_has_axis": rate("same_has_axis", "n"),
        "same_primary_axis": rate("same_primary", "both_axis"),
        "axis_overlap": rate("overlap", "both_axis"),
        "same_sign_when_axis_shared": rate("overlap_same_sign", "overlap"),
        "scored_primary_axis_found_in_second": rate("scored_axis_found", "scored"),
        "scored_primary_same_sign": rate("scored_same_sign", "scored_axis_found"),
        "counts": dict(c),
        "disagreements": disagreements,
    }


def cmd_qa(args: argparse.Namespace) -> int:
    main_cls = json.loads(Path(args.classifications).read_text(encoding="utf-8"))["votes"]
    second: dict[str, Any] = {}
    for f in sorted(Path(args.qa_dir).glob("*.out.json")):
        for item in json.loads(f.read_text(encoding="utf-8")).get("items") or []:
            second[item["vote_event_id"]] = item
    result = {"generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
              "method": f"Muestra aleatoria (semilla {args.sample_seed}) reclasificada por otros agentes sin ver la primera clasificación.",
              **agreement(main_cls, second)}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("disagreements",)}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    lt = sub.add_parser("link-texts", help="Enlazar el texto BOCG de las PNL y mociones votadas (red, con caché)")
    lt.add_argument("--db", required=True)
    lt.add_argument("--legislature", default="15")
    lt.add_argument("--since", help="Solo votaciones desde esta fecha (YYYY-MM-DD)")
    lt.add_argument("--out", default=str(DEFAULT_TEXTS))
    lt.add_argument("--motion-seed", default=str(DEFAULT_MOTION_SEED))
    lt.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    lt.add_argument("--listing-date", help="Fecha del listado en caché (YYYYMMDD); por defecto hoy")
    lt.add_argument("--workers", type=int, default=4)
    lt.add_argument("--timeout", type=int, default=90)
    lt.add_argument("--sleep", type=float, default=0.3)
    un = sub.add_parser("units", help="Escribir lotes de votaciones para clasificar")
    un.add_argument("--db", required=True)
    un.add_argument("--legislature", default="15")
    un.add_argument("--since", help="Solo votaciones desde esta fecha (YYYY-MM-DD)")
    un.add_argument("--seed", default=str(DEFAULT_SEED))
    un.add_argument("--texts", default=str(DEFAULT_TEXTS))
    un.add_argument("--bullets", default=str(DEFAULT_BULLETS))
    un.add_argument("--out-dir", required=True)
    un.add_argument("--batch-size", type=int, default=45)
    mg = sub.add_parser("merge", help="Unir las clasificaciones de los lotes en la semilla versionada")
    mg.add_argument("--units-dir", required=True, nargs="+")
    mg.add_argument("--classified-dir", required=True, nargs="+")
    mg.add_argument("--out", default=str(BASE_DIR / "etl/data/seeds/vote_atlas_classifications_v1.json"))
    mg.add_argument("--model", default="claude-opus-5-5")
    mg.add_argument("--allow-missing", action="store_true")
    qa = sub.add_parser("qa", help="Medir el acuerdo con una segunda clasificación independiente")
    qa.add_argument("--classifications", default=str(BASE_DIR / "etl/data/seeds/vote_atlas_classifications_v1.json"))
    qa.add_argument("--qa-dir", required=True)
    qa.add_argument("--out", required=True)
    qa.add_argument("--sample-seed", default="20261013", help="Semilla con la que se sacó la muestra (se anota en la evidencia)")
    args = parser.parse_args(argv)
    return {"link-texts": cmd_link_texts, "units": cmd_units, "merge": cmd_merge, "qa": cmd_qa}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())

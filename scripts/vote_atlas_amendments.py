#!/usr/bin/env python3
"""Amendment votes of the vote atlas: find the official text of every amendment put to a roll-call vote.

The vote data only says "Enmienda 327." or "Enmiendas al artículo 13". This step:

1. ``link``: for every bill with contested amendment votes, finds its expediente in the Congreso initiative
   listings (types 121/122, plus Rules and Statute reforms) and confirms it because the initiative page lists the
   very roll-call votes. Keeps the BOCG documents: amendments ("ENMIENDA NÚM. N"), Senate amendments (mensaje
   motivado) and committee report (votos particulares). Writes ``etl/data/seeds/vote_atlas_amendment_docs_v1.json``
   with, per vote, how its text was resolved.
2. ``units``: classification batches with the literal amendment text (same format as ``vote_atlas.py units``).

Resolution of each vote (``resolution``):
- ``numeros``: amendments by number (ranges expanded) found in the BOCG amendment documents;
- ``transaccional``: a transactional amendment, whose own text is not in the BOCG: the amendments it settles;
- ``resto``: "Resto de las enmiendas" of a group: that group's amendments to the bill not voted separately;
- ``senado``: the part of the Senate's mensaje motivado about the precept named in the vote;
- ``voto_particular``: the committee report section with the group's voto particular;
- ``sin_texto``: none of the above could be located (left unclassified, never guessed).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.export_voting_aid_snapshot import DEFAULT_SEED  # noqa: E402
from scripts.vote_atlas import (  # noqa: E402
    AMENDMENT_KINDS,
    CURRENT_LEGISLATURE,
    DEFAULT_BULLETS,
    KIND_LABELS,
    clean,
    contested,
    fold,
    leg_initiative_page,
    list_type_fresh,
    load_congreso_events,
    motion_key,
    party_majorities,
    similarity,
)
from scripts.voting_aid_motion_texts import DEFAULT_CACHE, fetch_pdf, parse_initiative_page, vote_path  # noqa: E402

DOCS_SCHEMA_VERSION = "vote_atlas_amendment_docs_v1"
DEFAULT_DOCS = BASE_DIR / "etl/data/seeds/vote_atlas_amendment_docs_v1.json"
LAW_TYPES = ("121", "122", "410", "127", "125", "120")
MAX_TEXT = 2600

# ---------------------------------------------------------------------------
# Linking bills.

LAW_PREFIX_RE = re.compile(
    r"^(?:Votaci[óo]n de conjunto(?: del texto)?(?: de la| del)?\s+)?(?:Proyecto de Ley(?: Org[áa]nica)?|Proposici[óo]n de Ley(?: Org[áa]nica)?|"
    r"Proposici[óo]n de reforma(?: del Reglamento del Congreso(?: de los Diputados)?)?)\s*",
    re.I,
)


def law_object(expediente_text: str) -> str:
    first = clean(str(expediente_text or "").split("\n")[0])
    first = re.sub(r"\s*\(corresponde a[^)]*\)", "", first, flags=re.I)
    first = re.sub(r"^(?:del|de los)\s+Grupos? Parlamentari[oa]s?.*?,\s+", "", LAW_PREFIX_RE.sub("", first), flags=re.I)
    return first.strip(" .")


def is_budget(ev: dict[str, Any]) -> bool:
    return fold(ev["title"]).startswith("presupuestos generales del estado")


def law_group_key(ev: dict[str, Any]) -> str:
    """One key per bill: all budget votes of a legislature share one (their 'title' is the budget section)."""
    if is_budget(ev):
        return f"{ev['legislature']}:presupuestos:{ev['vote_date'][:4]}"
    return f"{ev['legislature']}:{motion_key(ev['expediente_text'])}"


def rank_laws(obj: str, listing: list[dict[str, Any]], top: int = 6) -> list[str]:
    scored = sorted(listing, key=lambda x: -similarity(obj, law_object(x.get("titulo", ""))))
    return [x["id_iniciativa"] for x in scored[:top] if similarity(obj, law_object(x.get("titulo", ""))) > 0.2]


def doc_role(label: str) -> str | None:
    f = fold(label)
    if f.startswith("enmiendas del senado"):
        return "senado"
    if f.startswith("enmiendas a la totalidad") or f.startswith("indice de enmiendas"):
        return None
    if f.startswith("enmiendas"):
        return "enmiendas"
    if "dictamen" in f or "votos particulares" in f or "mantenimiento" in f:
        return "dictamen"
    return None


def link_law(group: dict[str, Any], listings: dict[str, list[dict[str, Any]]], cache_dir: Path, timeout: int) -> dict[str, Any]:
    leg = group["legislature"]
    wanted = {p for p in (vote_path(u) for u in group["source_urls"]) if p}
    listing = [x for t in LAW_TYPES for x in listings.get((leg, t), [])]
    if group["budget"]:
        obj = f"Presupuestos Generales del Estado para el año {int(group['year']) + 1}"
        candidates = [x["id_iniciativa"] for x in listing if obj.lower() in fold(x.get("titulo", ""))] or rank_laws(obj, listing)
    else:
        obj = law_object(group["expediente_text"])
        candidates = rank_laws(obj, listing)
    for refresh in (False, True):
        for exp in candidates:
            page = parse_initiative_page(leg_initiative_page(exp, leg, cache_dir, timeout, refresh=refresh))
            if wanted & set(page["vote_paths"]):
                docs = [{**b, "role": r} for b in page["boletines"] if (r := doc_role(b["label"]))]
                return {"expediente": exp, "match": "vote_listed_on_initiative_page", "object": obj, "docs": docs}
    return {"expediente": None, "match": "not_found", "object": obj, "candidates": candidates}


# ---------------------------------------------------------------------------
# Parsing BOCG amendment documents.

FURNITURE_RE = re.compile(
    r"^\s*(cve: BOCG-[\w-]+|BOLET[ÍI]N OFICIAL DE LAS CORTES GENERALES|CONGRESO DE LOS DIPUTADOS|"
    r"Serie [A-Z] N[úu]m\. [\w-]+\s+.*P[áa]g\. \d+|[A-Z]+ LEGISLATURA)\s*$"
)
AMENDMENT_RE = re.compile(r"^\s*ENMIENDA N[ÚU]M\. ?(\d+)\s*$", re.M)


def pdf_text(path: Path) -> str:
    out = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"], capture_output=True, check=True)
    lines = [ln for ln in out.stdout.decode("utf-8", errors="replace").split("\n") if not FURNITURE_RE.match(ln)]
    return "\n".join(lines).replace("\f", "\n")


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_amendments(text: str) -> dict[str, dict[str, str]]:
    """'ENMIENDA NÚM. N' blocks -> {N: {firmante, body}}; the first lines after the number are the signatory."""
    out: dict[str, dict[str, str]] = {}
    marks = list(AMENDMENT_RE.finditer(text))
    for i, m in enumerate(marks):
        block = text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        firmante: list[str] = []
        body_start = 0
        for j, ln in enumerate(lines):
            if re.match(r"^(FIRMANTE:?)$", ln, re.I):
                continue
            if re.match(r"^(De (adici|modific|supresi|sustituci)|Precepto|ALTAS|A la secci|Al art|A la disposici|Texto que se propone)", ln, re.I):
                body_start = j
                break
            firmante.append(ln)
            if len(firmante) >= 4:
                body_start = j + 1
                break
        body = squash(" ".join(lines[body_start:]))
        out.setdefault(m.group(1), {"firmante": squash(" ".join(firmante)), "body": body})
    return out


def load_doc_text(doc: dict[str, Any], cache_dir: Path, timeout: int) -> str:
    path = fetch_pdf(doc["pdf_url"], cache_dir, timeout)
    cache = path.with_suffix(".txt")
    if cache.exists() and cache.stat().st_size > 0:
        return cache.read_text(encoding="utf-8")
    text = pdf_text(path)
    cache.write_text(text, encoding="utf-8")
    return text


# ---------------------------------------------------------------------------
# Matching votes to amendments.

def expand_numbers(text: str) -> list[str]:
    """'Enmiendas 12, 15 y 35 a 37' -> 12, 15, 35, 36, 37 (numbers after the word 'enmienda(s)' only)."""
    t = re.sub(r"transaccional(?:\s+en\s+(?:Comisi[óo]n|Ponencia))?\s+(?:n[úu]m(?:ero|\.)?\s*)?\d+", "transaccional", text, flags=re.I)
    t = re.sub(r"(?:Primera|Segunda|Tercera) votaci[óo]n de las", "", t, flags=re.I)
    if "transaccional" in fold(text):
        # "Enmienda transaccional nº 20, a la enmienda 590 del Grupo …" / "… a las enmiendas 36 del Grupo Mixto (Sra.
        # Belarra), 99 del Grupo Republicano y 147 del …": the transactional's own number comes before "a la(s)
        # enmienda(s)"; after it, group names carry no digits, so every number is a target amendment. Without a
        # target ("Enmienda transaccional 7.") there is nothing to read.
        m = re.search(r"\ba\s+las?\s+enmiendas?\b", text, re.I)
        if not m:
            return []
        tail = re.sub(r"\(voto particular[^)]*\)", "", text[m.end():], flags=re.I)
        return sorted(set(re.findall(r"\b\d+\b", tail)), key=int)
    nums: list[str] = []
    for m in re.finditer(r"enmiendas?\s+((?:(?:n[úu]m(?:eros?|s?\.)\s*)?\d+(?:\s*(?:,|y|a|e)\s*\d+)*))", t, re.I):
        chunk = m.group(1)
        for a, b in re.findall(r"(\d+)\s*a\s*(\d+)", chunk):
            if 0 < int(b) - int(a) <= 200:
                nums.extend(str(n) for n in range(int(a), int(b) + 1))
        chunk = re.sub(r"\d+\s*a\s*\d+", "", chunk)
        nums.extend(re.findall(r"\d+", chunk))
    return sorted(set(nums), key=int)


GROUP_TOKENS = {
    "popular": "popular", "socialista": "socialista", "vox": "vox", "sumar": "sumar", "republicano": "republicano",
    "junts": "junts", "vasco": "vasco", "bildu": "bildu", "mixto": "mixto", "plural": "plural", "ciudadanos": "ciudadanos",
    "confederal de unidas podemos": "podemos", "unidas podemos": "podemos",
}


def group_tokens(text: str) -> set[str]:
    f = fold(text)
    return {v for k, v in GROUP_TOKENS.items() if k in f}


def persons_in(text: str) -> list[str]:
    """First surname of each deputy named in '(Sr. Sayas)', '(Sres. Sayas López y García Adanero)'."""
    m = re.search(r"\((?:Sr|Sra|Sres|Sras)\.\s*([^)]+)\)", text)
    if not m:
        return []
    names = re.split(r"\s*(?:,|\by\b)\s*", re.sub(r"\b(?:Sr|Sra|Sres|Sras)\.\s*", "", m.group(1)))
    return [fold(n).split()[0] for n in names if n.strip()]


def budget_scope(expediente_text: str):
    """Budget votes are by section ('Sección 17 (…)'): their 'resto' covers only that section's amendments.
    Other budget headings (titles of the articulado, provisions) cover amendments that are not to a section."""
    m = re.match(r"\s*Secci[óo]n\s+(\d+)", str(expediente_text or ""))
    if m:
        pat = re.compile(rf"Secci[óo]n:\s*{int(m.group(1)):02d}\b|Secci[óo]n:\s*{int(m.group(1))}\b")
        return lambda body: bool(pat.search(body))
    return lambda body: not re.search(r"Secci[óo]n:\s*\d+", body)


def senate_excerpt(text: str, ref: str, width: int = 2400) -> str:
    """Parts of the Senate's message about the precept named in the vote ('Enmienda al artículo 26.1 c)'):
    the explanation in the mensaje motivado and, further on, the amended text itself (two windows)."""
    body = text[text.find("MENSAJE MOTIVADO"):] if "MENSAJE MOTIVADO" in text else text
    flat = squash(body)
    folded = fold(flat)
    m = re.search(r"(art[íi]culo|disposici[óo]n (?:adicional|transitoria|derogatoria|final)|pre[áa]mbulo|anexo)\s*([\w.\s]{0,40})", ref, re.I)
    if not m:
        return flat[:width]
    head = fold(m.group(1))
    num = fold(squash(m.group(2)).split(" ")[0].strip(".,")) if m.group(2) else ""
    pattern = re.escape(head) + (r"\s+" + re.escape(num) + r"\b" if num else "")
    hits = [h.start() for h in re.finditer(pattern, folded)]
    if not hits:
        return flat[:width]
    windows, last_end = [], -1
    for h in hits:
        if h < last_end:
            continue
        windows.append(flat[max(0, h - 150): h + width // 2])
        last_end = h + width // 2
        if len(windows) == 2:
            break
    return " […] ".join(windows)


def resolve_vote(ev: dict[str, Any], amendments: dict[str, dict[str, str]], senate_text: str, dictamen_text: str,
                 separately: set[str], budget: bool = False) -> dict[str, Any]:
    sub_title, sub_text = clean(ev["subgroup_title"]), clean(ev["subgroup_text"])
    if ev["kind"] == "enmienda_senado":
        if not senate_text:
            return {"resolution": "sin_texto", "reason": "sin_mensaje_motivado"}
        return {"resolution": "senado", "excerpt": senate_excerpt(senate_text, sub_text)}
    if ev["kind"] == "voto_particular":
        if not dictamen_text:
            return {"resolution": "sin_texto", "reason": "sin_dictamen"}
        flat = squash(dictamen_text)
        want = group_tokens(sub_title + " " + sub_text)
        hits = [m.start() for m in re.finditer(r"VOTO PARTICULAR", flat)]
        for h in hits:
            if not want or group_tokens(flat[h:h + 400]) & want:
                return {"resolution": "voto_particular", "excerpt": flat[h:h + MAX_TEXT]}
        return {"resolution": "sin_texto", "reason": "voto_particular_no_encontrado"}
    nums = expand_numbers(sub_text)
    transactional = "transaccional" in fold(sub_text)
    if nums:
        found = [n for n in nums if n in amendments]
        if not found:
            return {"resolution": "sin_texto", "reason": "numero_no_encontrado", "numbers": nums}
        return {"resolution": "transaccional" if transactional else "numeros", "numbers": found,
                "missing": [n for n in nums if n not in amendments]}
    if "resto" in fold(sub_text) or "bloque" in fold(sub_text):
        want = group_tokens(sub_title)
        who = persons_in(sub_title)
        in_scope = budget_scope(ev["expediente_text"]) if budget else (lambda _b: True)
        pool = [n for n, a in amendments.items()
                if n not in separately and (not want or group_tokens(a["firmante"]) & want)
                and (not who or any(w in fold(a["firmante"]) for w in who)) and in_scope(a["body"])]
        if not pool:
            return {"resolution": "sin_texto", "reason": "resto_vacio"}
        return {"resolution": "resto", "numbers": sorted(pool, key=int)}
    return {"resolution": "sin_texto", "reason": "referencia_no_reconocida"}


# ---------------------------------------------------------------------------
# Commands.

def amendment_events(conn: sqlite3.Connection, seed: dict[str, Any], legs: list[tuple[str, str | None]]) -> list[dict[str, Any]]:
    out = []
    for lg, since in legs:
        evs = [e for e in load_congreso_events(conn, lg, since) if e["kind"] in AMENDMENT_KINDS]
        maj = party_majorities(conn, seed, [e["vote_event_id"] for e in evs], lg)
        out.extend(e for e in evs if contested(maj[e["vote_event_id"]]))
    return out


def parse_legs(values: list[str]) -> list[tuple[str, str | None]]:
    out = []
    for v in values:
        lg, _, since = v.partition(":")
        out.append((lg, since or None))
    return out


def cmd_link(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    legs = parse_legs(args.legislature)
    events = amendment_events(conn, seed, legs)
    cache_dir = Path(args.cache_dir)
    stamp = args.listing_date or datetime.now(timezone.utc).strftime("%Y%m%d")
    listings = {(lg, t): list_type_fresh(t, cache_dir, stamp, args.timeout, 0.2, lg) for lg, _s in legs for t in LAW_TYPES}
    groups: dict[str, dict[str, Any]] = {}
    for ev in events:
        g = groups.setdefault(law_group_key(ev), {
            "legislature": ev["legislature"], "expediente_text": ev["expediente_text"], "budget": is_budget(ev),
            "year": ev["vote_date"][:4], "events": [], "source_urls": [],
        })
        g["events"].append(ev)
        g["source_urls"].append(ev["source_url"] or ev["vote_event_id"][4:])
    print(f"amendment votes={len(events)} bills={len(groups)}", flush=True)

    def work(item: tuple[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
        key, g = item
        try:
            law = link_law(g, listings, cache_dir, args.timeout)
        except Exception as exc:  # noqa: BLE001
            law = {"expediente": None, "match": "error", "error": f"{type(exc).__name__}: {exc}"[:240]}
        amendments: dict[str, dict[str, str]] = {}
        senate = dictamen = ""
        doc_urls = defaultdict(list)
        for d in law.get("docs") or []:
            try:
                text = load_doc_text(d, cache_dir, args.timeout)
            except Exception as exc:  # noqa: BLE001
                law.setdefault("doc_errors", []).append(f"{d['bocg']}: {type(exc).__name__}: {exc}"[:200])
                continue
            doc_urls[d["role"]].append(d["pdf_url"])
            if d["role"] == "enmiendas":
                for n, a in parse_amendments(text).items():
                    amendments.setdefault(n, {**a, "doc": d["pdf_url"]})
            elif d["role"] == "senado":
                senate += "\n" + text
            elif d["role"] == "dictamen":
                dictamen += "\n" + text
        separately = {n for ev in g["events"] for n in expand_numbers(clean(ev["subgroup_text"]))}
        votes = {}
        for ev in g["events"]:
            r = resolve_vote(ev, amendments, senate, dictamen, separately, budget=g["budget"])
            votes[ev["vote_event_id"]] = {k: v for k, v in r.items() if k != "excerpt"}
        law.update({
            "legislature": g["legislature"], "title": clean(str(g["expediente_text"]).split("\n")[0]) if not g["budget"]
            else f"Presupuestos Generales del Estado para {int(g['year']) + 1}",
            "amendments_parsed": len(amendments), "doc_urls": dict(doc_urls), "votes": votes,
        })
        return key, law

    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for key, law in ex.map(work, sorted(groups.items())):
            results[key] = law
            res = Counter(v["resolution"] for v in law["votes"].values())
            print(f"{law.get('expediente') or '-':12} enm={law.get('amendments_parsed', 0):5} {dict(res)} {law['title'][:60]}", flush=True)
    res_all = Counter(v["resolution"] for law in results.values() for v in law["votes"].values())
    payload = {
        "meta": {
            "schema_version": DOCS_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "listing_date": stamp,
            "method": __doc__.split("\n\n")[1].strip() if __doc__ else "",
            "bills": len(results),
            "linked": sum(1 for r in results.values() if r.get("expediente")),
            "votes": sum(len(r["votes"]) for r in results.values()),
            "by_resolution": dict(sorted(res_all.items())),
        },
        "bills": dict(sorted(results.items())),
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"OK amendment docs -> {args.out} ({json.dumps(payload['meta']['by_resolution'], ensure_ascii=False)})")
    return 0


def amendment_text(nums: list[str], amendments: dict[str, dict[str, str]], limit: int = MAX_TEXT) -> list[dict[str, str]]:
    out, used = [], 0
    per = max(350, limit // max(1, len(nums)))
    for n in nums:
        a = amendments.get(n)
        if not a:
            continue
        body = a["body"][:per]
        out.append({"n": n, "firmante": a["firmante"][:120], "texto": body})
        used += len(body)
        if used >= limit:
            break
    return out


def cmd_units(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    docs = json.loads(Path(args.docs).read_text(encoding="utf-8"))["bills"]
    legs = parse_legs(args.legislature)
    events = {e["vote_event_id"]: e for e in amendment_events(conn, seed, legs)}
    bullets = json.loads(Path(args.bullets).read_text(encoding="utf-8")).get("by_vote", {}) if Path(args.bullets).exists() else {}
    cache_dir = Path(args.cache_dir)
    units_by_bill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, law in docs.items():
        amendments: dict[str, dict[str, str]] = {}
        senate = ""
        for role in ("enmiendas", "senado", "dictamen"):
            for url in (law.get("doc_urls") or {}).get(role, []):
                text = load_doc_text({"pdf_url": url}, cache_dir, args.timeout)
                if role == "enmiendas":
                    for n, a in parse_amendments(text).items():
                        amendments.setdefault(n, a)
                elif role == "senado":
                    senate += "\n" + text
                else:
                    law["_dictamen"] = law.get("_dictamen", "") + "\n" + text
        for vid, ref in law["votes"].items():
            ev = events.get(vid)
            if not ev or ref["resolution"] == "sin_texto":
                continue
            unit: dict[str, Any] = {
                "vote_event_id": vid,
                "vote_date": ev["vote_date"],
                "legislature": ev["legislature"],
                "kind": ev["kind"],
                "kind_label": KIND_LABELS[ev["kind"]],
                "title": law["title"] if law["title"].startswith("Presupuestos") else clean(ev["expediente_text"]),
                "subgroup": clean(" ".join(x for x in (ev["subgroup_title"], ev["subgroup_text"]) if x)),
                "result": "aprobada" if (ev["yes"] or 0) > (ev["no"] or 0) else "rechazada",
                "resolution": ref["resolution"],
                "yes_means": {
                    "enmienda_senado": "Votar Sí = aceptar el cambio que introdujo el Senado en la ley.",
                    "voto_particular": "Votar Sí = aprobar el voto particular (volver al texto que propone el grupo).",
                }.get(ev["kind"], "Votar Sí = incorporar la(s) enmienda(s) al texto de la ley."),
            }
            if ref["resolution"] in ("numeros", "transaccional", "resto"):
                nums = ref["numbers"]
                unit["amendments"] = amendment_text(nums if ref["resolution"] != "resto" else nums[:12], amendments)
                if ref["resolution"] == "resto":
                    unit["amendments_total"] = len(nums)
                    unit["note"] = ("Votación en bloque del resto de enmiendas del grupo: se muestran las primeras; "
                                    "clasifica la dirección dominante o usa 'mixto'.")
                if ref["resolution"] == "transaccional":
                    unit["note"] = ("Enmienda transaccional: su texto final no está en el BOCG; se muestran las enmiendas que "
                                    "transacciona. Baja la confianza.")
            elif ref["resolution"] == "senado":
                unit["senate_excerpt"] = senate_excerpt(senate, clean(ev["subgroup_text"]))
            elif ref["resolution"] == "voto_particular":
                flat = squash(law.get("_dictamen", ""))
                i = flat.find("VOTO PARTICULAR")
                unit["excerpt"] = flat[i:i + MAX_TEXT] if i >= 0 else ""
            b = (bullets.get(vid) or {}).get("bullets") or []
            if b:
                unit["law_bullets"] = [x.get("text") for x in b][:4]
            units_by_bill[key].append(unit)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    batches: list[list[dict[str, Any]]] = [[]]
    for key in sorted(units_by_bill, key=lambda k: units_by_bill[k][0]["vote_date"]):
        for u in sorted(units_by_bill[key], key=lambda u: u["vote_date"]):
            if len(batches[-1]) >= args.batch_size:
                batches.append([])
            batches[-1].append(u)
    for i, batch in enumerate(batches, 1):
        (out_dir / f"batch_enm_{i:03d}.json").write_text(json.dumps(batch, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n = sum(len(v) for v in units_by_bill.values())
    print(json.dumps({"units": n, "batches": len(batches), "by_resolution": dict(Counter(u["resolution"] for v in units_by_bill.values() for u in v))}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("link", "units"):
        p = sub.add_parser(name)
        p.add_argument("--db", required=True)
        p.add_argument("--seed", default=str(DEFAULT_SEED))
        p.add_argument("--legislature", action="append", default=[], help="LEG o LEG:YYYY-MM-DD (repetible)")
        p.add_argument("--docs", default=str(DEFAULT_DOCS))
        p.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
        p.add_argument("--timeout", type=int, default=180)
    sub.choices["link"].add_argument("--out", default=str(DEFAULT_DOCS))
    sub.choices["link"].add_argument("--listing-date")
    sub.choices["link"].add_argument("--workers", type=int, default=4)
    sub.choices["units"].add_argument("--bullets", default=str(DEFAULT_BULLETS))
    sub.choices["units"].add_argument("--out-dir", required=True)
    sub.choices["units"].add_argument("--batch-size", type=int, default=40)
    args = parser.parse_args(argv)
    args.legislature = args.legislature or [CURRENT_LEGISLATURE]
    return cmd_link(args) if args.cmd == "link" else cmd_units(args)


if __name__ == "__main__":
    raise SystemExit(main())

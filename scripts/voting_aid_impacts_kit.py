#!/usr/bin/env python3
"""Shared toolkit for drafting «Ramificaciones» (voting_aid_vote_impacts) without reinventing the wheel.

Every drafting agent used to rediscover the same things: how to get past the Congreso User-Agent check, which
INE/Eurostat endpoints answer, which hosts are blocked, which figures another agent already verified. This
puts them in one place, keeps every output short (an agent's context is re-read on every turn), and caches
downloads so a source fetched once serves everyone.

  catalog [REGEX]            verified figures already in the seed and part files (one line each, reuse by id)
  fetch URL [-g REGEX]       download once (shared cache), PDF->text with page markers, print only matching lines
  vote URL                   what a Congreso vote was about: expediente text and the point voted (textoSubGrupo)
  ine TABLE [-g REGEX]       latest values of an INE table (servicios.ine.es DATOS_TABLA), one line per series
  apply-indirect DIR --map M apply initiative-level indirect effects (applies_to: "all" or short vote ids) to its votes
  apply-effects DIR          apply per-vote direct effects ({"vote_event_id", "verdict": "written"|"none", "direct_effects", "note"})
  apply-votes DIR            apply per-vote figure reviews (keep/improved, final facts, new facts) to the part files
  apply-reviews DIR          apply reviewer verdicts (one <fact-id>.json each) to the seed and part files
  eurostat DATASET QUERY     Eurostat JSON-stat, e.g. `eurostat ilc_lvho07c "geo=ES&geo=EU27_2020&sinceTimePeriod=2023"`

To compute in one step (sums, shares, re-checks), use it from python instead of chaining shell calls:
  from scripts.voting_aid_impacts_kit import text, ine_series, eurostat_values
  text(url)                      cached plain text of any source (PDF pages marked «=== pág. N ===»)
  ine_series(table, nult=1)      {series name: [(year, period_id, value), ...]}
  eurostat_values(ds, query)     {"label | label": value}
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import html
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
SEED = BASE_DIR / "etl/data/seeds/voting_aid_vote_impacts_v1.json"
PARTS = BASE_DIR / "etl/data/seeds/voting_aid_vote_impacts_v1.d"
CACHE = BASE_DIR / "etl/data/raw/voting_aid_sources"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
# Seen blocking automated access while drafting (2026-10-13): fail fast instead of retrying.
BLOCKED = {
    "www.interior.gob.es": "403 Cloudflare challenge",
    "interior.gob.es": "403 Cloudflare challenge",
    "eur-lex.europa.eu": "WAF / empty page",
    "www.coe.int": "403 Cloudflare",
    "rm.coe.int": "403 Cloudflare",
    "www.ordenacionjuego.es": "connection refused",
    "www.unrwa.org": "403",
    "reliefweb.int": "403",
    "fra.europa.eu": "403 challenge",
}

# Official sites whose TLS chain fails from here (seen 2026-10-13). Retry unverified for these hosts only, never globally.
INSECURE_SSL_HOSTS = {"www.mites.gob.es", "mites.gob.es", "www.sepe.es", "sepe.es", "www.mapa.gob.es", "mapa.gob.es", "servicio.mapa.gob.es", "www.csd.gob.es", "www.educacionfpydeportes.gob.es", "www.transportes.gob.es", "www.tribunalconstitucional.es", "www.juventudeinfancia.gob.es", "juventudeinfancia.gob.es", "observatoriodelainfancia.juventudeinfancia.gob.es", "origin.miteco.gob.es"}


def out(text: str, limit: int) -> None:
    text = text.strip()
    print(text if len(text) <= limit else text[:limit] + f"\n… [recortado: {len(text)} caracteres; afina con -g]")


def catalog(args: argparse.Namespace) -> None:
    facts: dict[str, tuple[str, dict]] = {}
    for name, path in [("semilla", SEED)] + [(p.stem, p) for p in sorted(PARTS.glob("*.json"))]:
        for fid, f in (json.loads(path.read_text(encoding="utf-8")).get("facts") or {}).items():
            facts.setdefault(fid, (name, f))
    import unicodedata

    def fold(t: str) -> str:  # accent-insensitive matching: «pension» finds «pensión»
        return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()

    rx = re.compile("|".join(f"(?:{fold(r)})" for r in args.regex), re.I) if args.regex else None
    lines = []
    for fid, (_, f) in sorted(facts.items()):
        if args.prefix and not fid.startswith(tuple(args.prefix)):
            continue
        full = f"{fid} | {f.get('period')} | {f.get('source')} | {f.get('text')} | {f.get('url')}"
        if not rx or rx.search(fold(full)):
            # Compact by default: id, period and the start of the text; --full adds source and the whole text.
            lines.append(full if args.full else f"{fid} | {f.get('period')} | {str(f.get("text"))[:220]}")
    print(f"{len(lines)} de {len(facts)} cifras")
    shown, used = [], 0
    for line in lines:
        if used + len(line) > args.max:
            break
        shown.append(line)
        used += len(line) + 1
    print("\n".join(shown))
    if len(shown) < len(lines):  # never hide matches silently: list the rest by id
        rest = [line.split(" | ", 1)[0] for line in lines[len(shown):]]
        print(f"… y {len(rest)} más (pide `catalog <id>` para ver una): " + ", ".join(rest))


def _jaxi_csv(url: str) -> str:
    """PC-Axis «Tabla.htm?path=…&file=…» pages (Educación, other jaxi sites) render data with JavaScript:
    fetch the same table as CSV instead."""
    from urllib.parse import parse_qs
    u = urlparse(url)
    q = parse_qs(u.query)
    if u.path.endswith("/Tabla.htm") and q.get("path") and q.get("file"):
        base = u.path.rsplit("/Tabla.htm", 1)[0]
        return f"{u.scheme}://{u.netloc}{base}/files/_px/es/csv_bdsc{q["path"][0].rstrip("/")}/{q["file"][0]}.csv_bdsc?nocab=1"
    return url


def _download(url: str) -> tuple[Path | None, str]:
    url = _jaxi_csv(url)
    host = urlparse(url).hostname or ""
    if host in BLOCKED:
        return None, f"BLOQUEADO conocido ({BLOCKED[host]}): no reintentes, busca otra fuente oficial"
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(url.encode()).hexdigest()[:16]
    raw, txt, err = CACHE / f"{key}.bin", CACHE / f"{key}.txt", CACHE / f"{key}.err"
    if txt.exists():
        return txt, "cache"
    if err.exists():
        return None, f"falló antes: {err.read_text()}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9"})
    try:
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                body, ctype = r.read(), r.headers.get("Content-Type", "")
        except urllib.error.URLError as e:
            if host not in INSECURE_SSL_HOSTS or "CERTIFICATE" not in str(e).upper():
                raise
            import ssl
            with urllib.request.urlopen(req, timeout=40, context=ssl._create_unverified_context()) as r:
                body, ctype = r.read(), r.headers.get("Content-Type", "")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        err.write_text(str(e)[:200])
        return None, f"ERROR {e}"
    raw.write_bytes(body)
    if body[:4] == b"%PDF":
        pages = subprocess.run(["pdftotext", "-layout", str(raw), "-"], capture_output=True, text=True).stdout.split("\f")
        text = "\n".join(f"=== pág. {i} ===\n{p}" for i, p in enumerate(pages, 1) if p.strip())
    elif "json" in ctype or body[:1] in (b"{", b"["):
        text = body.decode("utf-8", "replace")
    else:
        s = body.decode("utf-8", "replace")
        s = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", s)
        s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d)>", "\n", s)
        text = re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)))
        text = re.sub(r"\n\s*\n+", "\n", text)
    if body[:15].lower().startswith(b"<!doctype") and ("Just a moment" in text[:3000] or len(text) < 400):
        err.write_text("challenge/HTML vacío")
        return None, "BLOQUEADO (reto anti-bot o página vacía)"
    txt.write_text(text, encoding="utf-8")
    return txt, f"descargado {len(body)} bytes"


def fetch(args: argparse.Namespace) -> None:
    path, status = _download(args.url)
    print(f"[{status}]")
    if not path:
        return
    text = path.read_text(encoding="utf-8")
    if not args.grep:
        print(f"{len(text)} caracteres en {path}; sin -g muestro el principio (para calcular, lee ese archivo con python)")
        out(text, min(args.max, 1500))
        return
    rx, lines, page, hits, last = re.compile(args.grep, re.I), text.split("\n"), "", [], -10**9
    for i, line in enumerate(lines):
        if line.startswith("=== pág."):
            page = line.strip("= ")
        elif rx.search(line) and i > last + args.context:  # skip matches already shown in the previous context
            last = i
            ctx = " ⏎ ".join(x.strip() for x in lines[max(0, i - args.context) : i + args.context + 1] if x.strip())
            hits.append(f"[{page or 'l.' + str(i)}] {ctx}")
    print(f"{len(hits)} coincidencias")
    out("\n".join(hits), args.max)


def vote(args: argparse.Namespace) -> None:
    url = args.url.removeprefix("url:")
    path, status = _download(url)
    if not path:
        print(f"[{status}]")
        return
    info = json.loads(path.read_text(encoding="utf-8")).get("informacion") or {}
    for k in ("fecha", "titulo", "textoExpediente", "tituloSubGrupo", "textoSubGrupo"):
        if info.get(k):
            print(f"{k}: {info[k]}")


def _get_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ERROR HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


def ine(args: argparse.Namespace) -> None:
    nult = max(args.nult, 40) if args.year else args.nult
    rows = _get_json(f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{args.table}?nult={nult}")
    if args.year:  # yearly total per series from monthly/quarterly data (e.g. trips in 2025 = sum of 12 months)
        for s in rows:
            pts = [d for d in s.get("Data") or [] if d.get("Anyo") == args.year and d.get("Valor") is not None]
            s["Data"] = [{"Anyo": args.year, "FK_Periodo": 28, "Valor": round(sum(d["Valor"] for d in pts), 3)}] if pts else []
            s["Nombre"] = f"{s.get('Nombre', '').strip()} [suma de {len(pts)} periodos de {args.year}]"
    rx = re.compile(args.grep, re.I) if args.grep else None
    lines = []
    for s in rows:
        if rx and not rx.search(s.get("Nombre", "")):
            continue
        vals = "; ".join(f"{d.get('Anyo')}{'' if d.get('FK_Periodo') == 28 else ' (periodo ' + str(d.get('FK_Periodo')) + ')'}: {d.get('Valor')}" for d in s.get("Data") or [])
        lines.append(f"{s.get('Nombre')} => {vals}")
    print(f"tabla {args.table}: {len(lines)} series (fuente https://www.ine.es/jaxiT3/Tabla.htm?t={args.table})")
    if not lines:
        print("ninguna serie casa con -g; nombres de ejemplo: " + " || ".join(s.get("Nombre", "") for s in rows[:5]))
    if args.sum and lines:
        total = sum((s.get("Data") or [{}])[-1].get("Valor") or 0 for s in rows if not rx or rx.search(s.get("Nombre", "")))
        print(f"SUMA del último valor de las {len(lines)} series: {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    out("\n".join(lines), args.max)


def eurostat(args: argparse.Namespace) -> None:
    d = _get_json(f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{args.dataset}?format=JSON&lang=EN&{args.query}")
    dims, sizes, vals = d["id"], d["size"], d["value"]
    labels = [{v: d["dimension"][k]["category"]["label"][c] for c, v in d["dimension"][k]["category"]["index"].items()} for k in dims]
    lines = []
    for flat, v in vals.items():
        idx, rest = [], int(flat)
        for s in reversed(sizes):
            idx.append(rest % s)
            rest //= s
        idx.reverse()
        lines.append(" | ".join(labels[i][j] for i, j in enumerate(idx) if sizes[i] > 1) + f" = {v}")
    print(f"{d.get('label')} (actualizado {d.get('updated')}); fuente https://ec.europa.eu/eurostat/databrowser/view/{args.dataset}/default/table")
    out("\n".join(lines), args.max)


def apply_reviews(args: argparse.Namespace) -> None:
    """ok/corrected verdicts stamp the fact with its review (and apply the correction) wherever it is defined;
    reject/unverifiable are only listed, for a person to decide."""
    reviews = {r["id"]: r for r in (json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(args.dir).glob("*.json")))}
    pending = {k: v for k, v in reviews.items() if v.get("verdict") in ("ok", "corrected")}
    touched = set()
    for path in [SEED] + sorted(PARTS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for fid, fact in (data.get("facts") or {}).items():
            r = pending.get(fid)
            if not r:
                continue
            if r["verdict"] == "corrected":
                fact.update({k: v for k, v in (r.get("corrected") or {}).items() if k in ("text", "period", "source", "url") and v})
            fact["review"] = {"status": "agent_reviewed", "verdict": r["verdict"], "checked": r.get("checked", ""), "by": args.by, "at": args.at}
            changed = True
            touched.add(fid)
        if changed:
            indent = None if path == SEED else 1
            path.write_text(json.dumps(data, ensure_ascii=False, indent=indent if indent else 2) + "\n", encoding="utf-8")
    counts = collections.Counter(r.get("verdict") for r in reviews.values())
    print(f"revisiones: {dict(counts)}; aplicadas a {len(touched)} cifras")
    for fid, r in sorted(reviews.items()):
        if r.get("verdict") not in ("ok", "corrected"):
            print(f"PENDIENTE {r.get('verdict')}: {fid} — {r.get('note') or r.get('checked')}")
    missing = set(pending) - touched
    if missing:
        print("sin definición encontrada: " + ", ".join(sorted(missing)))


def apply_votes(args: argparse.Namespace) -> None:
    """One <anything>.json per vote: {"vote_event_id", "verdict": "keep"|"improved", "facts": [...], "new_facts": {...}, "note"}.
    New facts go into the part file that owns the vote; the vote gets its final facts and a `scale_review` stamp."""
    reviews = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(args.dir).glob("*.json"))]
    by_vote = {r["vote_event_id"]: r for r in reviews}
    known = set()
    for path in [SEED] + sorted(PARTS.glob("*.json")):
        known |= set((json.loads(path.read_text(encoding="utf-8")).get("facts") or {}))
    done, problems = 0, []
    for path in sorted(PARTS.glob("*.json")) + [SEED]:
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for vid, vote in (data.get("votes") or {}).items():
            r = by_vote.get(vid)
            if not r:
                continue
            new = r.get("new_facts") or {}
            final = r.get("facts") or vote.get("facts")
            missing = [f for f in final if f not in known and f not in new]
            if r.get("verdict") not in ("keep", "improved") or not 1 <= len(final) <= 3 or missing:
                problems.append(f"{vid[-40:]}: verdict={r.get('verdict')} facts={final} desconocidas={missing}")
                continue
            for fid, fact in new.items():
                data.setdefault("facts", {})[fid] = {k: fact[k] for k in ("text", "period", "source", "url")}
                known.add(fid)
            vote["facts"] = list(final)
            vote["scale_review"] = {"verdict": r["verdict"], "note": r.get("note", ""), "by": args.by, "at": args.at}
            changed, done = True, done + 1
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1 if path != SEED else 2) + "\n", encoding="utf-8")
    print(f"aplicadas {done} de {len(reviews)}; {collections.Counter(r.get('verdict') for r in reviews)}")
    for line in problems:
        print("PROBLEMA " + line)


def apply_effects(args: argparse.Namespace) -> None:
    """Write drafted direct effects into the part file that owns each vote and stamp `effects_review`."""
    reviews = {r["vote_event_id"]: r for r in (json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(args.dir).glob("*.json")))}
    done, problems = 0, []
    for path in sorted(PARTS.glob("*.json")) + [SEED]:
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for vid, vote in (data.get("votes") or {}).items():
            r = reviews.get(vid)
            if not r:
                continue
            effects = r.get("direct_effects") or []
            if r.get("verdict") == "written" and not (1 <= len(effects) <= 4 and all(e.get("actor") and e.get("text") and e.get("locator") for e in effects)):
                problems.append(f"{vid[-40:]}: efectos incompletos")
                continue
            if r.get("verdict") == "written":
                vote["direct_effects"] = [{k: e[k] for k in ("actor", "text", "locator")} for e in effects]
            vote["effects_review"] = {"verdict": r.get("verdict"), "note": r.get("note", ""), "by": args.by, "at": args.at}
            changed, done = True, done + 1
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1 if path != SEED else 2) + "\n", encoding="utf-8")
    print(f"aplicadas {done} de {len(reviews)}; {collections.Counter(r.get('verdict') for r in reviews.values())}")
    for line in problems:
        print("PROBLEMA " + line)


def apply_indirect(args: argparse.Namespace) -> None:
    """One <expediente>.json per initiative with effects tagged applies_to ["all"] or short vote ids (sha1[:10]).
    A vote gets the effects that apply to it only if both kinds remain (max 3 of each); votes that already have
    indirect effects are left alone."""
    exp_votes = json.loads(Path(args.map).read_text(encoding="utf-8"))
    per_vote: dict[str, dict] = {}
    for path in sorted(Path(args.dir).glob("*.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        for vid in exp_votes.get(r.get("expediente"), []):
            short = hashlib.sha1(vid.encode()).hexdigest()[:10]
            sel = [e for e in r.get("effects") or [] if "all" in (e.get("applies_to") or []) or short in (e.get("applies_to") or [])]
            ben = [e for e in sel if e.get("kind") == "beneficio_esperado"][:3]
            ris = [e for e in sel if e.get("kind") == "riesgo_senalado"][:3]
            per_vote[vid] = {"effects": ben + ris if ben and ris else [], "gaps": r.get("gaps") or "", "note": r.get("note") or ""}
    stats = collections.Counter()
    for path in sorted(PARTS.glob("*.json")) + [SEED]:
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for vid, vote in (data.get("votes") or {}).items():
            r = per_vote.get(vid)
            if not r or vote.get("indirect_effects"):
                continue
            if r["effects"]:
                vote["indirect_effects"] = [{k: e[k] for k in ("kind", "text", "evidence", "source", "locator", "url")} for e in r["effects"]]
                if r["gaps"] and not vote.get("gaps"):
                    vote["gaps"] = r["gaps"]
                stats["con_efectos"] += 1
            else:
                stats["sin_equilibrio_o_vacio"] += 1
            vote["indirect_review"] = {"verdict": "written" if r["effects"] else "none", "note": r["note"], "by": args.by, "at": args.at}
            changed = True
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1 if path != SEED else 2) + "\n", encoding="utf-8")
    print(dict(stats))


def text(url: str) -> str:
    """Cached plain text of a source (raises if blocked or unreachable)."""
    path, status = _download(url)
    if not path:
        raise RuntimeError(status)
    return path.read_text(encoding="utf-8")


def ine_series(table: str | int, nult: int = 1) -> dict[str, list[tuple]]:
    rows = _get_json(f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{table}?nult={nult}")
    out: dict[str, list[tuple]] = {}
    for s in rows:
        name = s.get("Nombre", "").strip()
        if name in out:  # same label in two places (e.g. two towns called Torrent): keep both
            name = f"{name} [{s.get('COD')}]"
        out[name] = [(d.get("Anyo"), d.get("FK_Periodo"), d.get("Valor")) for d in s.get("Data") or []]
    return out


def eurostat_values(dataset: str, query: str = "geo=ES") -> dict[str, float]:
    d = _get_json(f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?format=JSON&lang=EN&{query}")
    dims, sizes = d["id"], d["size"]
    labels = [{v: d["dimension"][k]["category"]["label"][c] for c, v in d["dimension"][k]["category"]["index"].items()} for k in dims]
    out = {}
    for flat, v in d["value"].items():
        idx, rest = [], int(flat)
        for size in reversed(sizes):
            idx.append(rest % size)
            rest //= size
        idx.reverse()
        out[" | ".join(labels[i][j] for i, j in enumerate(idx) if sizes[i] > 1)] = v
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("catalog")
    c.add_argument("regex", nargs="*", help="one or more regex (OR), e.g. catalog pesca flota 'talidom'")
    c.add_argument("--full", action="store_true")
    c.add_argument("--prefix", action="append", help="only facts whose id starts with this (repeatable, e.g. --prefix eje-inmigracion --prefix eje-sahara)")
    c.add_argument("--max", type=int, default=3000)
    f = sub.add_parser("fetch")
    f.add_argument("url")
    f.add_argument("-g", "--grep")
    f.add_argument("-C", "--context", type=int, default=1)
    f.add_argument("--max", type=int, default=3500)
    v = sub.add_parser("vote")
    v.add_argument("url")
    i = sub.add_parser("ine")
    i.add_argument("table")
    i.add_argument("-g", "--grep")
    i.add_argument("--nult", type=int, default=1)
    i.add_argument("--sum", action="store_true", help="suma el último valor de las series que casan con -g")
    i.add_argument("--year", type=int, help="total anual por serie (suma de los meses/trimestres de ese año)")
    i.add_argument("--max", type=int, default=3500)
    e = sub.add_parser("eurostat", epilog='ejemplo: eurostat nrg_pc_204 "geo=ES&nrg_cons=KWH2500-4999&tax=I_TAX&tax=X_TAX&currency=EUR&sinceTimePeriod=2025"; si da 400, el error dice qué dimensión sobra o falta')
    e.add_argument("dataset")
    e.add_argument("query", nargs="?", default="geo=ES")
    e.add_argument("--max", type=int, default=3500)
    a = sub.add_parser("apply-reviews")
    a.add_argument("dir")
    a.add_argument("--by", default="claude-sonnet-5-5 (revisión de cifras derivadas)")
    a.add_argument("--at", default="2026-10-13")
    av = sub.add_parser("apply-votes")
    av.add_argument("dir")
    av.add_argument("--by", default="claude-sonnet-5-5 (revisión de escalas genéricas)")
    av.add_argument("--at", default="2026-10-13")
    ae = sub.add_parser("apply-effects")
    ae.add_argument("dir")
    ae.add_argument("--by", default="claude-sonnet-5-5 (efectos directos desde el texto oficial)")
    ae.add_argument("--at", default="2026-10-13")
    ai = sub.add_parser("apply-indirect")
    ai.add_argument("dir")
    ai.add_argument("--map", required=True, help="JSON {expediente: [vote_event_id, ...]}")
    ai.add_argument("--by", default="claude-sonnet-5-5 (efectos indirectos desde el debate del Pleno)")
    ai.add_argument("--at", default="2026-10-13")
    args = p.parse_args(argv)
    {"apply-indirect": apply_indirect, "apply-effects": apply_effects, "apply-votes": apply_votes, "apply-reviews": apply_reviews, "catalog": catalog, "fetch": fetch, "vote": vote, "ine": ine, "eurostat": eurostat}[args.cmd](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
  eurostat DATASET QUERY     Eurostat JSON-stat, e.g. `eurostat ilc_lvho07c "geo=ES&geo=EU27_2020&sinceTimePeriod=2023"`
"""

from __future__ import annotations

import argparse
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


def out(text: str, limit: int) -> None:
    text = text.strip()
    print(text if len(text) <= limit else text[:limit] + f"\n… [recortado: {len(text)} caracteres; afina con -g]")


def catalog(args: argparse.Namespace) -> None:
    facts: dict[str, tuple[str, dict]] = {}
    for name, path in [("semilla", SEED)] + [(p.stem, p) for p in sorted(PARTS.glob("*.json"))]:
        for fid, f in (json.loads(path.read_text(encoding="utf-8")).get("facts") or {}).items():
            facts.setdefault(fid, (name, f))
    rx = re.compile(args.regex, re.I) if args.regex else None
    lines = []
    for fid, (_, f) in sorted(facts.items()):
        line = f"{fid} | {f.get('period')} | {str(f.get('source'))[:70]} | {f.get('text')}"
        if not rx or rx.search(line):
            lines.append(line)
    print(f"{len(lines)} de {len(facts)} cifras")
    out("\n".join(lines), args.max)


def _download(url: str) -> tuple[Path | None, str]:
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
        with urllib.request.urlopen(req, timeout=40) as r:
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
        print(f"{len(text)} caracteres en {path.relative_to(BASE_DIR)}; sin -g muestro el principio")
        out(text, min(args.max, 1500))
        return
    rx, lines, page, hits = re.compile(args.grep, re.I), text.split("\n"), "", []
    for i, line in enumerate(lines):
        if line.startswith("=== pág."):
            page = line.strip("= ")
        elif rx.search(line):
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
    rows = _get_json(f"https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{args.table}?nult={args.nult}")
    rx = re.compile(args.grep, re.I) if args.grep else None
    lines = []
    for s in rows:
        if rx and not rx.search(s.get("Nombre", "")):
            continue
        vals = "; ".join(f"{d.get('Anyo')}{'' if d.get('FK_Periodo') == 28 else ' (periodo ' + str(d.get('FK_Periodo')) + ')'}: {d.get('Valor')}" for d in s.get("Data") or [])
        lines.append(f"{s.get('Nombre')} => {vals}")
    print(f"tabla {args.table}: {len(lines)} series (fuente https://www.ine.es/jaxiT3/Tabla.htm?t={args.table})")
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("catalog")
    c.add_argument("regex", nargs="?")
    c.add_argument("--max", type=int, default=6000)
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
    i.add_argument("--max", type=int, default=3500)
    e = sub.add_parser("eurostat")
    e.add_argument("dataset")
    e.add_argument("query", nargs="?", default="geo=ES")
    e.add_argument("--max", type=int, default=3500)
    args = p.parse_args(argv)
    {"catalog": catalog, "fetch": fetch, "vote": vote, "ine": ine, "eurostat": eurostat}[args.cmd](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

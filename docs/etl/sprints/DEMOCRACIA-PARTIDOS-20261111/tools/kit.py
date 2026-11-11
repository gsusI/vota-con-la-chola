#!/usr/bin/env python3
"""One-call helpers for drafting/reviewing ledger events (fetch + extract + grep in a single command).

    python3 docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/tools/kit.py text URL --grep "Declarar|nulidad" --ctx 160
    python3 docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/tools/kit.py text URL --head 600      # title / opening
    python3 docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/tools/kit.py fallo URL                # TC/TS «FALLO» section
    python3 docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/tools/kit.py boe-stc 172/2020 --ruled 2020-11-19
    python3 docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/tools/kit.py quote URL "literal quote to find"   # accents/case/space-insensitive, PDF page
    python3 docs/etl/sprints/DEMOCRACIA-PARTIDOS-20261111/tools/kit.py words "a quote to count"

`text` handles HTML and PDF (pdftotext), caches every download (sha256 printed) under /tmp/vclc-democracy-kit, and
prints only the matches, so the output stays small. BOE: use https://www.boe.es/diario_boe/txt.php?id=BOE-A-... .
commission.europa.eu often answers HTTP 429: the helper retries with a pause.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CACHE = Path("/tmp/vclc-democracy-kit")
UA = "Mozilla/5.0 (compatible; vclc-etl/1.0; +https://votaconlachola.org)"


def fetch(url: str) -> tuple[bytes, str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / hashlib.sha1(url.encode()).hexdigest()
    if key.exists():
        return key.read_bytes(), (key.with_suffix(".type").read_text() if key.with_suffix(".type").exists() else "")
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=60) as r:
                body, ctype = r.read(), r.headers.get("Content-Type", "")
            key.write_bytes(body)
            key.with_suffix(".type").write_text(ctype)
            return body, ctype
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(4 + 6 * attempt if "429" in str(e) else 2)
    raise SystemExit(f"FETCH FAILED {url}: {last}")


def to_text(body: bytes, ctype: str) -> str:
    if body[:5] == b"%PDF-" or "pdf" in ctype:
        p = CACHE / (hashlib.sha1(body).hexdigest() + ".pdf")
        p.write_bytes(body)
        out = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True)
        return re.sub(r"[ \t]+", " ", out.stdout)
    text = body.decode("utf-8", "replace")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text)


def cmd_text(a) -> None:
    body, ctype = fetch(a.url)
    text = to_text(body, ctype)
    print(f"# {a.url} · {len(body)} bytes · sha256 {hashlib.sha256(body).hexdigest()[:16]} · {len(text)} chars")
    if a.head:
        print(re.sub(r"\s+", " ", text[: a.head]))
    for pat in a.grep or []:
        hits = list(re.finditer(pat, text, flags=re.I))
        print(f"## /{pat}/: {len(hits)} hits")
        for m in hits[: a.max]:
            s, e = max(0, m.start() - a.ctx), min(len(text), m.end() + a.ctx)
            print("…" + re.sub(r"\s+", " ", text[s:e]) + "…")


def cmd_fallo(a) -> None:
    body, ctype = fetch(a.url)
    text = re.sub(r"\s+", " ", to_text(body, ctype))
    idx = [m.start() for m in re.finditer(r"\bF\s?A\s?L\s?L\s?(O|AMOS)\b", text)]
    if not idx:
        print("no FALLO heading found; use text --grep")
        return
    i = idx[-1] if len(idx) > 1 and a.last else idx[0]
    print(text[i : i + a.chars])


def _fold(text: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[«»“”\"'‘’]", "", t)
    return re.sub(r"\s+", " ", t)


def cmd_quote(a) -> None:
    body, ctype = fetch(a.url)
    raw = to_text(body, ctype) if not (body[:5] == b"%PDF-" or "pdf" in ctype) else None
    pages = [raw] if raw is not None else to_text(body, ctype).split("\f")
    q = _fold(a.quote)
    for i, page in enumerate(pages, 1):
        f = _fold(page)
        j = f.find(q)
        if j >= 0:
            where = f"page {i}" if raw is None else "html"
            print(f"FOUND ({where}) · {len(a.quote.split())} words · …{f[max(0, j - 120): j + len(q) + 120]}…")
            return
    words = q.split()
    best = max(range(max(1, len(words) - 3)), key=lambda k: any(" ".join(words[k:k + 4]) in _fold(p) for p in pages), default=0)
    print(f"NOT FOUND · {len(a.quote.split())} words · first 4-word chunk present: {any(' '.join(words[best:best + 4]) in _fold(p) for p in pages)}")


def _sumario(day: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def walk(o):
        if isinstance(o, dict):
            if "titulo" in o and "identificador" in o:
                out.append((o["identificador"], o["titulo"]))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    try:
        req = urllib.request.Request(f"https://www.boe.es/datosabiertos/api/boe/sumario/{day}", headers={"Accept": "application/json", "User-Agent": UA})
        walk(json.load(urllib.request.urlopen(req, timeout=30)))
    except Exception:  # noqa: BLE001
        pass
    return out


def cmd_boe_stc(a) -> None:
    ruled = dt.date.fromisoformat(a.ruled)
    days = [(ruled + dt.timedelta(d)).strftime("%Y%m%d") for d in range(1, a.days + 1)]
    pat = re.compile(r"Sentencia " + re.escape(a.number) + r",")
    with ThreadPoolExecutor(12) as ex:
        for day, items in zip(days, ex.map(_sumario, days)):
            for ident, title in items:
                if pat.search(title):
                    print(ident, day, f"https://www.boe.es/diario_boe/txt.php?id={ident}", "|", title[:240])
                    return
    print("not found in", a.days, "days after", a.ruled)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("text")
    t.add_argument("url")
    t.add_argument("--grep", action="append")
    t.add_argument("--ctx", type=int, default=160)
    t.add_argument("--max", type=int, default=6)
    t.add_argument("--head", type=int, default=0)
    f = sub.add_parser("fallo")
    f.add_argument("url")
    f.add_argument("--chars", type=int, default=1500)
    f.add_argument("--last", action="store_true", help="use the last FALLO heading (long rulings quote earlier ones)")
    b = sub.add_parser("boe-stc")
    b.add_argument("number", help="e.g. 172/2020")
    b.add_argument("--ruled", required=True)
    b.add_argument("--days", type=int, default=70)
    qp = sub.add_parser("quote")
    qp.add_argument("url")
    qp.add_argument("quote")
    w = sub.add_parser("words")
    w.add_argument("quote")
    a = ap.parse_args()
    if a.cmd == "text":
        cmd_text(a)
    elif a.cmd == "fallo":
        cmd_fallo(a)
    elif a.cmd == "quote":
        cmd_quote(a)
    elif a.cmd == "boe-stc":
        cmd_boe_stc(a)
    else:
        print(len(a.quote.split()), "words")


if __name__ == "__main__":
    sys.exit(main())

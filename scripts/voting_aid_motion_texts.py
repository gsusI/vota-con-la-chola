#!/usr/bin/env python3
"""Link the voting aid's non-binding motions (PNL) and motions (mociones) to their official text.

Votes on «Proposiciones no de Ley» (162/…) and «Mociones consecuencia de interpelación urgente» (173/…)
carry no text link in the vote data. For each one we:

1. find its expediente with the Congreso initiative search (title words, legislature XV) and confirm the
   match because the initiative page lists the very roll-call vote (its open-data JSON path);
2. keep the BOCG serie D publications listed there (original text, amendments, approval/rejection);
3. pick the text that was actually voted, and say which one it is (``text_status``):
   - ``aprobado``: the approval notice in BOCG D ("ha acordado aprobar … en los siguientes términos"),
     i.e. the final text, transactional amendments included;
   - ``original_votado``: the original text, voted as published ("Se vota en sus términos" or no note);
   - ``original_con_enmienda``: the original text, but it was voted with an amendment incorporated
     (the amendment is published in BOCG D, linked as ``amendments_url``);
   - ``original_transaccional``: the original text, but a transactional amendment was voted and was not
     published because the motion was rejected: only the original text is available.
4. extract the dispositive part literally ("El Congreso de los Diputados insta al Gobierno a: 1… 2…").

Network results are cached under etl/data/raw/voting_aid_texts/ (initiative pages + BOCG PDFs). The link
step writes a versioned, reviewable seed (etl/data/seeds/voting_aid_motion_texts_v1.json); the highlights
exporter reads that seed and the cached PDFs, so the published text never depends on a live search.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from etl.politicos_es.config import BASE_HEADERS  # noqa: E402

SEED_SCHEMA_VERSION = "voting_aid_motion_texts_v1"
DEFAULT_SEED = BASE_DIR / "etl/data/seeds/voting_aid_motion_texts_v1.json"
DEFAULT_POOL = BASE_DIR / "ui/gh-pages-next/public/citizen/data/voting_aid_pool_v1.json"
DEFAULT_SNAPSHOT = BASE_DIR / "ui/gh-pages-next/public/citizen/data/voting_aid_generales_v1.json"
DEFAULT_HIGHLIGHTS = BASE_DIR / "ui/gh-pages-next/public/citizen/data/voting_aid_highlights_v1.json"
DEFAULT_CACHE = BASE_DIR / "etl/data/raw/voting_aid_texts"
CONGRESO = "https://www.congreso.es"
SEARCH_URL = (
    f"{CONGRESO}/es/busqueda-de-iniciativas?p_p_id=iniciativas&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view"
    "&p_p_resource_id=filtrarListado&p_p_cacheability=cacheLevelPage"
)
DETAIL_URL = (
    f"{CONGRESO}/es/busqueda-de-iniciativas?p_p_id=iniciativas&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view"
    "&_iniciativas_mode=mostrarDetalle&_iniciativas_legislatura=XV&_iniciativas_id={exp}"
)
KIND_PREFIX = {"pnl": "162", "mocion": "173"}
# Bills, constitutional and Rules reforms (proposiciones/proyectos de ley 12x, reforma constitucional 10x, Reglamento 410).
LAW_ID_RE = re.compile(r"^(1[02]\d|410)/")
MOTION_KINDS = set(KIND_PREFIX)

TEXT_STATUS_LABELS = {
    "aprobado": "Texto aprobado (publicado en el BOCG tras la votación)",
    "original_votado": "Texto original, votado en sus términos",
    "original_con_enmienda": "Texto original; se votó con una enmienda incorporada (ver enmiendas)",
    "original_transaccional": "Texto original; se votó una enmienda transaccional que no se publicó",
}

# ---------------------------------------------------------------------------
# Matching a vote to its expediente.

STOPWORDS = set(
    "sobre medidas piensa adoptar gobierno pretende garantizar relativa relativo para nuestro nuestra parte desde "
    "traves situacion politica general relacion cuanto estado espana espanoles va llevar cabo cual debe deben".split()
)


def fold(text: str) -> str:
    return unicodedata.normalize("NFKD", str(text or "").lower()).encode("ascii", "ignore").decode("ascii")


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", fold(text)))


def motion_object(expediente_text: str) -> str:
    """'Proposición no de Ley del Grupo X, sobre Y.\\nSe vota…' -> 'sobre Y.'"""
    first = " ".join(str(expediente_text or "").split("\n")[0].split())
    first = re.sub(r"\s*\(corresponde a[^)]*\)", "", first, flags=re.I)
    first = re.sub(r"^Votación (?:de conjunto|conjunta)(?: de las enmiendas a la totalidad de devolución)?(?: del texto)?(?: de la| del| al)?\s+", "", first, flags=re.I)
    first = re.sub(r"^(Proposición no de Ley|Moción consecuencia de interpelación urgente|Moción|Proposición de Ley|Proyecto de Ley|Proposición)\s*", "", first, flags=re.I)
    first = re.sub(r"^(del|de los|de la)\s+(Grupos? Parlamentari[oa]s?|Grupo)\b.*?,\s+", "", first, flags=re.I)
    return first.strip()


def voted_terms(expediente_text: str) -> str:
    m = re.search(r"Se vota[^\n]*", str(expediente_text or ""))
    return " ".join(m.group(0).split()) if m else ""


def text_status_for(approved: bool, has_approval_text: bool, terms: str) -> str:
    if approved and has_approval_text:
        return "aprobado"
    t = fold(terms)
    if "transaccional" in t:
        return "original_transaccional"
    if "enmienda" in t:
        return "original_con_enmienda"
    return "original_votado"


def search_queries(obj: str) -> list[str]:
    """Short title queries (the search fails on long ones): longest words first, then the leading words."""
    words = [w for w in re.findall(r"[\wÁÉÍÓÚÑáéíóúñü\-]+", obj) if len(w) > 3 and fold(w) not in STOPWORDS]
    ranked = sorted(words, key=lambda w: -len(w))
    out = []
    for n in (4, 3, 2):
        keep = set(ranked[:n])
        q = " ".join(w for w in words if w in keep)
        if q and q not in out:
            out.append(q)
    for q in (" ".join(words[:3]), " ".join(words[-3:])):
        if q and q not in out:
            out.append(q)
    return out


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a) - {"proposicion", "ley", "mocion", "consecuencia", "interpelacion", "urgente"}, tokens(b) - {
        "proposicion", "ley", "mocion", "consecuencia", "interpelacion", "urgente"}
    return len(ta & tb) / max(1, len(ta | tb))


# ---------------------------------------------------------------------------
# Initiative page parsing.

BOLETIN_RE = re.compile(
    r"<li>\s*<div>\s*BOCG\. Congreso de los Diputados Núm\. (?P<num>[A-Z]-[\w-]+) de (?P<date>\d{2}/\d{2}/\d{4}) "
    r"Pág\.: (?P<page>\d+)\s*<br\s*/?>\s*(?P<label>[^<]+?)\s*</div>(?P<body>.*?)</li>",
    re.S,
)
DIARIO_RE = re.compile(r"DS\. Congreso de los Diputados Núm\.\s*(?P<num>\d+) de (?P<date>\d{2}/\d{2}/\d{4}) Pág:\s*(?P<page>\d+)")
PDF_RE = re.compile(r'href="(?P<href>/public_oficiales/[^"#]+\.PDF)(?:#page=(?P<page>\d+))?"', re.I)
VOTE_JSON_RE = re.compile(r"opendata/votaciones/(Leg\d+/Sesion\d+/\d{8}/Votacion\d+)/")


def parse_initiative_page(html: str) -> dict[str, Any]:
    boletines = []
    for m in BOLETIN_RE.finditer(html):
        pdf = PDF_RE.search(m.group("body"))
        if not pdf:
            continue
        day, month, year = m.group("date").split("/")
        boletines.append({
            "bocg": m.group("num"),
            "date": f"{year}-{month}-{day}",
            "page": int(m.group("page")),
            "label": " ".join(unescape(m.group("label")).split()),
            "pdf_url": f"{CONGRESO}{pdf.group('href')}",
        })
    diarios = []
    ds_block = html[html.find("Diarios de Sesiones"):] if "Diarios de Sesiones" in html else ""
    for m in DIARIO_RE.finditer(ds_block):
        pdf = PDF_RE.search(ds_block, m.end(), m.end() + 1500)
        day, month, year = m.group("date").split("/")
        diarios.append({
            "ds": m.group("num"),
            "date": f"{year}-{month}-{day}",
            "page": int(m.group("page")),
            "pdf_url": f"{CONGRESO}{pdf.group('href')}" if pdf else None,
        })
    status = re.search(r"Concluido - \(([^)]+)\)", html)
    return {
        "boletines": boletines,
        "diarios": diarios,
        "vote_paths": sorted(set(VOTE_JSON_RE.findall(html))),
        "result": status.group(1) if status else None,
    }


def vote_path(source_url: str) -> str | None:
    m = VOTE_JSON_RE.search(str(source_url or ""))
    return m.group(1) if m else None


def choose_documents(boletines: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    def first(pred):
        return next((b for b in boletines if pred(fold(b["label"]))), None)

    return {
        "original": first(lambda l: l.startswith("iniciativa") or l.startswith("texto")),
        "approval": first(lambda l: l.startswith("aprobacion")),
        "rejection": first(lambda l: l.startswith("rechaz")),
        "amendments": first(lambda l: l.startswith("enmiendas")),
        # Bills: the latest text the Pleno could vote on (approval, committee report, ponencia report).
        "final_stage": next((b for b in reversed(boletines) if re.match(r"(aprobacion|texto aprobado|dictamen|informe de la ponencia)", fold(b["label"]))), None),
    }


# ---------------------------------------------------------------------------
# BOCG D text extraction (pdftotext -layout pages).

PAGE_NOISE_RE = re.compile(
    r"^\s*(BOLETÍN OFICIAL DE LAS CORTES GENERALES|CONGRESO DE LOS DIPUTADOS|Serie D\s+Núm\..*Pág\. \d+|cve: BOCG-[\w-]+)\s*$"
)
# Footnotes with sources ("4 https://…", "   https://…") are not part of the voted text.
FOOTNOTE_RE = re.compile(r"^\s*(?:\d{1,3}\s+)?\S*https?://\S*\s*$|^\s*\d{1,3}\s+.*https?://")
EXPEDIENTE_LINE_RE = re.compile(r"^\s*(\d{3}/\d{6})(?:/\d{4})?\s*$")
# BOCG section headings that close an expediente block (uppercase headings inside a motion text do not).
SECTION_LINE_RE = re.compile(
    r"^\s*(CONTROL DE LA ACCIÓN DEL GOBIERNO|PROPOSICIONES NO DE LEY|MOCIONES CONSECUENCIA DE INTERPELACIONES|PREGUNTAS|"
    r"INTERPELACIONES|OTROS TEXTOS|COMPOSICIÓN Y ORGANIZACIÓN DE LA CÁMARA|ACUERDOS DE LA MESA|FUNCIÓN|DECLARACIONES INSTITUCIONALES|"
    r"COMPARECENCIAS|SOLICITUDES DE)\b[A-ZÁÉÍÓÚÑ ,]*$"
)


def pdf_pages_text(pdf_path: Path, first: int, last: int) -> str:
    out = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", "-f", str(first), "-l", str(last), str(pdf_path), "-"],
        capture_output=True, check=True,
    )
    return out.stdout.decode("utf-8", errors="replace")


def paragraphs(lines: list[str]) -> list[str]:
    """Join layout lines into paragraphs: a deeper indent than the body column opens a new paragraph."""
    body = [ln for ln in lines if ln.strip()]
    if not body:
        return []
    indents = sorted(len(ln) - len(ln.lstrip(" ")) for ln in body)
    base = indents[len(indents) // 4]  # body column (most lines start here)
    paras: list[str] = []
    for ln in lines:
        if not ln.strip():
            continue
        indent = len(ln) - len(ln.lstrip(" "))
        text = ln.strip()
        if not paras or indent > base + 1 or re.match(r"^(«|\d+[.ª)]\s|[a-z]\)\s|—\s)", text):
            paras.append(text)
        else:
            prev = paras[-1]
            # "Pau-\nCanfranc" keeps its hyphen; "intervencio-\nnes" is a line-break hyphenation.
            if prev.endswith("-") and not prev.endswith(" -"):
                paras[-1] = (prev[:-1] if text[:1].islower() else prev) + text
            else:
                paras[-1] = f"{prev} {text}"
    return paras


DISPOSITIVE_START_RE = re.compile(r"«\s*El Congreso|El Congreso de los Diputados(?:,)? (?:insta|acuerda)|ha acordado|Palacio del Congreso")
# Footnote numbers sit near the left margin; superscript call marks inside the body sit far to the right.
FOOTNOTE_START_RE = re.compile(r"^ {0,24}\d{1,2}(?:\s+[^\d\s.ºª)]|\s*$)")


def strip_footnotes(lines: list[str]) -> list[str]:
    """Drop a page's bottom footnote block ("4 Fuente…, https://…"): from the first footnote-looking line to the
    page end, only when that block cites a link (so numbered body text is never cut)."""
    for i, ln in enumerate(lines):
        if FOOTNOTE_START_RE.match(ln):
            tail = "\n".join(lines[i:])
            if "http" in tail and not EXPEDIENTE_LINE_RE.search(tail) and not DISPOSITIVE_START_RE.search(tail):
                return lines[:i]
    return lines


def expediente_segment(page_text: str, expediente: str, listed_page_index: int | None = None) -> list[str]:
    """Lines of the block for one expediente: from its header line (the last one at or before the listed
    page, since amendments and the approval notice share one header) to the next expediente/section header."""
    pages = page_text.split("\f")
    lines: list[str] = []
    header_lines: list[tuple[int, int]] = []  # (line index, page index)
    for pi, page in enumerate(pages):
        for ln in strip_footnotes(page.split("\n")):
            if PAGE_NOISE_RE.match(ln) or FOOTNOTE_RE.match(ln):
                continue
            m = EXPEDIENTE_LINE_RE.match(ln)
            if m and m.group(1) == expediente:
                header_lines.append((len(lines), pi))
            lines.append(ln)
    if not header_lines:
        return []
    eligible = [h for h in header_lines if listed_page_index is None or h[1] <= listed_page_index]
    start = (eligible[-1] if eligible else header_lines[0])[0]
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = EXPEDIENTE_LINE_RE.match(lines[j])
        alias = m and all(EXPEDIENTE_LINE_RE.match(x) or not x.strip() for x in lines[start + 1:j])  # "162/… 161/…" header pair
        if (m and m.group(1) != expediente and not alias) or SECTION_LINE_RE.match(lines[j]):
            end = j
            break
    return lines[start + 1:end]


def quoted_block(text: str, start: int) -> str | None:
    """Text inside the «…» that opens at or after `start`, honouring nested quotes. Never runs past the
    signature ("Palacio del Congreso…"), so an unbalanced quote cannot swallow the amendments that follow."""
    i = text.find("«", start)
    if i < 0:
        return None
    sig = text.find("Palacio del Congreso de los Diputados", i)
    stop = sig if sig > 0 else len(text)
    depth = 0
    for j in range(i, stop):
        # Inner quotes mix styles (“… », «… ”): count both families together so they stay balanced.
        if text[j] in "«“":
            depth += 1
        elif text[j] in "»”":
            depth -= 1
            if depth == 0:
                # Not the end of the block if more numbered points follow (quote closed inside a spilled
                # footnote) or the sentence goes on (an inner “… » mixing quote styles).
                after = text[j + 1:j + 240]
                if re.match(r"[.,;]?\s*:?\s*(?:\S*https?://[^\n]*)?\n\s*\d{1,2}\.\s", after) or re.match(r" [a-záéíóúñü]", after):
                    depth = 1
                    continue
                return text[i + 1:j]
    return text[i + 1:stop].rstrip().rstrip("»")


APPROVAL_RE = re.compile(r"ha (?:acordado (?:aprobar|lo siguiente)|aprobado (?:la|el)\b)", re.S)
APPROVAL_AS_IS_RE = re.compile(r"en sus (?:propios )?términos")
DISPOSITIVE_RE = re.compile(r"«\s*(?:El|1\.)\s*(?:Congreso de los Diputados|Pleno)?", re.S)


def dispositive_text(segment_lines: list[str], mode: str) -> str | None:
    """The literal dispositive part: approved terms (mode 'approval') or the original proposal."""
    joined = "\n".join(paragraphs(segment_lines))
    if mode == "approval":
        m = APPROVAL_RE.search(joined)
        if not m:
            return None
        # The approved text is the quote opened right after a colon ("…en los siguientes términos:");
        # quotes inside the title («BOCG. Congreso…», «bibliocausto») are skipped.
        q = next((x.start() for x in re.finditer(r":\s*«", joined[m.end():m.end() + 1600])), None)
        if q is not None:
            q = joined.find("«", m.end() + q)
        else:
            q = joined.find("«", m.end())
            while q >= 0 and joined[q + 1:q + 12].lstrip().startswith("BOCG"):
                q = joined.find("«", q + 1)
        lead = joined[m.end():q if q >= 0 else len(joined)]
        # Approved "en sus términos" without quoting it: the original publication has the text.
        if q < 0 or q - m.end() > 1500 or (APPROVAL_AS_IS_RE.search(lead) and not lead.rstrip().endswith(":")):
            return None
        return quoted_block(joined, q)
    # Original: the first quoted «El Congreso…» after the explanatory memorandum (amendments, published in the
    # same block for mociones, come after the motion's own signature).
    m = re.search(r"Exposición de motivos|presenta(?:n)? la siguiente", joined)
    after = m.end() if m else 0
    starts = [x.start() for x in re.finditer(r"«\s*El Congreso", joined[after:])] or [x.start() for x in DISPOSITIVE_RE.finditer(joined[after:])]
    if starts:
        return quoted_block(joined, after + starts[0])
    # Unquoted dispositive: from "El Congreso de los Diputados insta/acuerda…" to the signature.
    m = UNQUOTED_RE.search(joined, after)
    if m:
        end = joined.find("Palacio del Congreso de los Diputados", m.start())
        return joined[m.start():end if end > 0 else len(joined)]
    # Otherwise the quoted block that ends right before the proposal's signature («Por la que se insta…»).
    sig = joined.find("Palacio del Congreso de los Diputados", after)
    close = joined.rfind("»", after, sig if sig > 0 else len(joined))
    if close < 0 or (sig > 0 and joined[close:sig].strip(" .\n»") != ""):
        return None
    depth = 0
    for i in range(close, after - 1, -1):
        if joined[i] == "»":
            depth += 1
        elif joined[i] == "«":
            depth -= 1
            if depth == 0:
                return joined[i + 1:close]
    return None


UNQUOTED_RE = re.compile(r"^El Congreso de los Diputados (?:insta|acuerda|manifiesta|exige|reconoce|reitera|rechaza|condena|declara|muestra|expresa|se compromete|reafirma|considera)", re.M)
POINT_RE = re.compile(r"^(?P<n>\d{1,2})[.ª)]\s+")
SUBPOINT_RE = re.compile(r"^(?:[a-zñ]\)|[ivx]+\)|—|-|•)\s+")


def split_points(dispositive: str) -> dict[str, Any]:
    """Split '«El Congreso … insta al Gobierno a: 1. … 2. …»' into its intro and literal numbered points."""
    paras = [p.strip() for p in dispositive.split("\n") if p.strip()]
    intro: list[str] = []
    points: list[dict[str, str]] = []
    for p in paras:
        m = POINT_RE.match(p)
        if m:
            points.append({"n": m.group("n"), "text": p[m.end():].strip()})
        elif points and SUBPOINT_RE.match(p):
            points[-1]["text"] += " " + p
        elif points:
            points[-1]["text"] += " " + p
        else:
            intro.append(p)
    if not points:
        # Unnumbered: each paragraph after the intro is one point, literally.
        body = paras[1:] if len(paras) > 1 and paras[0].rstrip().endswith(":") else paras
        intro = paras[:1] if body is not paras else []
        points = [{"n": str(i), "text": p} for i, p in enumerate(body, 1)]
    clean = lambda s: drop_footnote_spill(re.sub(r"\s+", " ", s).strip())  # noqa: E731
    return {"intro": clean(" ".join(intro)), "points": [{"n": p["n"], "text": clean(p["text"])} for p in points]}


def drop_footnote_spill(text: str) -> str:
    """A footnote continued from the previous page (no number; its link line is already dropped) can land
    inside a point. Legal points never resume after a full stop in lower case, except lettered sub-points
    ("… b) …", "… c. …") and abbreviations: cut there."""
    for m in SPILL_RE.finditer(text):
        if m.group(1).lower().strip("(«\"") in ABBREVIATIONS or m.group(1)[-1:].isdigit():
            continue
        return text[:m.start(1) + len(m.group(1)) + 1]
    return re.sub(r"\s*\S*https?://.*$", "", text).rstrip()


SPILL_RE = re.compile(r"(\S+)\.\s+(?![a-zñ][.)]\s)[a-záéíóúñü]{2,}")
ABBREVIATIONS = {"art", "arts", "núm", "pág", "etc", "sr", "sra", "ss", "apdo", "cap", "vol", "pp", "ej", "aprox", "uu", "dña", "vid"}


def extract_motion_text(pdf_path: Path, page: int, expediente: str, mode: str, span: int = 14, back: int = 12) -> dict[str, Any] | None:
    first = max(1, page - back)
    seg = expediente_segment(pdf_pages_text(pdf_path, first, page + span), expediente, page - first)
    if not seg:
        return None
    disp = dispositive_text(seg, mode)
    if not disp:
        return None
    return split_points(disp)


# ---------------------------------------------------------------------------
# Network (cached) helpers.

def _request(url: str, data: bytes | None = None, extra: dict[str, str] | None = None, timeout: int = 90) -> bytes:
    headers = {**BASE_HEADERS, **(extra or {})}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def list_type(tipo: str, cache_dir: Path, timeout: int, sleep: float) -> list[dict[str, Any]]:
    """Every XV initiative of one type (e.g. 173 = mociones), page by page; cached per page."""
    out: list[dict[str, Any]] = []
    page, total = 1, None
    while total is None or len(out) < total:
        path = cache_dir / "initiatives" / f"list_{tipo}_p{page:03d}.json"

        def get(page=page) -> bytes:
            data = urllib.parse.urlencode({"_iniciativas_legislatura": "15", "_iniciativas_tipo": tipo, "_iniciativas_paginaActual": str(page)}).encode()
            raw = _request(SEARCH_URL, data, {
                "X-Requested-With": "XMLHttpRequest", "Origin": CONGRESO, "Referer": f"{CONGRESO}/es/busqueda-de-iniciativas",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            }, timeout)
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


def search_initiatives(query: str, timeout: int) -> list[dict[str, Any]]:
    data = urllib.parse.urlencode({"_iniciativas_legislatura": "15", "_iniciativas_titulo": query, "_iniciativas_paginaActual": "1"}).encode()
    raw = _request(SEARCH_URL, data, {
        "X-Requested-With": "XMLHttpRequest", "Origin": CONGRESO, "Referer": f"{CONGRESO}/es/busqueda-de-iniciativas",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }, timeout)
    return list((json.loads(raw).get("lista_iniciativas") or {}).values())


def cached(path: Path, fetch) -> bytes:
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def initiative_page(exp: str, cache_dir: Path, timeout: int) -> str:
    path = cache_dir / "initiatives" / f"{exp.replace('/', '_')}.html"
    data = cached(path, lambda: _request(DETAIL_URL.format(exp=urllib.parse.quote(exp, safe="")), timeout=timeout))
    return data.decode("utf-8", errors="replace")


def pdf_cache_path(url: str, cache_dir: Path) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.pdf"


def fetch_pdf(url: str, cache_dir: Path, timeout: int) -> Path:
    path = pdf_cache_path(url, cache_dir)

    def get() -> bytes:
        data = _request(url, timeout=timeout)
        if not data.startswith(b"%PDF"):
            raise ValueError(f"no es un PDF: {url}")
        return data

    cached(path, get)
    return path


# ---------------------------------------------------------------------------
# Link step: votes -> expedientes -> BOCG D documents (writes the seed).

def vote_kind(title: str) -> str:
    title = str(title or "")
    if title.startswith("Proposición no de Ley"):
        return "pnl"
    if title.startswith("Moción"):
        return "mocion"
    return "final" if title.startswith("Votación de conjunto") else "ley"


def target_votes(pool: dict[str, Any], snapshot: dict[str, Any], highlights: dict[str, Any], db: sqlite3.Connection,
                 keep: set[str] | None = None) -> list[dict[str, Any]]:
    """Motions (always), votes already in the seed (`keep`) and any other question vote without an official text."""
    keep = keep or set()
    have = set((highlights or {}).get("by_vote") or {}) - keep
    targets: dict[str, dict[str, Any]] = {}
    for it in pool.get("items") or []:
        kind = it.get("kind")
        if kind in MOTION_KINDS or it["vote_event_id"] not in have:
            targets[it["vote_event_id"]] = {"kind": kind, "approved": bool(it.get("approved")), "source_url": it.get("source_url")}
    for st in snapshot.get("statements") or []:
        for v in st.get("votes") or []:
            kind = vote_kind(v.get("title"))
            if kind in MOTION_KINDS or v["vote_event_id"] not in have:
                totals = v.get("totals") or {}
                targets[v["vote_event_id"]] = {"kind": kind, "approved": (totals.get("yes") or 0) > (totals.get("no") or 0), "source_url": v.get("source_url")}
    out = []
    for vid, t in targets.items():
        row = db.execute("SELECT expediente_text, vote_date, source_url FROM parl_vote_events WHERE vote_event_id = ?", (vid,)).fetchone()
        if not row:
            continue
        out.append({"vote_event_id": vid, **t, "expediente_text": row[0], "vote_date": row[1], "source_url": t["source_url"] or row[2]})
    return sorted(out, key=lambda x: x["vote_event_id"])


def candidate_ok(kind: str, initiative_id: str) -> bool:
    return initiative_id.startswith(KIND_PREFIX[kind]) if kind in KIND_PREFIX else bool(LAW_ID_RE.match(initiative_id))


def link_one(v: dict[str, Any], cache_dir: Path, timeout: int, sleep: float, previous: dict[str, Any] | None) -> dict[str, Any]:
    obj = motion_object(v["expediente_text"])
    exp = (previous or {}).get("expediente")
    candidates: list[str] = [exp] if exp else []
    if not candidates:
        for q in search_queries(obj):
            try:
                found = search_initiatives(q, timeout)
            except Exception:  # noqa: BLE001 - the search answers 5xx when nothing matches
                time.sleep(sleep)
                continue
            ranked = sorted((x for x in found if candidate_ok(v["kind"], str(x.get("id_iniciativa", "")))), key=lambda x: -similarity(obj, x.get("titulo", "")))
            candidates = [x["id_iniciativa"] for x in ranked[:3]]
            time.sleep(sleep)
            if candidates:
                break
    if not candidates and v["kind"] == "mocion":
        # Few mociones per legislature: rank the full 173 list locally.
        found = list_type("173", cache_dir, timeout, sleep)
        ranked = sorted(found, key=lambda x: -similarity(obj, x.get("titulo", "")))
        candidates = [x["id_iniciativa"] for x in ranked[:3]]
    want = vote_path(v["source_url"])
    for exp in candidates:
        page = parse_initiative_page(initiative_page(exp, cache_dir, timeout))
        if want and want in page["vote_paths"]:
            docs = choose_documents(page["boletines"])
            return {
                "kind": v["kind"], "expediente": exp, "vote_date": v["vote_date"], "approved": v["approved"],
                "voted_terms": voted_terms(v["expediente_text"]), "object": obj,
                "initiative_url": DETAIL_URL.format(exp=exp), "match": "vote_listed_on_initiative_page",
                "boletines": page["boletines"], "diarios": page["diarios"], **{f"{k}_doc": d for k, d in docs.items()},
            }
    return {"kind": v["kind"], "expediente": None, "vote_date": v["vote_date"], "approved": v["approved"],
            "voted_terms": voted_terms(v["expediente_text"]), "object": obj, "candidates": candidates, "match": "not_found"}


def cmd_link(args: argparse.Namespace) -> int:
    pool = json.loads(Path(args.pool).read_text(encoding="utf-8"))
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    db = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    seed_path = Path(args.seed)
    previous = json.loads(seed_path.read_text(encoding="utf-8")).get("votes", {}) if seed_path.exists() else {}
    highlights = json.loads(Path(args.highlights).read_text(encoding="utf-8")) if Path(args.highlights).exists() else {}
    votes = target_votes(pool, snapshot, highlights, db, keep=set(previous))
    hints = json.loads(Path(args.hints).read_text(encoding="utf-8")) if args.hints else {}
    for vid, h in hints.items():
        if h.get("id_iniciativa") and not (previous.get(vid) or {}).get("expediente"):
            previous[vid] = {"expediente": h["id_iniciativa"]}
    cache_dir = Path(args.cache_dir)
    results: dict[str, Any] = {}

    def work(v: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        try:
            r = link_one(v, cache_dir, args.timeout, args.sleep, previous.get(v["vote_event_id"]))
            if r.get("expediente") is None and (previous.get(v["vote_event_id"]) or {}).get("expediente"):
                r = link_one(v, cache_dir, args.timeout, args.sleep, None)  # stale hint: search again
        except Exception as exc:  # noqa: BLE001
            r = {"kind": v["kind"], "expediente": None, "match": "error", "error": f"{type(exc).__name__}: {exc}"[:200]}
        return v["vote_event_id"], r

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for vid, r in ex.map(work, votes):
            results[vid] = r
            print(f"{r['kind']:6} {r.get('expediente') or '-':12} {r['match']}", flush=True)
    payload = {
        "meta": {
            "schema_version": SEED_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "method": (
                "Expediente buscado en el buscador de iniciativas del Congreso (XV) y confirmado porque la ficha de la "
                "iniciativa enlaza la misma votación nominal. Boletines BOCG serie D y Diarios de Sesiones tal y como los lista la ficha."
            ),
            "votes": len(results),
            "linked": sum(1 for r in results.values() if r.get("expediente")),
        },
        "votes": dict(sorted(results.items())),
    }
    seed_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"OK seed -> {seed_path.relative_to(BASE_DIR) if seed_path.is_relative_to(BASE_DIR) else seed_path} "
          f"(votes={len(results)} linked={payload['meta']['linked']})")
    return 0


# ---------------------------------------------------------------------------
# Document step (used by export_voting_aid_highlights): seed entry -> highlight doc.

def motion_document(entry: dict[str, Any], cache_dir: Path, *, timeout: int = 60, offline: bool = False) -> dict[str, Any]:
    """Build the highlight document for one linked motion vote (raises if the text cannot be extracted)."""
    exp = entry["expediente"]
    approval, original = entry.get("approval_doc"), entry.get("original_doc")
    status = text_status_for(bool(entry.get("approved")), bool(approval), entry.get("voted_terms") or "")
    extracted, doc = None, None
    if status == "aprobado":
        path = pdf_cache_path(approval["pdf_url"], cache_dir) if offline else fetch_pdf(approval["pdf_url"], cache_dir, timeout)
        extracted = extract_motion_text(path, approval["page"], exp, "approval")
        doc = approval
        if extracted is None:  # approved "en sus términos": the voted text is the original one
            status = "original_votado"
    if extracted is None:
        # A rejection notice "cuyo texto se inserta a continuación" carries the text when no original is listed.
        original = original or entry.get("rejection_doc")
        if not original:
            raise ValueError(f"{exp}: sin publicación original en la ficha")
        path = pdf_cache_path(original["pdf_url"], cache_dir) if offline else fetch_pdf(original["pdf_url"], cache_dir, timeout)
        extracted = extract_motion_text(path, original["page"], exp, "original")
        doc = original
    if not extracted or not extracted["points"]:
        raise ValueError(f"{exp}: no se encontró la parte dispositiva en {doc['bocg']} pág. {doc['page']}")
    data = path.read_bytes()
    amend = entry.get("amendments_doc")
    return {
        "url": f"{doc['pdf_url']}#page={doc['page']}",
        "source": "BOCG",
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "expediente": exp,
        "bocg": f"BOCG Congreso D-{doc['bocg'].split('-', 1)[1]} ({doc['date']}), pág. {doc['page']}",
        "text_status": status,
        "text_status_label": TEXT_STATUS_LABELS[status],
        "voted_terms": entry.get("voted_terms") or "",
        "amendments_url": f"{amend['pdf_url']}#page={amend['page']}" if amend and status != "aprobado" else None,
        "intro": extracted["intro"],
        "points": extracted["points"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    link = sub.add_parser("link", help="Buscar expedientes y boletines (red + base de votaciones) y escribir la semilla")
    link.add_argument("--db", required=True, help="SQLite con parl_vote_events del Congreso XV")
    link.add_argument("--pool", default=str(DEFAULT_POOL))
    link.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    link.add_argument("--seed", default=str(DEFAULT_SEED))
    link.add_argument("--highlights", default=str(DEFAULT_HIGHLIGHTS), help="Votaciones que ya tienen texto (no se buscan, salvo PNL/mociones)")
    link.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    link.add_argument("--hints", help="JSON opcional vote_event_id -> {id_iniciativa} para evitar búsquedas")
    link.add_argument("--workers", type=int, default=3)
    link.add_argument("--timeout", type=int, default=120)
    link.add_argument("--sleep", type=float, default=0.5)
    args = parser.parse_args(argv)
    return cmd_link(args)


if __name__ == "__main__":
    raise SystemExit(main())

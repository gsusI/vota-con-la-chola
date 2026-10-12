#!/usr/bin/env python3
"""Extract "what is really inside" each voted text for the voting aid, from the official text.

Titles can hide omnibus contents (a decree-law "on transport" that also changes tax law or the
postal service). For every vote behind a question we fetch the official text and keep only its
own structure, literally: titles/chapters, article headings, the other laws it modifies (riders
in final provisions included) and an omnibus flag. No summarising or interpretation.

Sources: decree-laws from the BOE (ELI XML, built from "Real Decreto-ley N/YYYY, de D de mes"),
bills from the BOCG PDF linked to the vote. Votes without a linked text (non-binding motions, motions,
and bills whose vote carries no link) come from the seed written by scripts/voting_aid_motion_texts.py:
for motions the literal points of the BOCG serie D text that was voted (approved text when published,
otherwise the original, labelled), for bills the BOCG text listed on the initiative page. Raw downloads
are cached under etl/data/raw/voting_aid_texts/ and every document records URL and SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from etl.politicos_es.http import http_get_bytes  # noqa: E402
from scripts.export_voting_aid_pool import theme_for  # noqa: E402
from scripts import voting_aid_motion_texts as motions  # noqa: E402

DEFAULT_SNAPSHOT = BASE_DIR / "ui/gh-pages-next/public/citizen/data/voting_aid_generales_v1.json"
DEFAULT_POOL = BASE_DIR / "ui/gh-pages-next/public/citizen/data/voting_aid_pool_v1.json"
DEFAULT_OUT = BASE_DIR / "ui/gh-pages-next/public/citizen/data/voting_aid_highlights_v1.json"
DEFAULT_CACHE = BASE_DIR / "etl/data/raw/voting_aid_texts"
DEFAULT_MOTION_SEED = motions.DEFAULT_SEED
SCHEMA_VERSION = "voting_aid_highlights_v1"

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
RDL_RE = re.compile(r"Real Decreto-ley (\d+)/(\d{4}), de (\d{1,2}) de (\w+)", re.I)

# Omnibus: one vote whose title, blocks and modified norms span 3+ distinct themes.
# Off-topic riders: laws changed through final provisions whose theme is neither the title's nor the blocks'.
OMNIBUS_MIN_THEMES = 3
MAX_ITEMS = 10
MAX_LEN = 160

BOILERPLATE_RE = re.compile(
    r"^(objeto|ámbito|definiciones|entrada en vigor|títulos? competencial|facultades de desarrollo|habilitación|"
    r"desarrollo reglamentario|salvaguardia|normas? derogad|derogación|modificaciones presupuestarias|aspectos financieros|"
    r"beneficiarios|control|procedimiento de concesión|régimen jurídico|financiación|información, comunicación|"
    r"obligaciones de información|compatibilidad|gestión de las ayudas|liquidación|cofinanciación|afectación|importe|cuantía|"
    r"criterios|actuaciones subvencionables|plazo|vigencia|referencias)",
    re.I,
)
MODIFIES_RE = re.compile(r"^Modificaci[oó]n (?:del|de la|de los|de las) (.+)$", re.I)
CHANGE_RE = re.compile(
    r"^(Uno|Dos|Tres|Cuatro|Cinco|Seis|Siete|Ocho|Nueve|Diez|Once|Doce)\.\s+(Se (?:modifica|añade|añaden|introduce|suprime|deroga|incorpora|da nueva redacción)[^.]{0,200})",
    re.I,
)


def clip(text: str, n: int = MAX_LEN) -> str:
    text = " ".join(str(text or "").split()).strip().rstrip(".")
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def rdl_eli_url(title: str) -> str | None:
    m = RDL_RE.search(title or "")
    if not m:
        return None
    num, year, day, month = m.group(1), int(m.group(2)), int(m.group(3)), MONTHS.get(m.group(4).lower())
    if not month:
        return None
    return f"https://www.boe.es/eli/es/rdl/{year}/{month:02d}/{day:02d}/{int(num)}/dof/spa/xml"


def short_norm(text: str) -> str:
    # "Ley 34/2002, de 11 de julio, de servicios de la sociedad de la información y ..." -> kept, clipped.
    return clip(re.sub(r"\s*\(.*?\)\s*", " ", text), 120)


def finalize(blocks: list[str], articles: list[str], changes: list[str], modified: list[str], riders: list[str]) -> dict[str, Any]:
    def uniq(seq: list[str]) -> list[str]:
        seen, out = set(), []
        for s in seq:
            k = s.lower()
            if s and k not in seen:
                seen.add(k)
                out.append(s)
        return out

    blocks, articles, changes, modified, riders = map(uniq, (blocks, articles, changes, modified, riders))
    if blocks:
        bullets, basis = blocks, "bloques"
    elif changes:
        bullets, basis = changes, "cambios"
    elif articles:
        bullets, basis = articles, "artículos"
    else:
        bullets, basis = [f"Modifica: {m}" for m in modified], "normas"
    block_themes = sorted({t for t in (theme_for(x) for x in blocks + articles[:20]) if t != "Otros"})
    return {
        "bullets": bullets[:MAX_ITEMS],
        "bullets_basis": basis,
        "bullets_total": len(bullets),
        "modified_norms": modified[:MAX_ITEMS],
        "modified_norms_total": len(modified),
        "riders": riders[:MAX_ITEMS],
        "riders_total": len(riders),
        "block_themes": block_themes,
        "stats": {"blocks": len(blocks), "articles": len(articles), "modified_norms": len(modified), "riders": len(riders)},
    }


def parse_boe_xml(data: bytes) -> dict[str, Any]:
    root = ET.fromstring(data)
    texto = root.find("texto")
    if texto is None:
        raise ValueError("BOE XML sin <texto>")
    blocks: list[str] = []
    articles: list[str] = []
    modified: list[str] = []
    riders: list[str] = []
    pending_titulo = None
    titulo_has_capitulos = False
    for p in texto.iter("p"):
        cls = p.get("class") or ""
        text = " ".join("".join(p.itertext()).split())
        if cls == "titulo_tit":
            if pending_titulo and not titulo_has_capitulos:
                blocks.append(pending_titulo)
            pending_titulo, titulo_has_capitulos = clip(text), False
        elif cls == "capitulo_tit":
            titulo_has_capitulos = True
            blocks.append(clip(text))
        elif cls == "articulo" and not text.startswith(("«", '"', "“")):
            m = re.match(r"^((?:Artículo|Disposición (?:adicional|transitoria|final|derogatoria))[^.]*)\.\s*(.+)$", text)
            if not m:
                continue
            label, heading = m.group(1), m.group(2)
            mod = MODIFIES_RE.match(heading)
            if mod:
                norm = short_norm(mod.group(1))
                modified.append(norm)
                if label.startswith("Disposición final"):
                    riders.append(norm)
            elif label.startswith("Artículo") and not BOILERPLATE_RE.match(heading):
                articles.append(clip(heading))
    if pending_titulo and not titulo_has_capitulos:
        blocks.append(pending_titulo)
    return finalize(blocks, articles, [], modified, riders)


NOISE_RE = re.compile(
    r"(BOLETÍN OFICIAL DE LAS CORTES GENERALES|CONGRESO DE LOS DIPUTADOS|XV LEGISLATURA|Serie [AB]:? [A-ZÁÉÍÓÚ ]*|"
    r"Serie [AB] Núm\. [\d-]+ \d+ de \w+ de \d{4} Pág\. \d+|Núm\. [\d-]+ Pág\. \d+|cve: BOCG-[\w-]+)"
)
ORDINALS = r"(?:\d+(?: bis)?|(?i:único|primero|segundo|tercero|cuarto|quinto|sexto|séptimo|octavo|noveno|décimo|undécimo|duodécimo))"
STRUCT_RE = re.compile(
    r"(?<![«\"“])\b(?P<label>Artículo " + ORDINALS + r"|Disposición (?:adicional|transitoria|final|derogatoria) [a-záéíóú]+(?: [a-záéíóú]+)?)\.\s+"
    r"(?P<head>[A-ZÁÉÍÓÚÑ][^.]{2,200})\."
)
SECTION_RE = re.compile(r"(?<![«\"“])\b(TÍTULO|CAPÍTULO) (?:[IVXLC]+|PRELIMINAR|ÚNICO)\.?\s+(?P<title>[A-ZÁÉÍÓÚÑ][^.]{3,160}?)(?=\s+(?:Artículo|CAPÍTULO|Sección)\b)")
CHANGE_TEXT_RE = re.compile(
    r"\b(?:Uno|Dos|Tres|Cuatro|Cinco|Seis|Siete|Ocho|Nueve|Diez|Once|Doce|Trece|Catorce|Quince)\.\s+"
    r"(?P<what>Se (?:modifica|modifican|añade|añaden|introduce|introducen|suprime|suprimen|deroga|derogan|incorpora|incorporan|da nueva redacción a)\b[^.:]{0,220}?)"
    r"(?:,\s*(?:que|el cual|la cual|con la siguiente|en los siguientes)|:|\.)"
)
QUOTED_HEAD_RE = re.compile(r"«\s*(?P<label>Artículo [\w ]+?|Disposición [\w ]+?)\.\s+(?P<head>[A-ZÁÉÍÓÚÑ][^.«»]{2,120})\.")


def parse_bocg_text(text: str) -> dict[str, Any]:
    joined = " ".join(text.split())
    joined = NOISE_RE.sub(" ", joined)
    joined = " ".join(joined.split())
    # Skip the explanatory memorandum: the articulado starts at the first real heading after it.
    m = re.search(r"(Exposición de motivos|EXPOSICIÓN DE MOTIVOS|Preámbulo|PREÁMBULO)", joined)
    body = joined[m.end():] if m else joined
    first = [x.start() for x in (STRUCT_RE.search(body), SECTION_RE.search(body), CHANGE_TEXT_RE.search(body)) if x]
    body = body[min(first):] if first else body

    blocks = [clip(x.group("title")) for x in SECTION_RE.finditer(body)]
    articles: list[str] = []
    modified: list[str] = []
    riders: list[str] = []
    for x in STRUCT_RE.finditer(body):
        label, head = x.group("label"), x.group("head")
        mod = MODIFIES_RE.match(head)
        if mod:
            norm = short_norm(mod.group(1))
            modified.append(norm)
            if label.startswith("Disposición final"):
                riders.append(norm)
        elif label.startswith("Artículo") and not BOILERPLATE_RE.match(head):
            articles.append(clip(head))
    changes: list[str] = []
    for x in CHANGE_TEXT_RE.finditer(body):
        what = clip(re.sub(r"\s*«.*$", "", x.group("what")), 140)
        q = QUOTED_HEAD_RE.search(body, x.end(), x.end() + 600)
        if q:
            what = f"{what} ({clip(q.group('label'), 40)}: {clip(q.group('head'), 90)})"
        changes.append(what)
    return finalize(blocks, articles, changes, modified, riders)


def fetch_cached(url: str, cache_dir: Path, *, timeout: int, sleep: float) -> tuple[bytes, str, bool]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    ext = ".xml" if url.endswith("/xml") else ".pdf"
    path = cache_dir / f"{key}{ext}"
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes(), str(path), True
    data, _ctype = http_get_bytes(url, timeout)
    if not data or data[:15].lower().startswith((b"<!doctype html", b"<html")):
        raise ValueError("respuesta HTML en lugar del documento")
    path.write_bytes(data)
    time.sleep(sleep)
    return data, str(path), False


def pdf_to_text(path: str) -> str:
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", path, "-"], capture_output=True, check=True)
    return out.stdout.decode("utf-8", errors="replace")


def classify_scope(parsed: dict[str, Any], title: str) -> dict[str, Any]:
    """Add omnibus flag and off-topic riders, judged against the voted title and the text's own blocks."""
    title_theme = theme_for(title)
    main = set(parsed.get("block_themes") or [])
    if title_theme != "Otros":
        main.add(title_theme)
    norm_themes = {theme_for(n) for n in parsed.get("modified_norms") or []} - {"Otros"}
    themes = sorted(main | norm_themes)
    offtopic = [r for r in parsed.get("riders") or [] if theme_for(r) not in main and theme_for(r) != "Otros"]
    return {**parsed, "themes": themes, "omnibus": len(themes) >= OMNIBUS_MIN_THEMES, "offtopic_riders": offtopic}


TEXT_STATUS_LABELS = {
    **motions.TEXT_STATUS_LABELS,
    "boe": "Texto publicado en el BOE",
    "texto_inicial": "Texto inicial, tal como se presentó (antes de enmiendas)",
    "texto_tramitado": "Texto tras su paso por la Comisión o aprobado por el Pleno",
}


def bocg_text_status(url: str) -> str:
    # BOCG series A/B: "-1.PDF" is the text as presented; later numbers are reports, opinions and approvals.
    return "texto_inicial" if re.search(r"/BOCG-\d+-[AB]-\d+-1\.PDF", url, re.I) else "texto_tramitado"


def motion_highlight(entry: dict[str, Any], title: str, cache_dir: Path, *, timeout: int, offline: bool) -> dict[str, Any]:
    doc = motions.motion_document(entry, cache_dir, timeout=timeout, offline=offline)
    points = doc.pop("points")
    bullets = [clip(f"{p['n']}. {p['text']}") for p in points]
    # A motion is a list of requests, not a law carrying riders: it is never flagged omnibus
    # (keyword themes over free-text points would be noise).
    parsed = {
        "bullets": bullets[:MAX_ITEMS], "bullets_basis": "puntos", "bullets_total": len(bullets),
        "modified_norms": [], "modified_norms_total": 0, "riders": [], "riders_total": 0,
        "block_themes": [], "stats": {"points": len(points)},
    }
    scoped = classify_scope(parsed, title)
    return {**doc, **scoped, "points": points}


def law_highlight(entry: dict[str, Any], title: str, cache_dir: Path, *, timeout: int, offline: bool) -> dict[str, Any]:
    pick = (entry.get("final_stage_doc") if entry.get("kind") == "final" else None) or entry.get("original_doc") or entry.get("final_stage_doc")
    if not pick:
        raise ValueError(f"{entry.get('expediente')}: la ficha no lista ningún texto en el BOCG")
    url = pick["pdf_url"]
    path = motions.pdf_cache_path(url, cache_dir) if offline else motions.fetch_pdf(url, cache_dir, timeout)
    data = path.read_bytes()
    parsed = classify_scope(parse_bocg_text(pdf_to_text(str(path))), title)
    status = bocg_text_status(url)
    return {
        "url": url, "source": "BOCG", "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
        "expediente": entry.get("expediente"), "text_status": status, "text_status_label": TEXT_STATUS_LABELS[status],
        **parsed,
    }


def vote_documents(snapshot: dict[str, Any], pool: dict[str, Any]) -> dict[str, dict[str, str]]:
    """vote_event_id -> {url, kind} for every vote behind a question that has an official text."""
    out: dict[str, dict[str, str]] = {}

    def add(vid: str, title: str, text_url: str | None) -> None:
        eli = rdl_eli_url(title)
        if eli:
            out[vid] = {"url": eli, "kind": "boe", "title": title}
        elif text_url:
            out[vid] = {"url": text_url.split("#", 1)[0], "kind": "bocg", "title": title}

    for st in snapshot.get("statements") or []:
        for v in st.get("votes") or []:
            add(v["vote_event_id"], v.get("title") or "", v.get("text_url"))
    for it in pool.get("items") or []:
        add(it["vote_event_id"], it.get("title") or "", it.get("text_url"))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--pool", default=str(DEFAULT_POOL))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    parser.add_argument("--motion-seed", default=str(DEFAULT_MOTION_SEED), help="Semilla de PNL/mociones y leyes sin enlace (voting_aid_motion_texts.py link)")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--sleep", type=float, default=0.4, help="Pausa entre descargas nuevas (cortesía con el origen)")
    parser.add_argument("--offline", action="store_true", help="Usar solo la caché local")
    args = parser.parse_args(argv)

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    pool = json.loads(Path(args.pool).read_text(encoding="utf-8"))
    targets = vote_documents(snapshot, pool)
    cache_dir = Path(args.cache_dir)
    seed_path = Path(args.motion_seed)
    seed_votes = json.loads(seed_path.read_text(encoding="utf-8")).get("votes", {}) if seed_path.exists() else {}
    titles = {it["vote_event_id"]: it.get("title") or "" for it in pool.get("items") or []}
    for st in snapshot.get("statements") or []:
        for v in st.get("votes") or []:
            titles.setdefault(v["vote_event_id"], v.get("title") or "")

    docs: dict[str, Any] = {}
    by_vote: dict[str, str] = {}
    failures: list[dict[str, str]] = []
    for vid, target in sorted(targets.items()):
        url = target["url"]
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        by_vote[vid] = key
        if key in docs:
            continue
        try:
            if args.offline:
                path = cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}{'.xml' if url.endswith('/xml') else '.pdf'}"
                if not path.exists():
                    raise FileNotFoundError("no está en caché")
                data, cached = path.read_bytes(), True
                path_s = str(path)
            else:
                data, path_s, cached = fetch_cached(url, cache_dir, timeout=args.timeout, sleep=args.sleep)
            parsed = parse_boe_xml(data) if target["kind"] == "boe" else parse_bocg_text(pdf_to_text(path_s))
            parsed = classify_scope(parsed, target.get("title") or "")
            public_url = url.replace("/dof/spa/xml", "") if target["kind"] == "boe" else url
            status = "boe" if target["kind"] == "boe" else bocg_text_status(url)
            docs[key] = {
                "url": public_url,
                "source": "BOE" if target["kind"] == "boe" else "BOCG",
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "text_status": status,
                "text_status_label": TEXT_STATUS_LABELS[status],
                **parsed,
            }
        except Exception as exc:  # noqa: BLE001
            failures.append({"vote_event_id": vid, "url": url, "error": f"{type(exc).__name__}: {exc}"[:200]})
            by_vote.pop(vid, None)

    # Votes without a text link: motions (BOCG serie D points) and bills found on their initiative page.
    for vid, entry in sorted(seed_votes.items()):
        if vid in by_vote or not entry.get("expediente"):
            if not entry.get("expediente"):
                failures.append({"vote_event_id": vid, "url": "", "error": f"sin expediente ({entry.get('match')})"})
            continue
        builder = motion_highlight if entry.get("kind") in motions.MOTION_KINDS else law_highlight
        try:
            doc = builder(entry, titles.get(vid, ""), cache_dir, timeout=args.timeout, offline=args.offline)
        except Exception as exc:  # noqa: BLE001
            failures.append({"vote_event_id": vid, "url": entry.get("initiative_url") or "", "error": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        key = hashlib.sha1(f"{doc['url']}|{entry['expediente']}".encode("utf-8")).hexdigest()[:12]
        docs.setdefault(key, doc)
        by_vote[vid] = key

    omnibus = sum(1 for d in docs.values() if d["omnibus"])
    payload = {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "method": (
                "Encabezados literales del texto oficial (títulos y capítulos, artículos, normas que modifica). "
                f"Ómnibus: título, bloques y normas modificadas abarcan {OMNIBUS_MIN_THEMES} o más temas. "
                "Cambios ajenos al título: leyes modificadas en disposiciones finales de otro tema. "
                "PNL y mociones: puntos literales de la parte dispositiva publicada en el BOCG serie D "
                "(texto aprobado si se publicó; si no, el original, con text_status indicando si se votó con enmiendas)."
            ),
            "text_status_labels": TEXT_STATUS_LABELS,
            "votes_with_text": len(by_vote),
            "documents": len(docs),
            "omnibus_documents": omnibus,
            "failures": failures,
        },
        "by_vote": dict(sorted(by_vote.items())),
        "docs": dict(sorted(docs.items())),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    shown = out.resolve().relative_to(BASE_DIR) if out.resolve().is_relative_to(BASE_DIR) else out
    print(f"OK highlights -> {shown} (votes={len(by_vote)} docs={len(docs)} omnibus={omnibus} failures={len(failures)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Local document text extraction helpers."""

from __future__ import annotations

import html
from io import BytesIO
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
XML_ENCODING_RE = re.compile(br"encoding=['\"](?P<encoding>[^'\"]+)['\"]", re.I)
HTML_CHARSET_RE = re.compile(br"charset=(?P<charset>[A-Za-z0-9._-]+)", re.I)


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = TAG_RE.sub(" ", text)
    text = WS_RE.sub(" ", text).strip()
    return text


def decode_markup_bytes(raw_bytes: bytes) -> str:
    head = raw_bytes[:2048]
    candidates: list[str] = []
    for regex, group_name in ((XML_ENCODING_RE, "encoding"), (HTML_CHARSET_RE, "charset")):
        m = regex.search(head)
        if not m:
            continue
        try:
            enc = m.group(group_name).decode("ascii", errors="ignore").strip()
        except Exception:
            enc = ""
        if enc:
            candidates.append(enc)
    candidates.extend(["utf-8", "iso-8859-15", "iso-8859-1", "cp1252"])
    seen: set[str] = set()
    for encoding in candidates:
        key = encoding.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        try:
            return raw_bytes.decode(encoding)
        except Exception:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def extract_from_xml_or_html(raw_bytes: bytes) -> str:
    decoded = decode_markup_bytes(raw_bytes)

    try:
        root = ET.fromstring(decoded)
        joined = " ".join(t for t in root.itertext() if t)
        out = normalize_text(joined)
        if out:
            return out
    except Exception:
        pass

    return normalize_text(decoded)


def extract_from_pdf(raw_bytes: bytes, raw_path: Path) -> str:
    def _pdftotext_fallback() -> str:
        try:
            cp = subprocess.run(
                ["pdftotext", "-enc", "UTF-8", str(raw_path), "-"],
                check=False,
                capture_output=True,
                timeout=30,
            )
            if cp.returncode == 0 and cp.stdout:
                return normalize_text(cp.stdout.decode("utf-8", errors="replace"))
        except Exception:
            pass
        return ""

    reader = None
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(BytesIO(raw_bytes))
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(BytesIO(raw_bytes))
        except Exception:
            return _pdftotext_fallback()

    chunks: list[str] = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt:
            chunks.append(txt)
    out = normalize_text("\n".join(chunks))
    if out:
        return out
    return _pdftotext_fallback()


def should_parse_as_pdf(content_type: str, raw_path: Path) -> bool:
    ct = (content_type or "").lower()
    if "pdf" in ct:
        return True
    return raw_path.suffix.lower() == ".pdf"

"""Local document text extraction helpers."""

from __future__ import annotations

import html
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
XML_ENCODING_RE = re.compile(br"encoding=['\"](?P<encoding>[^'\"]+)['\"]", re.I)
HTML_CHARSET_RE = re.compile(br"charset=(?P<charset>[A-Za-z0-9._-]+)", re.I)


@dataclass(frozen=True)
class DocumentExtraction:
    text: str
    text_chars: int
    method: str
    truncated: bool


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


def extract_document_path(
    raw_path: Path,
    *,
    content_type: str = "",
    max_input_bytes: int = 50 * 1024 * 1024,
    max_text_chars: int = 2_000_000,
) -> DocumentExtraction:
    """Extract bounded text from one local document without loading PDFs whole."""

    path = Path(raw_path)
    if int(max_input_bytes) < 1 or int(max_text_chars) < 1:
        raise ValueError("max_input_bytes and max_text_chars must be >= 1")
    if not path.is_file():
        raise FileNotFoundError(path)

    if should_parse_as_pdf(content_type, path):
        reader = None
        method = ""
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            method = "pypdf_path"
        except Exception:
            try:
                from PyPDF2 import PdfReader  # type: ignore

                reader = PdfReader(str(path))
                method = "pypdf2_path"
            except Exception:
                reader = None

        if reader is not None:
            chunks: list[str] = []
            chars = 0
            truncated = False
            for page in reader.pages:
                try:
                    text = normalize_text(page.extract_text() or "")
                except Exception:
                    text = ""
                if not text:
                    continue
                remaining = int(max_text_chars) - chars
                if remaining <= 0:
                    truncated = True
                    break
                if len(text) > remaining:
                    chunks.append(text[:remaining])
                    chars += remaining
                    truncated = True
                    break
                chunks.append(text)
                chars += len(text)
            joined = normalize_text("\n".join(chunks))
            if joined:
                return DocumentExtraction(
                    text=joined,
                    text_chars=len(joined),
                    method=method,
                    truncated=truncated,
                )

        try:
            completed = subprocess.run(
                ["pdftotext", "-enc", "UTF-8", str(path), "-"],
                check=False,
                capture_output=True,
                timeout=120,
            )
        except Exception as exc:
            raise RuntimeError(f"PDF text extraction unavailable: {type(exc).__name__}: {exc}") from exc
        if completed.returncode != 0 or not completed.stdout:
            raise RuntimeError(f"pdftotext failed: exit_code={completed.returncode}")
        decoded = normalize_text(completed.stdout.decode("utf-8", errors="replace"))
        truncated = len(decoded) > int(max_text_chars)
        text = decoded[: int(max_text_chars)]
        return DocumentExtraction(
            text=text,
            text_chars=len(text),
            method="pdftotext",
            truncated=truncated,
        )

    declared_size = path.stat().st_size
    if declared_size > int(max_input_bytes):
        raise RuntimeError(
            f"markup input exceeds max_input_bytes: bytes={declared_size} max={int(max_input_bytes)}"
        )
    raw_bytes = path.read_bytes()
    decoded = extract_from_xml_or_html(raw_bytes)
    truncated = len(decoded) > int(max_text_chars)
    text = decoded[: int(max_text_chars)]
    return DocumentExtraction(
        text=text,
        text_chars=len(text),
        method="markup_path",
        truncated=truncated,
    )

"""Local document text extraction helpers."""

from __future__ import annotations

import html
import hashlib
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
DOCUMENT_EXTRACTION_ALGORITHM_VERSION = "document_extraction_v2_pdf_plain_text"


@dataclass(frozen=True)
class DocumentExtraction:
    text: str
    text_chars: int
    method: str
    truncated: bool


@dataclass(frozen=True)
class DocumentTextLocator:
    """Exact address into the normalized native text for one real document."""

    segment_index: int
    locator_type: str
    locator_value: str
    page_number: int | None
    text_start_char: int
    text_end_char: int
    text_chars: int
    text_sha256: str
    has_text: bool


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = TAG_RE.sub(" ", text)
    text = WS_RE.sub(" ", text).strip()
    return text


def normalize_plain_text(text: str) -> str:
    """Normalize extracted plain text without treating angle brackets as tags."""

    text = html.unescape(text)
    return WS_RE.sub(" ", text).strip()


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
                return normalize_plain_text(cp.stdout.decode("utf-8", errors="replace"))
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
    out = normalize_plain_text("\n".join(chunks))
    if out:
        return out
    return _pdftotext_fallback()


def should_parse_as_pdf(content_type: str, raw_path: Path) -> bool:
    ct = (content_type or "").lower()
    if "pdf" in ct:
        return True
    return raw_path.suffix.lower() == ".pdf"


def _normalized_pdf_pages_from_pdftotext(
    path: Path,
    *,
    expected_page_count: int,
    timeout_seconds: float,
) -> list[str]:
    try:
        completed = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", str(path), "-"],
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        raise RuntimeError(
            f"PDF page extraction unavailable: {type(exc).__name__}: {exc}"
        ) from exc
    if completed.returncode != 0:
        raise RuntimeError(
            f"pdftotext page extraction failed: exit_code={completed.returncode}"
        )
    pages = [
        normalize_plain_text(part)
        for part in completed.stdout.decode("utf-8", errors="replace").split("\f")
    ]
    while len(pages) > expected_page_count and pages[-1] == "":
        pages.pop()
    if len(pages) < expected_page_count:
        pages.extend([""] * (expected_page_count - len(pages)))
    if len(pages) != expected_page_count:
        raise RuntimeError(
            "pdftotext page boundary count drifted: "
            f"expected={expected_page_count} observed={len(pages)}"
        )
    return pages


def _normalized_pdf_pages_from_python(
    path: Path,
    *,
    extraction_method: str,
    expected_page_count: int,
) -> list[str]:
    if extraction_method == "pypdf_path":
        from pypdf import PdfReader  # type: ignore
    elif extraction_method == "pypdf2_path":
        from PyPDF2 import PdfReader  # type: ignore
    else:
        raise RuntimeError(f"unsupported PDF extraction method: {extraction_method}")
    reader = PdfReader(str(path))
    if len(reader.pages) != expected_page_count:
        raise RuntimeError(
            "Python PDF page count drifted: "
            f"expected={expected_page_count} observed={len(reader.pages)}"
        )
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(normalize_plain_text(page.extract_text() or ""))
        except Exception:
            pages.append("")
    return pages


def build_document_text_locators(
    native_text: str,
    *,
    raw_path: Path,
    content_type: str,
    extraction_method: str,
    expected_page_count: int | None,
    max_span_chars: int = 8_192,
    pdf_timeout_seconds: float = 120.0,
) -> list[DocumentTextLocator]:
    """Build exact page or normalized-span locators without copying public text."""

    if max_span_chars < 1 or pdf_timeout_seconds <= 0:
        raise ValueError("locator bounds must be positive")
    def encoded_digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    if should_parse_as_pdf(content_type, raw_path):
        if expected_page_count is None or expected_page_count < 1:
            raise RuntimeError("PDF locator generation requires a positive page count")
        if extraction_method == "pdftotext":
            pages = _normalized_pdf_pages_from_pdftotext(
                raw_path,
                expected_page_count=expected_page_count,
                timeout_seconds=pdf_timeout_seconds,
            )
        else:
            pages = _normalized_pdf_pages_from_python(
                raw_path,
                extraction_method=extraction_method,
                expected_page_count=expected_page_count,
            )
        reconstructed = normalize_plain_text(" ".join(page for page in pages if page))
        if reconstructed != native_text:
            raise RuntimeError("PDF page text does not reconstruct the native text CAS")
        locators: list[DocumentTextLocator] = []
        cursor = 0
        has_prior_text = False
        for page_number, page_text in enumerate(pages, start=1):
            if page_text and has_prior_text:
                cursor += 1
            start = cursor
            cursor += len(page_text)
            end = cursor
            if page_text:
                has_prior_text = True
            locators.append(
                DocumentTextLocator(
                    segment_index=page_number - 1,
                    locator_type="pdf_page",
                    locator_value=f"page:{page_number:06d}",
                    page_number=page_number,
                    text_start_char=start,
                    text_end_char=end,
                    text_chars=len(page_text),
                    text_sha256=encoded_digest(page_text),
                    has_text=bool(page_text),
                )
            )
        return locators

    if not native_text:
        return [
            DocumentTextLocator(
                segment_index=0,
                locator_type="document_no_text",
                locator_value="chars:000000000000-000000000000",
                page_number=None,
                text_start_char=0,
                text_end_char=0,
                text_chars=0,
                text_sha256=encoded_digest(""),
                has_text=False,
            )
        ]
    locators = []
    for segment_index, start in enumerate(range(0, len(native_text), max_span_chars)):
        end = min(len(native_text), start + max_span_chars)
        segment_text = native_text[start:end]
        locators.append(
            DocumentTextLocator(
                segment_index=segment_index,
                locator_type="normalized_text_span",
                locator_value=f"chars:{start:012d}-{end:012d}",
                page_number=None,
                text_start_char=start,
                text_end_char=end,
                text_chars=len(segment_text),
                text_sha256=encoded_digest(segment_text),
                has_text=True,
            )
        )
    return locators


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
                    text = normalize_plain_text(page.extract_text() or "")
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
            joined = normalize_plain_text("\n".join(chunks))
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
        decoded = normalize_plain_text(completed.stdout.decode("utf-8", errors="replace"))
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

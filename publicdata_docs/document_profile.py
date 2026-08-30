"""Deterministic language and encryption profiling for real document bytes."""

from __future__ import annotations

import codecs
import gzip
import hashlib
import importlib.metadata
import re
import shutil
import subprocess
import threading
import xml.parsers.expat
from collections.abc import Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

LANGUAGE_MODEL = "py3langid"
LANGUAGE_MODEL_VERSION = "0.3.0"
PROFILE_ALGORITHM_VERSION = "document_profile_v2"
DEFAULT_SAMPLE_BYTES = 64 * 1024
DEFAULT_MIN_ALPHA_CHARS = 200
DEFAULT_MIN_CONFIDENCE = 0.80
DEFAULT_MIN_MARGIN = 0.20
ISO639_1_RE = re.compile(r"^[a-z]{2}$")
PDF_ENCRYPTED_RE = re.compile(r"^Encrypted:\s*(yes|no)\b", re.MULTILINE)
_THREAD_LOCAL = threading.local()


class DocumentProfileError(RuntimeError):
    """Raised when exact document profiling cannot be completed."""


@dataclass(frozen=True)
class TextSample:
    text: str
    sample_bytes: int
    text_bytes: int
    text_sha256: str
    alphabetic_chars: int
    sample_sha256: str


def sha256_path(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_child(root: Path, relative: str) -> Path:
    relative_path = Path(str(relative or ""))
    if (
        not str(relative_path)
        or relative_path.is_absolute()
        or ".." in relative_path.parts
    ):
        raise DocumentProfileError(f"unsafe relative path: {relative!r}")
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise DocumentProfileError(f"path escapes root: {relative}") from exc
    return candidate


def _language_detector() -> Any:
    detector = getattr(_THREAD_LOCAL, "language_detector", None)
    if detector is None:
        try:
            installed = importlib.metadata.version(LANGUAGE_MODEL)
            from py3langid.langid import MODEL_FILE, LanguageIdentifier
        except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
            raise DocumentProfileError(
                f"{LANGUAGE_MODEL}=={LANGUAGE_MODEL_VERSION} is required"
            ) from exc
        if installed != LANGUAGE_MODEL_VERSION:
            raise DocumentProfileError(
                f"language model version drifted: {installed} != "
                f"{LANGUAGE_MODEL_VERSION}"
            )
        detector = LanguageIdentifier.from_pickled_model(
            MODEL_FILE,
            norm_probs=True,
        )
        _THREAD_LOCAL.language_detector = detector
    return detector


def validate_profile_runtime() -> dict[str, str]:
    """Fail before queue mutation when the pinned language runtime is unavailable."""

    _language_detector()
    return {
        "language_model": LANGUAGE_MODEL,
        "language_model_version": LANGUAGE_MODEL_VERSION,
        "profile_algorithm_version": PROFILE_ALGORITHM_VERSION,
    }


def read_verified_text_sample(
    path: Path,
    *,
    expected_sha256: str,
    max_sample_bytes: int = DEFAULT_SAMPLE_BYTES,
) -> TextSample:
    """Rehash all decompressed UTF-8 bytes and retain bounded head/tail text."""
    if max_sample_bytes < 1024:
        raise DocumentProfileError("sample byte limit must be at least 1024")
    head_limit = max_sample_bytes // 2
    tail_limit = max_sample_bytes - head_limit
    head = bytearray()
    tail = bytearray()
    digest = hashlib.sha256()
    text_bytes = 0
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    try:
        with gzip.open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                text_bytes += len(chunk)
                decoder.decode(chunk)
                if len(head) < head_limit:
                    head.extend(chunk[: head_limit - len(head)])
                tail.extend(chunk)
                if len(tail) > tail_limit:
                    del tail[: len(tail) - tail_limit]
        decoder.decode(b"", final=True)
    except (OSError, EOFError, UnicodeDecodeError) as exc:
        raise DocumentProfileError(f"cannot read text CAS {path.name}: {exc}") from exc
    actual_sha256 = digest.hexdigest()
    if actual_sha256 != expected_sha256:
        raise DocumentProfileError(
            f"text CAS checksum drifted: {path.name}: {actual_sha256}"
        )
    if text_bytes <= max_sample_bytes:
        sample_bytes = bytes(head) + bytes(tail[len(head) :])
    else:
        sample_bytes = bytes(head) + b"\n" + bytes(tail)
    # Head/tail byte bounds may cut a multibyte code point. The full stream was
    # already validated strictly above; dropping only a cut boundary fragment is
    # deterministic and does not alter or replace the retained CAS bytes.
    text = sample_bytes.decode("utf-8", errors="ignore")
    return TextSample(
        text=text,
        sample_bytes=len(sample_bytes),
        text_bytes=text_bytes,
        text_sha256=actual_sha256,
        alphabetic_chars=sum(character.isalpha() for character in text),
        sample_sha256=hashlib.sha256(sample_bytes).hexdigest(),
    )


def classify_language(
    sample: TextSample,
    *,
    min_alpha_chars: int = DEFAULT_MIN_ALPHA_CHARS,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    min_margin: float = DEFAULT_MIN_MARGIN,
) -> dict[str, Any]:
    if sample.alphabetic_chars < min_alpha_chars:
        return {
            "machine_language_candidate": "und",
            "machine_language_status": "insufficient_alphabetic_text",
            "machine_language_confidence": None,
            "machine_language_margin": None,
            "machine_language_runner_up": None,
        }
    ranked = _language_detector().rank(sample.text)
    if len(ranked) < 2:
        raise DocumentProfileError("language model did not return two candidates")
    first_language, first_confidence = ranked[0]
    second_language, second_confidence = ranked[1]
    confidence = float(first_confidence)
    margin = confidence - float(second_confidence)
    accepted = confidence >= min_confidence and margin >= min_margin
    return {
        "machine_language_candidate": str(first_language),
        "machine_language_status": (
            "candidate_threshold_passed" if accepted else "candidate_below_threshold"
        ),
        "machine_language_confidence": round(confidence, 8),
        "machine_language_margin": round(margin, 8),
        "machine_language_runner_up": str(second_language),
    }


def normalize_declared_language(value: str | None) -> str | None:
    raw = str(value or "").strip().replace("_", "-").lower()
    if not raw:
        return None
    primary = raw.split("-", 1)[0]
    return primary if ISO639_1_RE.fullmatch(primary) else None


class _MarkupLanguageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.language: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        attributes = {name.casefold(): value for name, value in attrs}
        if lowered == "html" and self.language is None:
            self.language = normalize_declared_language(
                attributes.get("lang") or attributes.get("xml:lang")
            )
        if lowered == "meta" and self.language is None:
            http_equiv = str(attributes.get("http-equiv") or "").casefold()
            name = str(attributes.get("name") or "").casefold()
            if http_equiv == "content-language" or name == "language":
                self.language = normalize_declared_language(attributes.get("content"))


class _StopAfterRoot(Exception):
    pass


def declared_markup_language(path: Path, extension: str) -> str | None:
    if extension in {"html", "htm"}:
        parser = _MarkupLanguageParser()
        decoder = codecs.getincrementaldecoder("utf-8")("ignore")
        with path.open("rb") as handle:
            remaining = 1024 * 1024
            while remaining > 0 and parser.language is None:
                chunk = handle.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                parser.feed(decoder.decode(chunk))
        return parser.language
    if extension != "xml":
        return None
    declared: str | None = None

    def start(name: str, attributes: Mapping[str, str]) -> None:
        nonlocal declared
        del name
        for key, value in attributes.items():
            local = key.rsplit("}", 1)[-1].rsplit(":", 1)[-1].casefold()
            if local == "lang":
                declared = normalize_declared_language(value)
                break
        raise _StopAfterRoot

    parser = xml.parsers.expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler = start
    try:
        with path.open("rb") as handle:
            parser.ParseFile(handle)
    except _StopAfterRoot:
        pass
    except (OSError, xml.parsers.expat.ExpatError):
        return None
    return declared


def pdf_profile(path: Path, timeout: float) -> tuple[str, str | None]:
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        raise DocumentProfileError("pdfinfo is required for encryption classification")
    try:
        result = subprocess.run(
            [pdfinfo, str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DocumentProfileError(f"pdfinfo failed: {path.name}: {exc}") from exc
    match = PDF_ENCRYPTED_RE.search(result.stdout)
    if result.returncode != 0 or match is None:
        detail = result.stderr.strip() or "missing Encrypted field"
        raise DocumentProfileError(f"pdfinfo failed: {path.name}: {detail}")
    encrypted = "encrypted" if match.group(1) == "yes" else "not_encrypted"
    declared: str | None = None
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path), strict=False)
        if not reader.is_encrypted:
            root = reader.trailer.get("/Root")
            if root is not None:
                root_object = root.get_object()
                declared = normalize_declared_language(root_object.get("/Lang"))
    except Exception:  # noqa: BLE001 - language metadata is optional evidence
        declared = None
    return encrypted, declared


def profile_document_content(
    *,
    raw_path: Path,
    content_sha256: str,
    extension: str,
    text_cas_path: Path,
    text_sha256: str,
    sample_bytes: int,
    min_alpha_chars: int,
    min_confidence: float,
    min_margin: float,
    pdf_timeout: float,
) -> dict[str, Any]:
    if sha256_path(raw_path) != content_sha256:
        raise DocumentProfileError(f"raw checksum drifted: {raw_path.name}")
    sample = read_verified_text_sample(
        text_cas_path,
        expected_sha256=text_sha256,
        max_sample_bytes=sample_bytes,
    )
    language = classify_language(
        sample,
        min_alpha_chars=min_alpha_chars,
        min_confidence=min_confidence,
        min_margin=min_margin,
    )
    normalized_extension = extension.casefold().lstrip(".")
    if normalized_extension == "pdf":
        encryption_status, declared_language = pdf_profile(raw_path, pdf_timeout)
    else:
        encryption_status = "not_applicable_plain_markup"
        declared_language = declared_markup_language(raw_path, normalized_extension)
    machine_candidate = str(language["machine_language_candidate"])
    if declared_language and machine_candidate != "und":
        evidence_status = (
            "source_declared_model_agree"
            if declared_language == machine_candidate
            else "source_declared_model_conflict"
        )
    elif declared_language:
        evidence_status = "source_declared_only"
    elif machine_candidate != "und":
        evidence_status = "machine_candidate_only_unreviewed"
    else:
        evidence_status = "unknown_unreviewed"
    return {
        **language,
        "source_declared_language": declared_language,
        "language_evidence_status": evidence_status,
        "language_review_status": "unreviewed",
        "encryption_status": encryption_status,
        "language_model": LANGUAGE_MODEL,
        "language_model_version": LANGUAGE_MODEL_VERSION,
        "profile_algorithm_version": PROFILE_ALGORITHM_VERSION,
        "language_sample_bytes": sample.sample_bytes,
        "language_sample_sha256": sample.sample_sha256,
        "language_sample_alphabetic_chars": sample.alphabetic_chars,
        "native_text_bytes": sample.text_bytes,
        "native_text_sha256_verified": sample.text_sha256,
    }

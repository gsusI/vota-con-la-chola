from __future__ import annotations

import html as html_lib
import re
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from etl.politicos_es.util import normalize_ws, now_utc_iso, sha256_bytes

from .http import http_get_bytes, payload_looks_like_html


_PAGE_ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bname=['\"]\((?:P(?:\u00e1|a)gina)(?P<num>\d+)\)['\"]",
    re.I,
)
_PAGE_HINT_RE = re.compile(r"p(?:\u00e1|a)gina\s*(?P<num>\d+)", re.I)
_PAGE_PARAM_RE = re.compile(r"(?:^|[?&#])page=(?P<num>\d+)(?:$|[&#])", re.I)
_TEXTO_INTEGRO_DIV_RE = re.compile(r"<div\s+class=['\"]textoIntegro['\"]\s*>", re.I)


def _canonical_url(url: str) -> str:
    u = normalize_ws(url)
    if not u:
        return ""
    # Fragments are page anchors; fetching without them is stable and cacheable.
    return u.split("#", 1)[0]


def _page_hint_from_url(url: str) -> int | None:
    """Extract a page hint from URL fragments (PáginaNN) or #page=NN."""
    u = normalize_ws(url)
    if not u:
        return None

    m = _PAGE_PARAM_RE.search(u)
    if m:
        try:
            return int(m.group("num"))
        except ValueError:
            return None

    parsed = urlparse(u)
    if parsed.fragment:
        frag = unquote(parsed.fragment)
        m2 = _PAGE_HINT_RE.search(frag)
        if m2:
            try:
                return int(m2.group("num"))
            except ValueError:
                return None
    return None


def _guess_ext(payload: bytes, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    if payload_looks_like_html(payload) or "text/html" in ct:
        return "html"
    if payload[:5] == b"%PDF-" or "application/pdf" in ct:
        return "pdf"
    return "bin"


def _strip_html(html: str) -> str:
    # Remove scripts/styles first to reduce noise.
    cleaned = re.sub(r"<script\\b.*?</script>", " ", html, flags=re.I | re.S)
    cleaned = re.sub(r"<style\\b.*?</style>", " ", cleaned, flags=re.I | re.S)
    cleaned = html_lib.unescape(cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return normalize_ws(cleaned)


def _extract_texto_integro_div(html: str) -> str:
    """Extract inner HTML for <div class="textoIntegro">...</div> (best-effort).

    Congreso "mostrarTextoIntegro" pages wrap the Diario text inside this div. Restricting extraction to
    this container prevents polluting excerpts with navigation/scripts.
    """
    if not html:
        return ""
    m = _TEXTO_INTEGRO_DIV_RE.search(html)
    if not m:
        return html

    start_tag_end = html.find(">", m.end() - 1)
    if start_tag_end < 0:
        return html

    lower = html.lower()
    i = start_tag_end + 1
    depth = 1
    while i < len(html):
        next_open = lower.find("<div", i)
        next_close = lower.find("</div", i)
        if next_close < 0:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            i = next_open + 4
            continue
        depth -= 1
        if depth <= 0:
            return html[start_tag_end + 1 : next_close]
        i = next_close + 5
    return html[start_tag_end + 1 :]


def _extract_congreso_texto_integro_page_excerpt(html: str, page_hint: int | None) -> str:
    """Extract a page-sized excerpt from Congreso 'mostrarTextoIntegro' HTML.

    The page anchors look like: <a name='(Página22)'><b>Página 22</b></a>
    """
    if not html:
        return ""

    html = _extract_texto_integro_div(html)

    if page_hint is None:
        # Fallback: strip the whole textoIntegro container.
        return _strip_html(html)

    # Find the requested anchor, then slice until the next page anchor.
    matches = list(_PAGE_ANCHOR_RE.finditer(html))
    if not matches:
        return _strip_html(html)
    start = -1
    end = len(html)
    for idx, m in enumerate(matches):
        try:
            num = int(m.group("num"))
        except (TypeError, ValueError):
            continue
        if num != int(page_hint):
            continue
        start = m.start()
        if idx + 1 < len(matches):
            end = matches[idx + 1].start()
        break
    if start < 0:
        return _strip_html(html)

    return _strip_html(html[start:end])


def _raw_path_for_content(raw_dir: Path, *, source_id: str, content_sha: str, ext: str) -> Path:
    out_dir = raw_dir / "text_documents" / source_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{content_sha}.{ext}"


def _read_file_url(url: str) -> bytes:
    parsed = urlparse(url)
    path = unquote(parsed.path)
    return Path(path).read_bytes()


def backfill_text_documents_from_topic_evidence(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    raw_dir: Path,
    timeout: int,
    limit: int = 200,
    only_missing: bool = True,
    from_dir: Path | None = None,
    strict_network: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Fetch and store text document metadata for declared evidence rows.

    Scope: starts with Congreso interventions (declared evidence with ENLACETEXTOINTEGRO/PDF).
    The contract is small:
    - Keep raw bytes on disk (raw_dir/text_documents/<source_id>/...).
    - Store only metadata + an excerpt in SQLite (text_documents).
    """
    now_iso = now_utc_iso()
    seen = 0
    skipped = 0
    failures: list[str] = []
    extracted_excerpt = 0

    existing: set[int] = set()
    if only_missing:
        try:
            rows = conn.execute(
                "SELECT source_record_pk FROM text_documents WHERE source_id = ? AND source_record_pk IS NOT NULL",
                (source_id,),
            ).fetchall()
            for r in rows:
                try:
                    existing.add(int(r[0]))
                except Exception:  # noqa: BLE001
                    continue
        except sqlite3.Error:
            existing = set()

    rows = conn.execute(
        """
        SELECT DISTINCT
          source_record_pk,
          source_url
        FROM topic_evidence
        WHERE source_id = ?
          AND evidence_type LIKE 'declared:%'
          AND source_record_pk IS NOT NULL
          AND source_url IS NOT NULL
          AND TRIM(source_url) <> ''
        ORDER BY source_record_pk ASC
        LIMIT ?
        """,
        (source_id, int(limit)),
    ).fetchall()

    # Cache downloads by canonical URL to avoid repeated fetches for different page anchors.
    by_url_cache: dict[str, tuple[bytes, str | None]] = {}

    to_upsert: list[tuple[Any, ...]] = []
    for r in rows:
        seen += 1
        sr_pk = int(r["source_record_pk"])
        source_url_full = normalize_ws(str(r["source_url"] or ""))
        if not source_url_full:
            continue
        if only_missing and sr_pk in existing:
            skipped += 1
            continue

        payload_bytes: bytes | None = None
        content_type: str | None = None
        try:
            if from_dir is not None:
                for ext in ("html", "htm", "pdf", "bin"):
                    p = from_dir / f"textdoc_{sr_pk}.{ext}"
                    if p.exists():
                        payload_bytes = p.read_bytes()
                        content_type = "text/html" if ext in {"html", "htm"} else ("application/pdf" if ext == "pdf" else None)
                        break

            if payload_bytes is None and source_url_full.lower().startswith("file://"):
                payload_bytes = _read_file_url(source_url_full)

            url_canon = _canonical_url(source_url_full)
            if payload_bytes is None:
                cached = by_url_cache.get(url_canon)
                if cached is not None:
                    payload_bytes, content_type = cached
                else:
                    # Try reusing a previously downloaded raw_path for the same canonical URL.
                    try:
                        row = conn.execute(
                            """
                            SELECT raw_path, content_type
                            FROM text_documents
                            WHERE source_id = ?
                              AND source_url LIKE ?
                              AND raw_path IS NOT NULL
                              AND TRIM(raw_path) <> ''
                            ORDER BY fetched_at DESC, text_document_id DESC
                            LIMIT 1
                            """,
                            (source_id, f"{url_canon}%"),
                        ).fetchone()
                    except sqlite3.Error:
                        row = None

                    if row is not None:
                        try:
                            p = Path(str(row["raw_path"]))
                            if p.exists():
                                payload_bytes = p.read_bytes()
                                content_type = str(row["content_type"] or "") or None
                        except OSError:
                            payload_bytes = None
                            content_type = None

                    if payload_bytes is None:
                        payload_bytes, content_type = http_get_bytes(
                            url_canon,
                            timeout=int(timeout),
                            headers={"Accept": "text/html,application/xhtml+xml,application/pdf,*/*"},
                        )
                    by_url_cache[url_canon] = (payload_bytes, content_type)

            assert payload_bytes is not None
            ext = _guess_ext(payload_bytes, content_type)
            content_sha = sha256_bytes(payload_bytes)
            raw_path = _raw_path_for_content(raw_dir, source_id=source_id, content_sha=content_sha, ext=ext)
            if not dry_run and not raw_path.exists():
                raw_path.write_bytes(payload_bytes)

            excerpt = None
            text_chars = None
            if ext == "html":
                page_hint = _page_hint_from_url(source_url_full)
                html = payload_bytes.decode("utf-8", errors="replace")
                excerpt_text = _extract_congreso_texto_integro_page_excerpt(html, page_hint=page_hint)
                if excerpt_text:
                    excerpt = excerpt_text[:4000]
                    text_chars = len(excerpt_text)
                    extracted_excerpt += 1

            to_upsert.append(
                (
                    source_id,
                    source_url_full,
                    sr_pk,
                    now_iso,
                    content_type,
                    content_sha,
                    len(payload_bytes),
                    str(raw_path),
                    excerpt,
                    text_chars,
                    now_iso,
                    now_iso,
                )
            )
        except Exception as exc:  # noqa: BLE001
            failures.append(f"source_record_pk={sr_pk} url={source_url_full} -> {type(exc).__name__}: {exc}")
            if strict_network:
                raise

    if dry_run:
        return {
            "source_id": source_id,
            "dry_run": True,
            "seen": seen,
            "skipped_existing": skipped,
            "to_upsert": len(to_upsert),
            "extracted_excerpt": extracted_excerpt,
            "failures": failures,
        }

    if to_upsert:
        with conn:
            conn.executemany(
                """
                INSERT INTO text_documents (
                  source_id, source_url, source_record_pk,
                  fetched_at, content_type, content_sha256, bytes, raw_path,
                  text_excerpt, text_chars,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_record_pk) DO UPDATE SET
                  source_url = excluded.source_url,
                  fetched_at = excluded.fetched_at,
                  content_type = excluded.content_type,
                  content_sha256 = excluded.content_sha256,
                  bytes = excluded.bytes,
                  raw_path = excluded.raw_path,
                  text_excerpt = CASE
                    WHEN excluded.text_excerpt IS NOT NULL AND TRIM(excluded.text_excerpt) <> '' THEN excluded.text_excerpt
                    ELSE text_documents.text_excerpt
                  END,
                  text_chars = CASE
                    WHEN excluded.text_chars IS NOT NULL AND excluded.text_chars > 0 THEN excluded.text_chars
                    ELSE text_documents.text_chars
                  END,
                  updated_at = excluded.updated_at
                """,
                to_upsert,
            )
            # Note: we don't distinguish inserts vs updates here (keep it simple).

    # Make declared evidence auditable in the UI by copying a short excerpt into topic_evidence.
    # This is safe because topic_evidence is derived and fully traceable via source_record_pk.
    try:
        with conn:
            conn.execute(
                """
                UPDATE topic_evidence
                SET excerpt = COALESCE(
                  (
                    SELECT SUBSTR(d.text_excerpt, 1, 800)
                    FROM text_documents d
                    WHERE d.source_id = topic_evidence.source_id
                      AND d.source_record_pk = topic_evidence.source_record_pk
                      AND d.text_excerpt IS NOT NULL
                      AND TRIM(d.text_excerpt) <> ''
                    LIMIT 1
                  ),
                  topic_evidence.excerpt
                ),
                updated_at = ?
                WHERE topic_evidence.source_id = ?
                  AND topic_evidence.evidence_type LIKE 'declared:%'
                  AND topic_evidence.source_record_pk IS NOT NULL
                  AND EXISTS (
                    SELECT 1
                    FROM text_documents d
                    WHERE d.source_id = topic_evidence.source_id
                      AND d.source_record_pk = topic_evidence.source_record_pk
                      AND d.text_excerpt IS NOT NULL
                      AND TRIM(d.text_excerpt) <> ''
                  )
                """,
                (now_iso, source_id),
            )
    except sqlite3.Error:
        pass

    try:
        docs_total = int(
            (conn.execute("SELECT COUNT(*) AS c FROM text_documents WHERE source_id = ?", (source_id,)).fetchone() or {"c": 0})["c"]
        )
    except sqlite3.Error:
        docs_total = 0

    return {
        "source_id": source_id,
        "dry_run": False,
        "seen": seen,
        "skipped_existing": skipped,
        "upserted": len(to_upsert),
        "documents_total_for_source": docs_total,
        "extracted_excerpt": extracted_excerpt,
        "failures": failures,
    }

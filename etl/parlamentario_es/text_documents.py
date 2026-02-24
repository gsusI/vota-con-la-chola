from __future__ import annotations

from dataclasses import dataclass
import json
import html as html_lib
import random
import re
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

from etl.politicos_es.util import normalize_ws, now_utc_iso, sha256_bytes, stable_json

from .http import http_get_bytes, payload_looks_like_html


_PAGE_ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bname=['\"]\((?:P(?:\u00e1|a)gina)(?P<num>\d+)\)['\"]",
    re.I,
)
_PAGE_HINT_RE = re.compile(r"p(?:\u00e1|a)gina\s*(?P<num>\d+)", re.I)
_PAGE_PARAM_RE = re.compile(r"(?:^|[?&#])page=(?P<num>\d+)(?:$|[&#])", re.I)
_TEXTO_INTEGRO_DIV_RE = re.compile(r"<div\s+class=['\"]textoIntegro['\"]\s*>", re.I)
_URL_RE = re.compile(r"https?://\S+", re.I)
_SENADO_GLOBAL_ENMIENDAS_RE = re.compile(
    r"^(?P<scheme>https?)://(?:www\.)?senado\.es/"
    r"(?P<legis>legis\d+)/expedientes/(?P<tipo>\d+)/enmiendas/"
    r"global_enmiendas_vetos_\d+_(?P<num>\d{9})\.xml$",
    re.I,
)


INITIATIVE_DOC_SOURCE_ID = "parl_initiative_docs"
_SKIP_HTTP_STATUSES_DEFAULT = (403, 404, 500)
_ARCHIVE_FALLBACK_HTTP_STATUSES_DEFAULT = (404,)
_WAYBACK_AVAILABLE_API = "https://archive.org/wayback/available"


class HTTPStatusError(RuntimeError):
    """HTTP-like error carrying a status code (for document_fetches)."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = int(code)


@dataclass(frozen=True)
class _PlaywrightFetchConfig:
    user_data_dir: str
    channel: str = "chrome"
    headless: bool = False


class _PlaywrightFetcher:
    """Fetch bytes using a real browser network stack (WAF-friendly).

    We use a persistent context so cookies + storage from a captured profile
    are available (often required for senado.es protected endpoints).
    """

    def __init__(self, cfg: _PlaywrightFetchConfig):
        self.cfg = cfg
        self._pw = None
        self._ctx = None
        self._page = None
        self._warmed = False

    def __enter__(self) -> "_PlaywrightFetcher":
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Playwright no disponible. Instala:\n"
                "  python3 -m pip install playwright\n"
                "  python3 -m playwright install chromium\n"
            ) from exc

        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=self.cfg.user_data_dir,
            headless=bool(self.cfg.headless),
            channel=self.cfg.channel or None,
            accept_downloads=True,
            locale="es-ES",
            timezone_id="Europe/Madrid",
            viewport={"width": 1280, "height": 800},
            args=["--no-default-browser-check"],
        )
        self._page = self._ctx.new_page()
        try:
            self._page.set_extra_http_headers({"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"})
        except Exception:  # noqa: BLE001
            pass
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        try:
            try:
                if self._page is not None:
                    self._page.close()
            finally:
                self._page = None
            if self._ctx is not None:
                self._ctx.close()
        finally:
            self._ctx = None
            try:
                if self._pw is not None:
                    self._pw.stop()
            finally:
                self._pw = None

    def get_bytes(
        self,
        url: str,
        *,
        timeout_seconds: int,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, str | None]:
        assert self._ctx is not None
        assert self._page is not None

        timeout_ms = int(timeout_seconds) * 1000

        # Warm the browser session once to establish any clearance cookie/state.
        # Without this, some senado.es endpoints return 403 even with a persisted profile.
        if not self._warmed:
            seed = "https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=15&id1=610&id2=000002"
            resp_seed = self._page.goto(seed, wait_until="domcontentloaded", timeout=timeout_ms)
            if resp_seed is None or int(resp_seed.status) >= 400:
                st = int(resp_seed.status) if resp_seed is not None else 0
                raise HTTPStatusError(st or 599, f"warmup failed (playwright) status={st}")
            self._warmed = True

        req_headers = dict(headers or {})
        # Never inject Cookie header here; the browser profile manages cookies.
        req_headers = {str(k): str(v) for k, v in req_headers.items() if str(k).lower() != "cookie"}

        resp = self._ctx.request.get(url, headers=req_headers or None, timeout=timeout_ms)
        status = int(resp.status)
        if status >= 400:
            raise HTTPStatusError(status, f"HTTP {status} (playwright)")
        try:
            payload = resp.body()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"playwright: no se pudo leer body: {exc}") from exc
        ct = None
        try:
            ct = (resp.headers or {}).get("content-type")
        except Exception:  # noqa: BLE001
            ct = None
        return payload, ct


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (str(table),),
        ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False


def _fetch_status_by_url(conn: sqlite3.Connection, *, urls: list[str]) -> dict[str, dict[str, Any]]:
    if not urls:
        return {}
    if not _table_exists(conn, "document_fetches"):
        return {}
    out: dict[str, dict[str, Any]] = {}
    chunk = 700
    for i in range(0, len(urls), chunk):
        batch = urls[i : i + chunk]
        qmarks = ",".join("?" for _ in batch)
        try:
            rows = conn.execute(
                f"""
                SELECT
                  doc_url,
                  attempts,
                  fetched_ok,
                  last_http_status,
                  last_attempt_at
                FROM document_fetches
                WHERE doc_url IN ({qmarks})
                """,
                batch,
            ).fetchall()
        except sqlite3.Error:
            rows = []
        for r in rows:
            url = normalize_ws(str(r["doc_url"] or ""))
            if not url:
                continue
            out[url] = dict(r)
    return out


def _upsert_document_fetch_status(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    doc_url: str,
    now_iso: str,
    fetched_ok: bool,
    http_status: int | None,
    error: str | None,
    content_type: str | None,
    content_sha256: str | None,
    bytes_len: int | None,
    raw_path: str | None,
) -> None:
    if not _table_exists(conn, "document_fetches"):
        return
    with conn:
        conn.execute(
            """
            INSERT INTO document_fetches (
              doc_url, source_id,
              first_attempt_at, last_attempt_at,
              attempts, fetched_ok,
              last_http_status, last_error,
              content_type, content_sha256, bytes, raw_path
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(doc_url) DO UPDATE SET
              source_id = excluded.source_id,
              last_attempt_at = excluded.last_attempt_at,
              attempts = document_fetches.attempts + 1,
              fetched_ok = CASE
                WHEN excluded.fetched_ok = 1 THEN 1
                ELSE document_fetches.fetched_ok
              END,
              last_http_status = excluded.last_http_status,
              last_error = excluded.last_error,
              content_type = CASE
                WHEN excluded.content_type IS NOT NULL AND TRIM(excluded.content_type) <> '' THEN excluded.content_type
                ELSE document_fetches.content_type
              END,
              content_sha256 = CASE
                WHEN excluded.content_sha256 IS NOT NULL AND TRIM(excluded.content_sha256) <> '' THEN excluded.content_sha256
                ELSE document_fetches.content_sha256
              END,
              bytes = CASE
                WHEN excluded.bytes IS NOT NULL AND excluded.bytes > 0 THEN excluded.bytes
                ELSE document_fetches.bytes
              END,
              raw_path = CASE
                WHEN excluded.raw_path IS NOT NULL AND TRIM(excluded.raw_path) <> '' THEN excluded.raw_path
                ELSE document_fetches.raw_path
              END
            """,
            (
                doc_url,
                source_id,
                now_iso,
                now_iso,
                1 if fetched_ok else 0,
                int(http_status) if http_status is not None else None,
                normalize_ws(str(error or "")) or None,
                normalize_ws(str(content_type or "")) or None,
                normalize_ws(str(content_sha256 or "")) or None,
                int(bytes_len) if bytes_len is not None else None,
                normalize_ws(str(raw_path or "")) or None,
            ),
        )


def _canonical_url(url: str) -> str:
    u = normalize_ws(url)
    if not u:
        return ""
    # Fragments are page anchors; fetching without them is stable and cacheable.
    return u.split("#", 1)[0]


def _dedupe_keep_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        token = normalize_ws(str(raw or ""))
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _exception_http_status(exc: Exception) -> int | None:
    if hasattr(exc, "code"):
        try:
            return int(getattr(exc, "code"))
        except Exception:  # noqa: BLE001
            return None
    return None


def _is_senado_global_enmiendas_url(url: str) -> bool:
    token = _canonical_url(url).lower()
    return bool(token and "senado.es" in token and "global_enmiendas_vetos_" in token)


def _has_senado_bocg_alternative(downloaded_urls: set[str]) -> bool:
    if not downloaded_urls:
        return False
    for url in downloaded_urls:
        token = _canonical_url(url).lower()
        if not token:
            continue
        if "/publicaciones/pdf/senado/bocg/" in token:
            return True
        if "/xml/ini-3-" in token:
            return True
        if "ficopendataservlet" in token and "tipofich=3" in token:
            return True
    return False


def _derive_senado_ini_url_from_global_enmiendas(url: str) -> str | None:
    """Derive INI XML URL from Senado global_enmiendas_vetos URL."""
    token = _canonical_url(url)
    if not token:
        return None
    m = _SENADO_GLOBAL_ENMIENDAS_RE.match(token)
    if not m:
        return None
    scheme = normalize_ws(str(m.group("scheme") or "")).lower() or "http"
    legis = normalize_ws(str(m.group("legis") or ""))
    tipo = normalize_ws(str(m.group("tipo") or ""))
    num = normalize_ws(str(m.group("num") or ""))
    if not legis or not tipo or not num:
        return None
    return f"{scheme}://www.senado.es/{legis}/expedientes/{tipo}/xml/INI-3-{num}.xml"


def _lookup_wayback_candidates(
    original_url: str,
    *,
    timeout: int,
) -> tuple[list[str], str | None]:
    """Return candidate archive URLs for an original URL (best-effort)."""
    api_url = f"{_WAYBACK_AVAILABLE_API}?url={quote(original_url, safe='')}"
    payload, _ = http_get_bytes(
        api_url,
        timeout=max(1, int(timeout)),
        headers={"Accept": "application/json,*/*"},
    )
    try:
        obj = json.loads(payload.decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"wayback available json invalido: {type(exc).__name__}: {exc}") from exc
    if not isinstance(obj, dict):
        return [], None
    snapshots = obj.get("archived_snapshots")
    if not isinstance(snapshots, dict):
        return [], None
    closest = snapshots.get("closest")
    if not isinstance(closest, dict):
        return [], None
    available = str(closest.get("available") or "").strip().lower()
    if available not in {"1", "true", "yes"}:
        return [], None
    timestamp = normalize_ws(str(closest.get("timestamp") or "")) or None
    closest_url = _canonical_url(str(closest.get("url") or ""))
    candidates: list[str] = []
    if timestamp:
        candidates.append(f"https://web.archive.org/web/{timestamp}id_/{original_url}")
        candidates.append(f"https://web.archive.org/web/{timestamp}/{original_url}")
    if closest_url:
        candidates.append(closest_url)
    return _dedupe_keep_order(candidates), timestamp


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


def _clean_extracted_url(url: str) -> str:
    u = normalize_ws(url)
    if not u:
        return ""
    # Common cases: URLs inside parentheses or followed by punctuation in text fields.
    while u and u[0] in "('\"<[{":
        u = u[1:].lstrip()
    while u and u[-1] in ").,;>\"']}" :
        u = u[:-1].rstrip()
    return u


def _extract_urls(text: str | None) -> list[str]:
    if not text:
        return []
    raw = str(text)
    urls = [_clean_extracted_url(u) for u in _URL_RE.findall(raw)]
    urls = [u for u in urls if u.startswith("http")]
    if not urls:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def backfill_initiative_links_from_raw_payload(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...] | list[str],
    limit: int = 0,
    only_missing: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Backfill links_bocg_json/links_ds_json from parl_initiatives.raw_payload.

    This repairs historical rows ingested before URL extraction was implemented correctly.
    """
    now_iso = now_utc_iso()
    source_list: list[str] = []
    for raw_id in list(source_ids or []):
        sid = normalize_ws(str(raw_id))
        if not sid or sid in source_list:
            continue
        source_list.append(sid)

    if not source_list:
        return {"dry_run": bool(dry_run), "source_ids": [], "seen": 0, "updated": 0, "failures": []}

    placeholders = ",".join("?" for _ in source_list)
    where = f"WHERE source_id IN ({placeholders})"
    if only_missing:
        where += " AND (links_bocg_json IS NULL OR TRIM(links_bocg_json) = '' OR links_ds_json IS NULL OR TRIM(links_ds_json) = '')"

    limit_sql = ""
    params: list[Any] = [*source_list]
    if limit and int(limit) > 0:
        limit_sql = " LIMIT ?"
        params.append(int(limit))

    rows = conn.execute(
        f"""
        SELECT initiative_id, source_id, legislature, expediente, raw_payload, links_bocg_json, links_ds_json
        FROM parl_initiatives
        {where}
        ORDER BY initiative_id ASC
        {limit_sql}
        """,
        params,
    ).fetchall()

    seen = len(rows)
    failures: list[str] = []
    updates: list[tuple[Any, ...]] = []
    for r in rows:
        initiative_id = normalize_ws(str(r["initiative_id"] or ""))
        if not initiative_id:
            continue
        existing_bocg = normalize_ws(str(r["links_bocg_json"] or ""))
        existing_ds = normalize_ws(str(r["links_ds_json"] or ""))
        if only_missing and existing_bocg and existing_ds:
            continue

        try:
            payload = json.loads(str(r["raw_payload"] or "{}"))
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{initiative_id}: raw_payload JSON -> {type(exc).__name__}: {exc}")
            continue
        if not isinstance(payload, dict):
            continue

        bocg_urls = _extract_urls(payload.get("ENLACESBOCG") or payload.get("PDF"))
        ds_urls = _extract_urls(payload.get("ENLACESDS"))

        # Senado: many initiative rows don't include URL fields in raw_payload,
        # but we can deterministically construct the official endpoints from
        # (legislature, expediente=id1/id2). Only fill missing values.
        source_id = normalize_ws(str(r["source_id"] or ""))
        if source_id == "senado_iniciativas" and not bocg_urls and not ds_urls:
            leg = normalize_ws(str(r["legislature"] or ""))
            exp = normalize_ws(str(r["expediente"] or ""))
            if leg and exp and "/" in exp:
                id1, id2 = [normalize_ws(p) for p in exp.split("/", 1)]
                if id1.isdigit() and id2.isdigit():
                    bocg_urls = [
                        f"https://www.senado.es/web/ficopendataservlet?legis={leg}&tipoFich=3&tipoEx={id1}&numEx={id2}",
                    ]
                    ds_urls = [
                        f"https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis={leg}&id1={id1}&id2={id2}",
                        f"https://www.senado.es/web/ficopendataservlet?legis={leg}&tipoFich=12&tipoEx={id1}&numEx={id2}",
                    ]

        bocg_json = stable_json(bocg_urls) if bocg_urls else None
        ds_json = stable_json(ds_urls) if ds_urls else None

        out_bocg = existing_bocg or (bocg_json or "")
        out_ds = existing_ds or (ds_json or "")
        out_bocg = out_bocg if out_bocg.strip() else ""
        out_ds = out_ds if out_ds.strip() else ""

        # Only write when we are actually filling a missing value.
        changed = False
        write_bocg = None
        write_ds = None
        if not existing_bocg and out_bocg:
            write_bocg = out_bocg
            changed = True
        if not existing_ds and out_ds:
            write_ds = out_ds
            changed = True
        if not changed:
            continue

        updates.append((write_bocg, write_ds, now_iso, initiative_id))

    if dry_run:
        return {
            "dry_run": True,
            "source_ids": source_list,
            "seen": seen,
            "would_update": len(updates),
            "failures": failures[:30],
        }

    if updates:
        with conn:
            conn.executemany(
                """
                UPDATE parl_initiatives
                SET
                  links_bocg_json = COALESCE(?, links_bocg_json),
                  links_ds_json = COALESCE(?, links_ds_json),
                  updated_at = ?
                WHERE initiative_id = ?
                """,
                updates,
            )

    return {
        "dry_run": False,
        "source_ids": source_list,
        "seen": seen,
        "updated": len(updates),
        "failures": failures[:30],
    }


def backfill_initiative_documents_from_parl_initiatives(
    conn: sqlite3.Connection,
    *,
    initiative_source_ids: tuple[str, ...] | list[str],
    raw_dir: Path,
    timeout: int,
    snapshot_date: str | None = None,
    limit_initiatives: int = 200,
    max_docs_per_initiative: int = 3,
    only_linked_to_votes: bool = True,
    only_missing: bool = True,
    retry_forbidden: bool = False,
    sleep_seconds: float = 0.0,
    sleep_jitter_seconds: float = 0.0,
    cookie: str | None = None,
    playwright_user_data_dir: str | None = None,
    playwright_channel: str = "chrome",
    playwright_headless: bool = False,
    archive_fallback: bool = False,
    archive_timeout: int = 12,
    strict_network: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Download and materialize BOCG/DS docs referenced by parl_initiatives links.

    Stores bytes on disk under raw_dir/text_documents/<INITIATIVE_DOC_SOURCE_ID>/...
    and metadata in text_documents. Also records initiative->document URLs in
    parl_initiative_documents for Explorer drill-down.
    """
    from .db import upsert_source_records_with_content_sha256  # noqa: PLC0415

    now_iso = now_utc_iso()
    raw_dir = Path(raw_dir)

    source_list: list[str] = []
    for raw_id in list(initiative_source_ids or []):
        sid = normalize_ws(str(raw_id))
        if not sid or sid in source_list:
            continue
        source_list.append(sid)

    if not source_list:
        return {"dry_run": bool(dry_run), "initiative_source_ids": [], "initiatives_seen": 0, "doc_links_seen": 0}

    if limit_initiatives <= 0:
        limit_initiatives = 200
    if max_docs_per_initiative <= 0:
        max_docs_per_initiative = 2
    archive_fallback = bool(archive_fallback)
    archive_timeout = max(1, int(archive_timeout))

    placeholders = ",".join("?" for _ in source_list)
    missing_clause = ""
    if only_missing:
        missing_clause = """
          AND (
            NOT EXISTS (
              SELECT 1
              FROM parl_initiative_documents d
              WHERE d.initiative_id = i.initiative_id
            )
            OR EXISTS (
              SELECT 1
              FROM parl_initiative_documents d
              WHERE d.initiative_id = i.initiative_id
                AND d.source_record_pk IS NULL
            )
          )
        """

    order_priority_sql = """
        CASE
          WHEN NOT EXISTS (
            SELECT 1
            FROM parl_initiative_documents d0
            WHERE d0.initiative_id = i.initiative_id
          ) THEN 0
          WHEN NOT EXISTS (
            SELECT 1
            FROM parl_initiative_documents d0
            WHERE d0.initiative_id = i.initiative_id
              AND d0.source_record_pk IS NOT NULL
          ) THEN 1
          ELSE 2
        END
    """

    has_fetch_status = _table_exists(conn, "document_fetches")

    if only_linked_to_votes:
        sql = f"""
        SELECT
          i.source_id,
          i.initiative_id,
          i.links_bocg_json,
          i.links_ds_json,
          MAX(e.vote_date) AS last_vote_date
        FROM parl_initiatives i
        JOIN parl_vote_event_initiatives vi ON vi.initiative_id = i.initiative_id
        JOIN parl_vote_events e ON e.vote_event_id = vi.vote_event_id
        WHERE i.source_id IN ({placeholders})
          AND (
            (i.links_bocg_json IS NOT NULL AND TRIM(i.links_bocg_json) <> '')
            OR (i.links_ds_json IS NOT NULL AND TRIM(i.links_ds_json) <> '')
          )
          {missing_clause}
        GROUP BY i.source_id, i.initiative_id
        ORDER BY {order_priority_sql} ASC, last_vote_date DESC, i.initiative_id ASC
        LIMIT ?
        """
    else:
        leg_order_sql = """
            CASE
              WHEN i.legislature GLOB '[0-9]*' THEN CAST(i.legislature AS INTEGER)
              ELSE 0
            END
        """
        if has_fetch_status:
            # For wide queue drains, avoid retrying the same hot blocked URLs first.
            # Prioritize initiatives with missing docs that were never attempted,
            # then oldest-attempted missing docs.
            sql = f"""
            SELECT
              i.source_id,
              i.initiative_id,
              i.links_bocg_json,
              i.links_ds_json,
              NULL AS last_vote_date,
              (
                SELECT MIN(df.last_attempt_at)
                FROM parl_initiative_documents d0
                LEFT JOIN document_fetches df ON df.doc_url = d0.doc_url
                WHERE d0.initiative_id = i.initiative_id
                  AND d0.source_record_pk IS NULL
              ) AS oldest_missing_attempt_at
            FROM parl_initiatives i
            WHERE i.source_id IN ({placeholders})
              AND (
                (i.links_bocg_json IS NOT NULL AND TRIM(i.links_bocg_json) <> '')
                OR (i.links_ds_json IS NOT NULL AND TRIM(i.links_ds_json) <> '')
              )
              {missing_clause}
            ORDER BY {order_priority_sql} ASC, {leg_order_sql} DESC, oldest_missing_attempt_at ASC, i.updated_at DESC, i.initiative_id ASC
            LIMIT ?
            """
        else:
            sql = f"""
            SELECT
              i.source_id,
              i.initiative_id,
              i.links_bocg_json,
              i.links_ds_json,
              NULL AS last_vote_date
            FROM parl_initiatives i
            WHERE i.source_id IN ({placeholders})
              AND (
                (i.links_bocg_json IS NOT NULL AND TRIM(i.links_bocg_json) <> '')
                OR (i.links_ds_json IS NOT NULL AND TRIM(i.links_ds_json) <> '')
              )
              {missing_clause}
            ORDER BY {order_priority_sql} ASC, {leg_order_sql} DESC, i.updated_at DESC, i.initiative_id ASC
            LIMIT ?
            """

    rows = conn.execute(sql, (*source_list, int(limit_initiatives))).fetchall()

    initiatives_seen = len(rows)
    initiative_ids = [normalize_ws(str(r["initiative_id"] or "")) for r in rows]

    # When draining only missing docs, avoid spending per-initiative caps on URLs
    # that are already materialized. Otherwise max-docs-per-initiative=1 can keep
    # re-selecting the same downloaded first URL and starve missing secondary URLs.
    downloaded_urls_by_initiative: dict[str, set[str]] = {}
    if only_missing and initiative_ids:
        chunk = 800
        uniq_ids: list[str] = []
        seen_ids: set[str] = set()
        for iid in initiative_ids:
            if not iid or iid in seen_ids:
                continue
            seen_ids.add(iid)
            uniq_ids.append(iid)
        for i in range(0, len(uniq_ids), chunk):
            batch = uniq_ids[i : i + chunk]
            qmarks = ",".join("?" for _ in batch)
            fetched_rows = conn.execute(
                f"""
                SELECT initiative_id, doc_url
                FROM parl_initiative_documents
                WHERE initiative_id IN ({qmarks})
                  AND source_record_pk IS NOT NULL
                """,
                batch,
            ).fetchall()
            for fr in fetched_rows:
                iid = normalize_ws(str(fr["initiative_id"] or ""))
                url = _canonical_url(str(fr["doc_url"] or ""))
                if not iid or not url:
                    continue
                downloaded_urls_by_initiative.setdefault(iid, set()).add(url)

    derived_ini_candidates = 0
    derived_ini_selected = 0
    skipped_redundant_global_urls = 0
    doc_entries: list[dict[str, Any]] = []
    for r in rows:
        initiative_id = normalize_ws(str(r["initiative_id"] or ""))
        initiative_source_id = normalize_ws(str(r["source_id"] or ""))
        if not initiative_id:
            continue

        for doc_kind, raw_links in (
            ("bocg", r["links_bocg_json"]),
            ("ds", r["links_ds_json"]),
        ):
            links_raw = normalize_ws(str(raw_links or ""))
            if not links_raw:
                continue
            urls: list[str] = []
            try:
                parsed = json.loads(links_raw)
                if isinstance(parsed, list):
                    urls = [normalize_ws(str(u or "")) for u in parsed]
                else:
                    urls = []
            except Exception:  # noqa: BLE001
                urls = []

            urls = [u for u in urls if u.startswith("http")]
            if not urls:
                continue
            original_canon_urls = {_canonical_url(u) for u in urls if _canonical_url(u)}

            # Senado tail recovery: when a global_enmiendas URL is present, prepend the corresponding
            # INI XML URL so low per-initiative caps can still fetch useful metadata/context.
            derived_canon_urls: set[str] = set()
            if initiative_source_id == "senado_iniciativas" and doc_kind == "bocg":
                expanded_urls: list[str] = []
                for u in urls:
                    ini_url = _derive_senado_ini_url_from_global_enmiendas(u)
                    ini_canon = _canonical_url(ini_url or "")
                    if ini_url and ini_canon and ini_canon not in original_canon_urls and ini_canon not in derived_canon_urls:
                        derived_ini_candidates += 1
                        derived_canon_urls.add(ini_canon)
                        expanded_urls.append(ini_url)
                    expanded_urls.append(u)
                urls = expanded_urls

            seen_urls: set[str] = set()
            kept = 0
            has_downloaded_senado_bocg_alt = False
            if only_missing and initiative_source_id == "senado_iniciativas" and doc_kind == "bocg":
                has_downloaded_senado_bocg_alt = _has_senado_bocg_alternative(
                    downloaded_urls_by_initiative.get(initiative_id, set())
                )
            for u in urls:
                if kept >= int(max_docs_per_initiative):
                    break
                u_canon = _canonical_url(u)
                if not u_canon or u_canon in seen_urls:
                    continue
                if only_missing and u_canon in downloaded_urls_by_initiative.get(initiative_id, set()):
                    continue
                is_derived_probe = u_canon in derived_canon_urls
                if only_missing and has_downloaded_senado_bocg_alt and (
                    is_derived_probe or _is_senado_global_enmiendas_url(u_canon)
                ):
                    # Once an initiative already has a BOCG alternative document (INI/detail/publication),
                    # retrying stale global_enmiendas URLs (or their derived probe URLs) only creates churn.
                    skipped_redundant_global_urls += 1
                    continue
                seen_urls.add(u_canon)
                kept += 1
                if is_derived_probe:
                    derived_ini_selected += 1
                doc_entries.append(
                    {
                        "initiative_id": initiative_id,
                        "doc_kind": doc_kind,
                        "doc_url": u_canon,
                        "is_derived_probe": bool(is_derived_probe),
                    }
                )

    # Dedupe per-initiative rows.
    dedup: set[tuple[str, str, str]] = set()
    doc_entries_deduped: list[dict[str, Any]] = []
    for e in doc_entries:
        key = (str(e["initiative_id"]), str(e["doc_kind"]), str(e["doc_url"]))
        if key in dedup:
            continue
        dedup.add(key)
        doc_entries_deduped.append(e)
    doc_entries = doc_entries_deduped

    doc_links_seen = len(doc_entries)
    candidate_urls = sorted({str(e["doc_url"]) for e in doc_entries if str(e.get("doc_url") or "").startswith("http")})

    # Resolve already-fetched URLs (keyed by canonical URL).
    existing_pk_by_url: dict[str, int] = {}
    if only_missing and candidate_urls:
        chunk = 800
        for i in range(0, len(candidate_urls), chunk):
            batch = candidate_urls[i : i + chunk]
            qmarks = ",".join("?" for _ in batch)
            fetched = conn.execute(
                f"""
                SELECT source_url, source_record_pk
                FROM text_documents
                WHERE source_id = ?
                  AND source_url IN ({qmarks})
                  AND source_record_pk IS NOT NULL
                """,
                (INITIATIVE_DOC_SOURCE_ID, *batch),
            ).fetchall()
            for row in fetched:
                try:
                    url = normalize_ws(str(row["source_url"] or ""))
                    pk = int(row["source_record_pk"])
                except Exception:  # noqa: BLE001
                    continue
                if url and url not in existing_pk_by_url:
                    existing_pk_by_url[url] = pk

    fetch_status = _fetch_status_by_url(conn, urls=candidate_urls)

    urls_to_fetch = [u for u in candidate_urls if u not in existing_pk_by_url] if only_missing else list(candidate_urls)
    if fetch_status and urls_to_fetch:

        def _url_priority(u: str) -> tuple[int, int, str, str]:
            st = fetch_status.get(u) or {}
            attempts = int(st.get("attempts") or 0)
            fetched = int(st.get("fetched_ok") or 0)
            last_http = int(st.get("last_http_status") or 0)
            last_attempt = normalize_ws(str(st.get("last_attempt_at") or "")) or ""
            hard_fail = 1 if attempts > 0 and fetched == 0 and last_http in _SKIP_HTTP_STATUSES_DEFAULT else 0
            return (hard_fail, attempts, last_attempt, u)

        urls_to_fetch = sorted(urls_to_fetch, key=_url_priority)
    skipped_forbidden = 0
    archive_first_urls: set[str] = set()
    if not retry_forbidden and fetch_status:
        filtered: list[str] = []
        for u in urls_to_fetch:
            st = fetch_status.get(u) or {}
            attempts = int(st.get("attempts") or 0)
            fetched = int(st.get("fetched_ok") or 0)
            last_http = int(st.get("last_http_status") or 0)
            hard_failed = attempts > 0 and fetched == 0 and last_http in _SKIP_HTTP_STATUSES_DEFAULT
            if hard_failed:
                if archive_fallback and last_http in _ARCHIVE_FALLBACK_HTTP_STATUSES_DEFAULT:
                    archive_first_urls.add(u)
                    filtered.append(u)
                    continue
                skipped_forbidden += 1
                continue
            filtered.append(u)
        urls_to_fetch = filtered

    failures: list[str] = []
    sr_rows: list[dict[str, Any]] = []
    td_rows: list[tuple[Any, ...]] = []
    skipped_existing = len(candidate_urls) - len(urls_to_fetch) if only_missing else 0
    fetched_ok = 0

    archive_lookup_attempted = 0
    archive_hits = 0
    archive_fetched_ok = 0
    archive_lookup_failures: list[str] = []
    archive_lookup_cache: dict[str, tuple[list[str], str | None] | None] = {}

    by_url_cache: dict[str, tuple[bytes, str | None, str, str | None, str]] = {}

    pw_cfg: _PlaywrightFetchConfig | None = None
    if playwright_user_data_dir:
        pw_cfg = _PlaywrightFetchConfig(
            user_data_dir=str(playwright_user_data_dir),
            channel=str(playwright_channel or "chrome"),
            headless=bool(playwright_headless),
        )

    pw_fetcher: _PlaywrightFetcher | None = None

    def fetch_one(url: str) -> tuple[bytes, str | None]:
        nonlocal pw_fetcher
        headers = {"Accept": "application/pdf,text/html,*/*"}
        cookie_value = normalize_ws(str(cookie or ""))
        if cookie_value:
            headers["Cookie"] = cookie_value

        host = (urlparse(url).netloc or "").lower()
        use_playwright = bool(pw_cfg) and (host.endswith("senado.es") or host.endswith("www.senado.es"))
        if use_playwright:
            if pw_fetcher is None:
                pw_fetcher = _PlaywrightFetcher(pw_cfg)  # type: ignore[arg-type]
                pw_fetcher.__enter__()
            # Prefer browser session state (cookies/storage) from the persistent profile.
            # Avoid injecting Cookie header here; it can conflict with browser-managed cookies.
            return pw_fetcher.get_bytes(url, timeout_seconds=int(timeout), headers={k: v for k, v in headers.items() if k.lower() != "cookie"})

        return http_get_bytes(url, timeout=int(timeout), headers=headers)

    def _lookup_archive_candidates_cached(url: str) -> tuple[list[str], str | None]:
        nonlocal archive_lookup_attempted
        nonlocal archive_hits
        if url in archive_lookup_cache:
            cached = archive_lookup_cache[url]
            if cached is None:
                return [], None
            return cached
        archive_lookup_attempted += 1
        try:
            candidates, timestamp = _lookup_wayback_candidates(url, timeout=archive_timeout)
        except Exception as exc:  # noqa: BLE001
            archive_lookup_failures.append(f"url={url} -> {type(exc).__name__}: {exc}")
            archive_lookup_cache[url] = None
            return [], None
        if candidates:
            archive_hits += 1
            archive_lookup_cache[url] = (candidates, timestamp)
            return candidates, timestamp
        archive_lookup_cache[url] = None
        return [], None

    def _fetch_one_archive(url: str) -> tuple[bytes, str | None, str, str | None]:
        candidates, timestamp = _lookup_archive_candidates_cached(url)
        if not candidates:
            raise HTTPStatusError(404, "archive fallback: no snapshot candidates")
        headers = {"Accept": "application/pdf,text/html,*/*"}
        last_exc: Exception | None = None
        for archived_url in candidates:
            try:
                payload, content_type = http_get_bytes(
                    archived_url,
                    timeout=archive_timeout,
                    headers=headers,
                )
                return payload, content_type, archived_url, timestamp
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                continue
        if last_exc is not None:
            status = _exception_http_status(last_exc) or 599
            raise HTTPStatusError(status, f"archive fallback failed: {type(last_exc).__name__}: {last_exc}")
        raise HTTPStatusError(404, "archive fallback failed: no archived candidates")

    try:
        for url in urls_to_fetch:
            payload_bytes: bytes | None = None
            content_type: str | None = None
            fetched_from_url = url
            fetch_method = "direct"
            archive_timestamp: str | None = None
            try:
                cached = by_url_cache.get(url)
                if cached is not None:
                    payload_bytes, content_type, fetched_from_url, archive_timestamp, fetch_method = cached
                else:
                    if archive_fallback and url in archive_first_urls:
                        payload_bytes, content_type, fetched_from_url, archive_timestamp = _fetch_one_archive(url)
                        fetch_method = "archive_wayback"
                        archive_fetched_ok += 1
                    else:
                        try:
                            payload_bytes, content_type = fetch_one(url)
                        except Exception as direct_exc:  # noqa: BLE001
                            direct_status = _exception_http_status(direct_exc)
                            if archive_fallback and direct_status in _ARCHIVE_FALLBACK_HTTP_STATUSES_DEFAULT:
                                payload_bytes, content_type, fetched_from_url, archive_timestamp = _fetch_one_archive(url)
                                fetch_method = "archive_wayback"
                                archive_fetched_ok += 1
                            else:
                                raise
                    by_url_cache[url] = (
                        payload_bytes,
                        content_type,
                        fetched_from_url,
                        archive_timestamp,
                        fetch_method,
                    )

                assert payload_bytes is not None
                ext = _guess_ext(payload_bytes, content_type)
                content_sha = sha256_bytes(payload_bytes)
                raw_path = _raw_path_for_content(
                    raw_dir,
                    source_id=INITIATIVE_DOC_SOURCE_ID,
                    content_sha=content_sha,
                    ext=ext,
                )
                if not dry_run and not raw_path.exists():
                    raw_path.write_bytes(payload_bytes)

                excerpt = None
                text_chars = None
                if ext == "html":
                    html = payload_bytes.decode("utf-8", errors="replace")
                    excerpt_text = _strip_html(html)
                    if excerpt_text:
                        excerpt = excerpt_text[:4000]
                        text_chars = len(excerpt_text)

                sr_payload_obj: dict[str, Any] = {
                    "url": url,
                    "snapshot_date": snapshot_date or "",
                    "fetch_method": fetch_method,
                }
                if fetched_from_url and fetched_from_url != url:
                    sr_payload_obj["fetched_from_url"] = fetched_from_url
                if archive_timestamp:
                    sr_payload_obj["archive_timestamp"] = archive_timestamp
                sr_payload = stable_json(sr_payload_obj)
                sr_rows.append(
                    {
                        "source_record_id": url,
                        "raw_payload": sr_payload,
                        "content_sha256": content_sha,
                    }
                )
                td_rows.append(
                    (
                        INITIATIVE_DOC_SOURCE_ID,
                        url,
                        url,  # placeholder for pk_map lookup
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
                fetched_ok += 1
                if not dry_run:
                    _upsert_document_fetch_status(
                        conn,
                        source_id=INITIATIVE_DOC_SOURCE_ID,
                        doc_url=url,
                        now_iso=now_iso,
                        fetched_ok=True,
                        http_status=200,
                        error=None,
                        content_type=content_type,
                        content_sha256=content_sha,
                        bytes_len=len(payload_bytes),
                        raw_path=str(raw_path),
                    )
            except Exception as exc:  # noqa: BLE001
                failures.append(f"url={url} -> {type(exc).__name__}: {exc}")
                http_status = _exception_http_status(exc)
                if not dry_run:
                    _upsert_document_fetch_status(
                        conn,
                        source_id=INITIATIVE_DOC_SOURCE_ID,
                        doc_url=url,
                        now_iso=now_iso,
                        fetched_ok=False,
                        http_status=http_status,
                        error=f"{type(exc).__name__}: {exc}",
                        content_type=None,
                        content_sha256=None,
                        bytes_len=None,
                        raw_path=None,
                    )
                if strict_network:
                    raise
            finally:
                base_sleep = float(sleep_seconds or 0.0)
                jitter = float(sleep_jitter_seconds or 0.0)
                if base_sleep > 0.0 or jitter > 0.0:
                    time.sleep(max(0.0, base_sleep) + random.uniform(0.0, max(0.0, jitter)))
    finally:
        if pw_fetcher is not None:
            pw_fetcher.__exit__(None, None, None)

    pk_map: dict[str, int] = {}
    if sr_rows and not dry_run:
        pk_map = upsert_source_records_with_content_sha256(
            conn,
            source_id=INITIATIVE_DOC_SOURCE_ID,
            rows=sr_rows,
            snapshot_date=snapshot_date,
            now_iso=now_iso,
        )

    # Upsert text_documents keyed by source_record_pk.
    if td_rows and not dry_run:
        params: list[tuple[Any, ...]] = []
        for (
            td_source_id,
            td_source_url,
            td_source_record_id,
            fetched_at,
            content_type,
            content_sha,
            bytes_len,
            raw_path,
            excerpt,
            text_chars,
            created_at,
            updated_at,
        ) in td_rows:
            sr_pk = pk_map.get(str(td_source_record_id))
            if sr_pk is None:
                continue
            params.append(
                (
                    td_source_id,
                    td_source_url,
                    int(sr_pk),
                    fetched_at,
                    content_type,
                    content_sha,
                    int(bytes_len),
                    raw_path,
                    excerpt,
                    int(text_chars) if text_chars is not None else None,
                    created_at,
                    updated_at,
                )
            )
        if params:
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
                    params,
                )

    # Upsert initiative -> document mapping (url rows are valuable even when download failed).
    mapping_rows: list[tuple[Any, ...]] = []
    derived_probe_unfetched_skipped = 0
    for e in doc_entries:
        url = str(e["doc_url"])
        sr_pk = existing_pk_by_url.get(url) or pk_map.get(url)
        if bool(e.get("is_derived_probe")) and sr_pk is None:
            derived_probe_unfetched_skipped += 1
            continue
        mapping_rows.append(
            (
                str(e["initiative_id"]),
                str(e["doc_kind"]),
                url,
                int(sr_pk) if sr_pk is not None else None,
                now_iso,
                now_iso,
            )
        )

    if mapping_rows and not dry_run:
        with conn:
            conn.executemany(
                """
                INSERT INTO parl_initiative_documents (
                  initiative_id, doc_kind, doc_url, source_record_pk,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(initiative_id, doc_kind, doc_url) DO UPDATE SET
                  source_record_pk = COALESCE(excluded.source_record_pk, parl_initiative_documents.source_record_pk),
                  updated_at = excluded.updated_at
                """,
                mapping_rows,
            )

    return {
        "dry_run": bool(dry_run),
        "initiative_source_ids": source_list,
        "archive_fallback": bool(archive_fallback),
        "initiatives_seen": initiatives_seen,
        "doc_links_seen": doc_links_seen,
        "candidate_urls": len(candidate_urls),
        "urls_to_fetch": len(urls_to_fetch),
        "derived_ini_candidates": derived_ini_candidates,
        "derived_ini_selected": derived_ini_selected,
        "derived_probe_unfetched_skipped": derived_probe_unfetched_skipped,
        "skipped_redundant_global_urls": skipped_redundant_global_urls,
        "skipped_existing": skipped_existing,
        "skipped_forbidden": skipped_forbidden,
        "archive_first_urls": len(archive_first_urls),
        "archive_lookup_attempted": archive_lookup_attempted,
        "archive_hits": archive_hits,
        "archive_fetched_ok": archive_fetched_ok,
        "archive_lookup_failures": archive_lookup_failures[:30],
        "fetched_ok": fetched_ok,
        "text_documents_upserted": len(pk_map),
        "initiative_documents_upserted": len(mapping_rows) if not dry_run else 0,
        "failures": failures[:30],
    }

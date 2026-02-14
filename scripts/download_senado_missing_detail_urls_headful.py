#!/usr/bin/env python3
"""Download Senado detail XML URLs from a list with a headful browser fallback.

Workflow:
- Try plain HTTP download first (fast and reproducible).
- If HTTP fails and headful fallback is enabled, open the URL in a visible browser
  (Playwright Chromium/Chrome), wait for any WAF challenge to be solved manually,
  then save page content as XML.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import sys


UA = "Mozilla/5.0 (compatible; etl-script/1.0)"
URL_RE = re.compile(r"/legis(?P<leg>\d+)/votaciones/")


def _normalize_url(raw: str) -> str:
    u = (raw or "").strip()
    if u.startswith("url:"):
        u = u[4:].strip()
    return u


def _output_path(url: str, out_root: Path) -> Path:
    leg = "unknown"
    match = URL_RE.search(url)
    if match:
        leg = match.group("leg")
    out_dir = out_root / f"legis{leg}"
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(urlparse(url).path).name
    if not filename:
        filename = f"ses_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:10]}.xml"
    if not filename.lower().endswith(".xml"):
        filename = f"{filename}.xml"
    return out_dir / filename


def _looks_html(payload: bytes) -> bool:
    if not payload:
        return True
    text = payload.lstrip()[:1024].lower()
    if not text:
        return True
    if text.startswith(b"<!doctype html") or text.startswith(b"<html"):
        return True
    return b"<html" in text


def _looks_xml(payload: bytes) -> bool:
    if not payload or _looks_html(payload):
        return False
    txt = payload.lstrip()[:4].lower()
    return txt.startswith(b"<?xm") or txt.startswith(b"<")


def _fetch_with_http(url: str, *, timeout: int, cookie: str | None = None) -> bytes:
    headers = {
        "User-Agent": UA,
        "Accept": "application/xml,text/xml,*/*",
    }
    if cookie:
        headers["Cookie"] = cookie

    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        ct = resp.headers.get("Content-Type") or ""
        payload = resp.read()
    if "text/html" in ct.lower():
        raise RuntimeError(f"content-type unexpected: {ct!r}")
    if not _looks_xml(payload):
        raise RuntimeError("response is not XML-like payload")
    return payload


def _is_blocked(title: str, url: str, html: str) -> bool:
    t = (title or "").lower()
    u = (url or "").lower()
    h = (html or "").lower()

    if ("just a moment" in t) or ("un momento" in t):
        if "_cf_chl_opt" in h:
            return True
    if "enable javascript and cookies to continue" in h:
        return True
    if "performing security verification" in h:
        return True
    if "__cf_chl" in u:
        return True
    if "access denied" in t:
        return True
    if "errors.edgesuite.net" in h:
        return True
    if "you don't have permission to access" in h:
        return True
    return False


class HeadfulFetcher:
    def __init__(
        self,
        *,
        timeout: int,
        challenge_wait_seconds: int,
        channel: str,
        viewport: str,
        user_data_dir: str,
    ) -> None:
        self.timeout = int(timeout)
        self.challenge_wait_seconds = int(challenge_wait_seconds)
        self.channel = channel or "chrome"
        self.viewport = viewport
        self.user_data_dir = user_data_dir
        self._playwright = None
        self._context = None
        self._page = None
        self._pw_mod = None

    def __enter__(self) -> "HeadfulFetcher":
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as e:
            raise RuntimeError("Playwright not available. Install/playwright: python3 -m pip install playwright && python3 -m playwright install chromium") from e

        self._pw_mod = sync_playwright()
        p = self._pw_mod.__enter__()
        w, h = 1280, 800
        try:
            w_s, h_s = self.viewport.lower().split("x", 1)
            w = int(w_s)
            h = int(h_s)
        except Exception:
            pass

        self._context = p.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=False,
            channel=self.channel or None,
            locale="es-ES",
            timezone_id="Europe/Madrid",
            viewport={"width": w, "height": h},
            args=["--disable-dev-shm-usage", "--no-default-browser-check"],
        )
        self._page = self._context.new_page()
        self._page.set_extra_http_headers({"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"})
        return self

    def __exit__(self, *_exc: Any) -> None:
        if self._page is not None:
            try:
                self._page.close()
            except Exception:
                pass
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
        if self._pw_mod is not None:
            try:
                self._pw_mod.__exit__(None, None, None)
            except Exception:
                pass

    def _await_clearance(self, url: str, *, deadline: float) -> None:
        if self._page is None:
            return
        page = self._page
        while True:
            try:
                title = page.title()
            except Exception:
                title = ""
            try:
                cur_url = page.url
            except Exception:
                cur_url = ""
            try:
                html = page.content()
            except Exception:
                html = ""

            if not _is_blocked(title, cur_url, html):
                return

            now = time.time()
            if now >= deadline:
                raise RuntimeError(f"still blocked at {url!r} title={title!r} url={cur_url!r}")

            remaining = int(deadline - now)
            print(
                f"[pw] blocked by challenge, waiting for manual solve ({remaining}s): "
                f"title={title!r} url={cur_url!r}"
            )
            time.sleep(min(10, remaining))
            try:
                page.reload(timeout=self.timeout * 1000)
            except Exception:
                time.sleep(2)

    def fetch(self, url: str) -> bytes:
        if self._page is None:
            raise RuntimeError("headful fetcher is not initialized")

        page = self._page
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            self._await_clearance(url, deadline=time.time() + self.challenge_wait_seconds)
            page.wait_for_load_state("networkidle", timeout=10_000)
            html = page.content()
            payload = html.encode("utf-8")
            if not _looks_xml(payload):
                raise RuntimeError("headful content is not XML-like")
            return payload
        except Exception as e:
            raise RuntimeError(f"headful fetch failed: {e}") from e


def _parse_viewport(value: str) -> str:
    value = (value or "").strip() or "1280x800"
    if re.fullmatch(r"\d+x\d+", value.lower()):
        return value.lower()
    return "1280x800"


def _read_urls(paths: list[str]) -> list[str]:
    lines: list[str] = []
    for p in paths:
        text = Path(p).read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            url = _normalize_url(line)
            if not url or url in lines:
                continue
            lines.append(url)
    return lines


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download senado detail XMLs from URL list with optional headful browser fallback."
    )
    p.add_argument("--urls-file", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--headful-timeout", type=int, default=30)
    p.add_argument("--headful-wait-seconds", type=int, default=90)
    p.add_argument("--channel", default="chrome")
    p.add_argument("--viewport", default="1280x800")
    p.add_argument("--user-data-dir", default="etl/data/raw/manual/senado_votaciones_ses/.headful-profile")
    p.add_argument("--cookie", default="")
    p.add_argument(
        "--no-headful-fallback",
        action="store_true",
        help="Do not open browser fallback; fail when normal HTTP does not work.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    urls = _read_urls([args.urls_file])
    if not urls:
        print("No URLs found.")
        return 1

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    viewport = _parse_viewport(args.viewport)

    fetcher = None
    success = 0
    skipped = 0
    failed = 0

    for i, url in enumerate(urls, start=1):
        out_file = _output_path(url, out_root)
        if out_file.exists():
            skipped += 1
            print(f"[skip {i}/{len(urls)}] {url}")
            continue

        payload = None
        method = "http"
        try:
            payload = _fetch_with_http(url, timeout=args.timeout, cookie=(args.cookie or "").strip() or None)
        except (HTTPError, URLError, OSError, ValueError, RuntimeError) as exc:
            if args.no_headful_fallback:
                print(f"[fail {i}/{len(urls)}] {url} via http: {exc}", file=sys.stderr)
                failed += 1
                continue
            if fetcher is None:
                try:
                    fetcher = HeadfulFetcher(
                        timeout=args.headful_timeout,
                        challenge_wait_seconds=args.headful_wait_seconds,
                        channel=args.channel,
                        viewport=viewport,
                        user_data_dir=args.user_data_dir,
                    )
                    fetcher.__enter__()
                except Exception as exc_h:
                    print(f"[fail {i}/{len(urls)}] {url} via headful init: {exc_h}", file=sys.stderr)
                    failed += 1
                    continue
            try:
                payload = fetcher.fetch(url)
                method = "headful"
            except Exception as exc_h:
                print(f"[fail {i}/{len(urls)}] {url}: {exc_h}", file=sys.stderr)
                failed += 1
                continue

        if payload is None:
            failed += 1
            continue

        try:
            out_file.write_bytes(payload)
            success += 1
            print(f"[ok:{method} {i}/{len(urls)}] {url} -> {out_file}")
        except OSError as exc:
            print(f"[fail {i}/{len(urls)}] save {url}: {exc}", file=sys.stderr)
            failed += 1

    if fetcher is not None:
        fetcher.__exit__()

    print(f"Summary: ok={success} skipped={skipped} fail={failed}")
    if failed:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Batch capture pages using an interactive (non-headless) Chrome via Playwright.

This differs from `manual_crawl_playwright.py`:
- It creates a fresh browser *context* per URL (clean cookies/storage per page),
  which can reduce Cloudflare/WAF challenges that appear after sequential
  navigation in a single context.
- Link extraction is done from a local HTML snapshot (no network fetch needed).

Outputs go under `etl/data/raw/manual/<label>_<timestamp>/`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_filename(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "_", s)
    s = s.strip("_.-")
    return s or "out"


def extract_hrefs(html: str) -> list[str]:
    # Conservative extraction: href="...". Good enough for these pages.
    return re.findall(r'href=\"([^\"]+)\"', html, flags=re.IGNORECASE)


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch capture pages (fresh context per URL)")
    ap.add_argument("--label", required=True)
    ap.add_argument("--links-from-html", required=True, help="Local HTML file containing links to capture.")
    ap.add_argument("--resolve-base-url", required=True, help="Base URL for resolving relative hrefs.")

    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--href-prefix")
    g.add_argument("--href-regex")

    ap.add_argument("--out-dir", default="etl/data/raw/manual")
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--delay-seconds", type=float, default=0.8)
    ap.add_argument("--delay-jitter-seconds", type=float, default=0.6)
    ap.add_argument("--page-timeout-seconds", type=int, default=120)
    ap.add_argument("--post-load-wait-seconds", type=float, default=0.5)
    ap.add_argument("--channel", default="chrome")
    ap.add_argument("--viewport", default="1280x800")
    ap.add_argument("--save-screenshots", action="store_true")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as e:
        print(
            "[pw] Playwright not available. Install:\n"
            "  python3 -m pip install playwright\n"
            "  python3 -m playwright install chromium\n"
            f"[pw] import error: {e!r}",
            file=sys.stderr,
        )
        return 2

    vw, vh = 1280, 800
    try:
        vw, vh = [int(x) for x in args.viewport.lower().split("x", 1)]
    except Exception:
        pass

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"{sanitize_filename(args.label)}_{stamp}"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    html = pathlib.Path(args.links_from_html).read_text(encoding="utf-8", errors="replace")
    hrefs = extract_hrefs(html)

    kept: list[str] = []
    if args.href_prefix:
        kept = [h for h in hrefs if h.startswith(args.href_prefix)]
    else:
        rx = re.compile(args.href_regex or "")
        kept = [h for h in hrefs if rx.search(h)]

    abs_links: list[str] = [urljoin(args.resolve_base_url, h) for h in kept]
    seen: set[str] = set()
    links: list[str] = []
    for u in abs_links:
        if u in seen:
            continue
        seen.add(u)
        links.append(u)

    if args.max_pages and args.max_pages > 0:
        links = links[: args.max_pages]

    meta: dict = {
        "started_at": now_iso(),
        "label": args.label,
        "links_from_html": args.links_from_html,
        "resolve_base_url": args.resolve_base_url,
        "href_prefix": args.href_prefix,
        "href_regex": args.href_regex,
        "links": links,
        "visited": [],
        "errors": [],
        "channel": args.channel,
        "viewport": {"width": vw, "height": vh},
        "save_screenshots": bool(args.save_screenshots),
    }

    def save_meta() -> None:
        (run_dir / "run.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    run_dir.mkdir(parents=True, exist_ok=True)
    save_meta()

    print(f"[pw] run dir: {run_dir}")
    print(f"[pw] urls to capture: {len(links)}")
    sys.stdout.flush()

    def delay() -> None:
        d = max(0.0, args.delay_seconds) + random.uniform(0.0, max(0.0, args.delay_jitter_seconds))
        time.sleep(d)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            channel=args.channel or None,
            args=[
                "--disable-dev-shm-usage",
                "--no-default-browser-check",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        for i, url in enumerate(links, start=1):
            rec = {"i": i, "url": url, "started_at": now_iso()}
            try:
                delay()
                context = browser.new_context(
                    locale="es-ES",
                    timezone_id="Europe/Madrid",
                    viewport={"width": vw, "height": vh},
                )
                page = context.new_page()
                page.set_extra_http_headers({"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"})

                resp = page.goto(url, wait_until="domcontentloaded", timeout=args.page_timeout_seconds * 1000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except Exception:
                    pass
                if args.post_load_wait_seconds > 0:
                    time.sleep(args.post_load_wait_seconds)

                title = page.title()
                final_url = page.url
                content = page.content()

                parsed = urlparse(final_url)
                tail = sanitize_filename(parsed.path.strip("/").split("/")[-1] or f"page_{i}")
                out_base = pages_dir / f"{i:03d}_{tail}"
                out_base.with_suffix(".html").write_text(content, encoding="utf-8")
                if args.save_screenshots:
                    try:
                        page.screenshot(path=str(out_base) + ".png", full_page=True)
                    except Exception:
                        pass

                rec.update(
                    {
                        "status": resp.status if resp else None,
                        "title": title,
                        "final_url": final_url,
                        "html_len": len(content),
                        "saved_html": str(out_base.with_suffix(".html")),
                        "ended_at": now_iso(),
                    }
                )
                meta["visited"].append(rec)
                if i % 10 == 0:
                    save_meta()
                print(f"[pw] {i}/{len(links)} ok status={rec['status']} title={title!r}")
                sys.stdout.flush()
            except Exception as e:
                rec.update({"status": "error", "error": repr(e), "ended_at": now_iso()})
                meta["visited"].append(rec)
                meta["errors"].append({"i": i, "url": url, "error": repr(e), "ts": now_iso()})
                save_meta()
                print(f"[pw] {i}/{len(links)} ERROR {e!r}", file=sys.stderr)
                sys.stderr.flush()
            finally:
                try:
                    context.close()
                except Exception:
                    pass

        meta["ended_at"] = now_iso()
        save_meta()
        print(f"[pw] done: visited={len(meta['visited'])} errors={len(meta['errors'])}")
        sys.stdout.flush()
        time.sleep(1)
        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


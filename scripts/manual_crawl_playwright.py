"""
Interactive (non-headless) Playwright crawler for manual snapshots.

Goal:
- Some sources block curl/requests but load in a real browser.
- Crawl a list page, extract profile links by href prefix or regex,
  visit each link, and save HTML + screenshot + a small meta JSON.

Outputs go under `etl/data/raw/manual/` by default, which is ignored by git.
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


def is_challenge_or_deny(title: str, url: str, html: str) -> bool:
    t = (title or "").lower()
    u = (url or "").lower()
    h = (html or "").lower()

    # Cloudflare
    # Only treat as blocked when we see strong markers of an interstitial
    # challenge page (not merely Cloudflare JS being present on an otherwise
    # normal page).
    title_says_challenge = ("just a moment" in t) or ("un momento" in t)
    # Some sites include Cloudflare JS (e.g. /cdn-cgi/.../jsd/main.js) even when
    # the page is accessible. Treat it as blocked only when we see a real
    # interactive challenge page marker.
    has_chl_opt = "_cf_chl_opt" in h
    if title_says_challenge and has_chl_opt:
        return True
    if "enable javascript and cookies to continue" in h:
        return True
    if "performing security verification" in h:
        return True
    if "__cf_chl" in u:
        return True

    # Akamai / generic deny
    if "access denied" in t:
        return True
    if "errors.edgesuite.net" in h:
        return True
    if "you don't have permission to access" in h:
        return True

    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Interactive Playwright crawler")
    ap.add_argument("--start-url", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out-dir", default="etl/data/raw/manual")

    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--href-prefix", help="Only keep links whose href starts with this prefix")
    g.add_argument("--href-regex", help="Only keep links whose href matches this regex")

    ap.add_argument("--max-pages", type=int, default=0, help="0 = no limit")
    ap.add_argument("--delay-seconds", type=float, default=0.6)
    ap.add_argument("--delay-jitter-seconds", type=float, default=0.4)
    ap.add_argument("--wait-seconds-before-crawl", type=int, default=10)
    ap.add_argument("--challenge-wait-seconds", type=int, default=120)
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
    run_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    meta: dict = {
        "started_at": now_iso(),
        "label": args.label,
        "start_url": args.start_url,
        "href_prefix": args.href_prefix,
        "href_regex": args.href_regex,
        "max_pages": args.max_pages,
        "delay_seconds": args.delay_seconds,
        "delay_jitter_seconds": args.delay_jitter_seconds,
        "wait_seconds_before_crawl": args.wait_seconds_before_crawl,
        "challenge_wait_seconds": args.challenge_wait_seconds,
        "channel": args.channel,
        "viewport": {"width": vw, "height": vh},
        "save_screenshots": bool(args.save_screenshots),
        "links": [],
        "visited": [],
        "errors": [],
    }

    def save_meta() -> None:
        (run_dir / "run.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"[pw] run dir: {run_dir}")
    print(f"[pw] opening: {args.start_url}")
    print(f"[pw] after load, waiting {args.wait_seconds_before_crawl}s before extracting links")
    sys.stdout.flush()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(run_dir / "profile"),
            headless=False,
            channel=args.channel or None,
            locale="es-ES",
            timezone_id="Europe/Madrid",
            viewport={"width": vw, "height": vh},
            args=["--no-default-browser-check"],
        )

        page = ctx.new_page()
        page.set_extra_http_headers({"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"})

        def ensure_not_blocked(where: str) -> None:
            deadline = time.time() + args.challenge_wait_seconds
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

                if not is_challenge_or_deny(title, cur_url, html):
                    return

                if time.time() >= deadline:
                    raise RuntimeError(f"still blocked at {where}: title={title!r} url={cur_url!r}")

                print(
                    f"[pw] blocked at {where}: title={title!r} url={cur_url!r} "
                    f"(waiting up to {int(deadline-time.time())}s for you to solve it)"
                )
                sys.stdout.flush()
                time.sleep(5)

        try:
            page.goto(args.start_url, wait_until="domcontentloaded", timeout=120_000)
            ensure_not_blocked("start-url")
        except Exception as e:
            meta["errors"].append({"stage": "goto_start", "error": repr(e), "ts": now_iso()})
            save_meta()
            print(f"[pw] failed to open start url: {e!r}", file=sys.stderr)
            ctx.close()
            return 3

        time.sleep(max(0, args.wait_seconds_before_crawl))

        # Extract and normalize links.
        hrefs: list[str] = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)",
        )

        kept: list[str] = []
        if args.href_prefix:
            for h in hrefs:
                if h.startswith(args.href_prefix):
                    kept.append(h)
        else:
            rx = re.compile(args.href_regex or "")
            for h in hrefs:
                if rx.search(h):
                    kept.append(h)

        # Resolve relative to start_url's origin.
        base = args.start_url
        abs_links: list[str] = []
        for h in kept:
            abs_links.append(urljoin(base, h))

        # Deduplicate while preserving order.
        seen: set[str] = set()
        links: list[str] = []
        for u in abs_links:
            if u in seen:
                continue
            seen.add(u)
            links.append(u)

        if args.max_pages and args.max_pages > 0:
            links = links[: args.max_pages]

        meta["links"] = links
        save_meta()
        print(f"[pw] extracted links: {len(links)}")
        sys.stdout.flush()

        def delay() -> None:
            d = max(0.0, args.delay_seconds) + random.uniform(0.0, max(0.0, args.delay_jitter_seconds))
            time.sleep(d)

        for i, url in enumerate(links, start=1):
            rec = {"i": i, "url": url, "started_at": now_iso(), "status": None, "title": None, "final_url": None}
            try:
                delay()
                resp = page.goto(url, wait_until="domcontentloaded", timeout=120_000)
                ensure_not_blocked(f"visit:{i}")

                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except Exception:
                    pass

                title = page.title()
                final_url = page.url
                html = page.content()

                # File naming uses path tail.
                parsed = urlparse(final_url)
                tail = sanitize_filename(parsed.path.strip("/").split("/")[-1] or f"page_{i}")
                out_base = pages_dir / f"{i:03d}_{tail}"

                out_base.with_suffix(".html").write_text(html, encoding="utf-8")
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
                        "html_len": len(html),
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
                meta["errors"].append({"stage": "visit", "i": i, "url": url, "error": repr(e), "ts": now_iso()})
                save_meta()
                print(f"[pw] {i}/{len(links)} ERROR {e!r}", file=sys.stderr)
                sys.stderr.flush()

        meta["ended_at"] = now_iso()
        save_meta()
        print(f"[pw] done: visited={len(meta['visited'])} errors={len(meta['errors'])}")
        sys.stdout.flush()
        time.sleep(2)
        ctx.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

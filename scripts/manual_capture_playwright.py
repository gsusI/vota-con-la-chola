"""
Interactive (non-headless) browser capture for WAF/Cloudflare-blocked pages.

Use-case:
- Some sources block curl/requests but load in a real browser session.
- This script opens Chromium/Chrome with Playwright, gives you time to solve any
  challenges, and then saves HTML + screenshot + cookies/storage + a light
  network log under `etl/data/raw/manual/` (which is ignored by git).

Notes:
- This is intentionally a *manual* tool. It is not used by the normal Docker ETL.
- Cookies/storage may be sensitive; keep these artifacts out of git.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_filename(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "_", s)
    s = s.strip("_.-")
    return s or "out"


def main() -> int:
    ap = argparse.ArgumentParser(description="Interactive Playwright page capture")
    ap.add_argument("--url", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out-dir", default="etl/data/raw/manual")
    ap.add_argument("--wait-seconds", type=int, default=180)
    ap.add_argument("--channel", default="chrome", help="Playwright browser channel (e.g. chrome).")
    ap.add_argument("--viewport", default="1280x800")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as e:
        print(
            "[pw] Playwright is not installed. Install it with:\n"
            "  python3 -m pip install playwright\n"
            "  python3 -m playwright install chromium\n"
            f"[pw] import error: {e!r}",
            file=sys.stderr,
        )
        return 2

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = out_dir / f"{sanitize_filename(args.label)}_{stamp}"

    vw, vh = 1280, 800
    try:
        vw, vh = [int(x) for x in args.viewport.lower().split("x", 1)]
    except Exception:
        pass

    meta: dict = {
        "started_at": now_iso(),
        "url": args.url,
        "label": args.label,
        "wait_seconds": args.wait_seconds,
        "channel": args.channel,
        "viewport": {"width": vw, "height": vh},
        "network": [],
        "result": None,
    }

    print(f"[pw] opening interactive browser: {args.url}")
    print(
        "[pw] if you see any CAPTCHA/challenge, solve it in the window; "
        f"auto-capture in {args.wait_seconds}s"
    )
    sys.stdout.flush()

    with sync_playwright() as p:
        user_data_dir = str(base) + "_profile"
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            channel=args.channel or None,
            locale="es-ES",
            timezone_id="Europe/Madrid",
            viewport={"width": vw, "height": vh},
            args=["--no-default-browser-check"],
        )

        def on_response(resp) -> None:
            try:
                req = resp.request
                meta["network"].append(
                    {
                        "ts": now_iso(),
                        "status": resp.status,
                        "url": resp.url,
                        "resource_type": req.resource_type,
                        "method": req.method,
                        "content_type": resp.headers.get("content-type"),
                    }
                )
            except Exception:
                pass

        ctx.on("response", on_response)

        page = ctx.new_page()
        page.set_extra_http_headers({"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"})

        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=120_000)
        except Exception as e:
            meta["result"] = {"status": "goto_error", "error": repr(e), "ended_at": now_iso()}
            base.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            print(f"[pw] goto error: {e!r}", file=sys.stderr)
            sys.stdout.flush()
            time.sleep(5)
            ctx.close()
            return 3

        for i in range(args.wait_seconds):
            if i % 15 == 0:
                try:
                    print(f"[pw] t+{i}s title={page.title()!r} url={page.url!r}")
                    sys.stdout.flush()
                except Exception:
                    pass
            time.sleep(1)

        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass

        try:
            page.screenshot(path=str(base) + ".png", full_page=True)
        except Exception:
            pass

        try:
            base.with_suffix(".html").write_text(page.content(), encoding="utf-8")
        except Exception as e:
            meta.setdefault("errors", []).append({"write_html": repr(e)})

        # Cookies/storage can include session tokens. Keep in ignored raw folder.
        try:
            base.with_suffix(".storage.json").write_text(
                json.dumps(ctx.storage_state(), indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
        except Exception as e:
            meta.setdefault("errors", []).append({"write_storage": repr(e)})

        try:
            base.with_suffix(".cookies.json").write_text(
                json.dumps(ctx.cookies(), indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
        except Exception as e:
            meta.setdefault("errors", []).append({"write_cookies": repr(e)})

        try:
            meta["result"] = {
                "status": "captured",
                "title": page.title(),
                "final_url": page.url,
                "html_len": len(page.content()),
                "ended_at": now_iso(),
            }
        except Exception as e:
            meta["result"] = {"status": "captured_partial", "error": repr(e), "ended_at": now_iso()}

        base.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        print(
            f"[pw] saved: {base}.html {base}.png {base}.storage.json {base}.cookies.json {base}.meta.json"
        )
        sys.stdout.flush()

        time.sleep(2)
        ctx.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


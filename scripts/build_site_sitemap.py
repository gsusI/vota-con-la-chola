#!/usr/bin/env python3
"""Write sitemap.xml for the exported site from the pages it actually ships.

Walks <site>/**/index.html, skips pages marked noindex or whose canonical points to another URL,
and lists the rest by their canonical URL (or the page path when it has none). Runs after
`next build`, so new pages enter the sitemap without a hand-kept list.
"""
import argparse
import html
import os
import re
from pathlib import Path
from xml.sax.saxutils import escape

SITE_ORIGIN = os.environ.get("NEXT_PUBLIC_SITE_ORIGIN", "https://votaconlachola.org").rstrip("/")
SKIP_PREFIXES = ("404/", "_not-found/", "legacy/", "og/")
HEAD_RE = re.compile(r"<head[^>]*>(.*?)</head>", re.S | re.I)
ROBOTS_RE = re.compile(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', re.I)
CANONICAL_RE = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]*)"', re.I)
# Hubs and evergreen tools first: crawlers read priority only as a hint, but it orders our own report.
PRIORITY = (
    ("", "1.0"),
    ("visualizaciones/", "0.9"),
    ("citizen/vota/", "0.9"),
    ("citizen/", "0.7"),
)


def page_url(rel_dir: str) -> str:
    return f"{SITE_ORIGIN}/{rel_dir}" if rel_dir else f"{SITE_ORIGIN}/"


def priority_for(rel_dir: str) -> str:
    if rel_dir == "":
        return "1.0"
    for prefix, value in PRIORITY[1:]:
        if rel_dir.startswith(prefix):
            depth = rel_dir[len(prefix):].count("/")
            return value if depth == 0 else f"{max(float(value) - 0.1 * depth, 0.3):.1f}"
    return "0.5"


def collect(site: Path) -> list[tuple[str, str]]:
    urls: dict[str, str] = {}
    for path in sorted(site.rglob("index.html")):
        rel_dir = path.parent.relative_to(site).as_posix()
        rel_dir = "" if rel_dir == "." else f"{rel_dir}/"
        if rel_dir.startswith(SKIP_PREFIXES) or any(part.startswith(".") for part in Path(rel_dir).parts):
            continue
        head_match = HEAD_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        head = head_match.group(1) if head_match else ""
        robots = ROBOTS_RE.search(head)
        if robots and "noindex" in robots.group(1).lower():
            continue
        self_url = page_url(rel_dir)
        canonical = CANONICAL_RE.search(head)
        if canonical:
            target = html.unescape(canonical.group(1))
            if target.split("#")[0].split("?")[0] != self_url:
                continue
        urls[self_url] = priority_for(rel_dir)
    return sorted(urls.items(), key=lambda item: (-float(item[1]), item[0]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--path", required=True, type=Path, help="Exported site directory (ui/site/out)")
    args = parser.parse_args()
    entries = collect(args.path)
    if not entries:
        raise SystemExit(f"No indexable pages under {args.path}")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines += [f"  <url><loc>{escape(url)}</loc><priority>{prio}</priority></url>" for url, prio in entries]
    lines.append("</urlset>")
    (args.path / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"sitemap.xml: {len(entries)} URLs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

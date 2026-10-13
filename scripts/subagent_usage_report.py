#!/usr/bin/env python3
"""Where did each subagent's tokens go? Read the subagent transcripts of a Claude Code session and report, per agent,
turns, input tokens (re-read context: cache read + cache creation + fresh input), output tokens, tool calls and the
largest tool results. Use it after a pilot agent to find what to fix (big dumps, repeated reads, failed fetches)
before scaling a fan-out, and again while the wave runs.

  python3 scripts/subagent_usage_report.py <session-dir>/subagents [--only ID,ID] [--top 4]

Transcripts live under ~/.claude/projects/<project-slug>/<session-id>/subagents/agent-<id>.jsonl.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def summarize(path: Path, top: int) -> dict:
    label, turns, tokens_in, tokens_out = "", 0, 0, 0
    tools: collections.Counter[str] = collections.Counter()
    calls: dict[str, tuple[str, str]] = {}
    results: list[tuple[int, str, str]] = []
    for line in path.open(encoding="utf-8"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        m = e.get("message") or {}
        content = m.get("content")
        if e.get("type") == "user" and isinstance(content, str) and not label:
            label = content.strip().splitlines()[0][-70:]
        if e.get("type") == "assistant":
            u = m.get("usage") or {}
            turns += 1
            tokens_in += u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            tokens_out += u.get("output_tokens", 0)
            for c in content or []:
                if c.get("type") == "tool_use":
                    tools[c["name"]] += 1
                    calls[c["id"]] = (c["name"], json.dumps(c.get("input"), ensure_ascii=False)[:110])
        if e.get("type") == "user" and isinstance(content, list):
            for c in content:
                if c.get("type") == "tool_result":
                    body = c.get("content")
                    size = len(body if isinstance(body, str) else json.dumps(body, ensure_ascii=False))
                    name, args = calls.get(c.get("tool_use_id"), ("?", ""))
                    results.append((size, name, args))
    return {
        "id": path.stem.removeprefix("agent-"),
        "label": label,
        "turns": turns,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tools": dict(tools),
        "result_chars": sum(r[0] for r in results),
        "largest": sorted(results, reverse=True)[:top],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("subagents_dir")
    p.add_argument("--only", help="comma-separated agent ids")
    p.add_argument("--top", type=int, default=4)
    args = p.parse_args(argv)
    only = set(args.only.split(",")) if args.only else None
    rows = [summarize(f, args.top) for f in sorted(Path(args.subagents_dir).glob("agent-*.jsonl")) if not only or f.stem.removeprefix("agent-") in only]
    for r in sorted(rows, key=lambda r: -r["tokens_in"]):
        print(f"== {r['label']} [{r['id']}] turns={r['turns']} in={r['tokens_in'] / 1e6:.2f}M out={r['tokens_out']:,} results={r['result_chars']:,} chars")
        print(f"   tools={r['tools']}")
        for size, name, a in r["largest"]:
            print(f"   {size:>9,} {name} {a}")
    if rows:
        total = sum(r["tokens_in"] for r in rows)
        print(f"\n{len(rows)} agentes, {total / 1e6:.1f}M tokens de entrada, mediana de turnos {sorted(r['turns'] for r in rows)[len(rows) // 2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

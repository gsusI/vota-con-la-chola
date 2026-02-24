#!/usr/bin/env python3
"""Build deterministic Tailwind+MD3 utility CSS for /citizen."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_TOKENS = Path("ui/citizen/tailwind_md3.tokens.json")
DEFAULT_OUT = Path("ui/citizen/tailwind_md3.generated.css")

REQUIRED_COLOR_KEYS = (
    "primary",
    "on_primary",
    "secondary",
    "on_secondary",
    "surface",
    "surface_container",
    "surface_variant",
    "on_surface",
    "on_surface_variant",
    "outline",
    "error",
    "on_error",
    "success",
    "warning",
    "info",
)
REQUIRED_RADII_KEYS = ("sm", "md", "lg", "full")
REQUIRED_SHADOW_KEYS = ("sm", "md")
REQUIRED_TYPO_KEYS = ("sans", "mono")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build citizen Tailwind+MD3 generated CSS")
    ap.add_argument("--tokens", default=str(DEFAULT_TOKENS))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--check", action="store_true", help="Do not write; fail with exit 4 when output would change")
    return ap.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("expected JSON object")
    return obj


def _require_dict(obj: dict[str, Any], key: str) -> dict[str, Any]:
    v = obj.get(key)
    if not isinstance(v, dict):
        raise ValueError(f"missing or invalid object: {key}")
    return v


def _require_str_dict(d: dict[str, Any], required_keys: tuple[str, ...], *, section: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in required_keys:
        value = d.get(key)
        txt = str(value or "").strip()
        if not txt:
            raise ValueError(f"missing or empty {section}.{key}")
        out[key] = txt
    return out


def _sorted_spacing_items(spacing: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key, value in spacing.items():
        k = str(key).strip()
        v = str(value or "").strip()
        if not k or not v:
            continue
        rows.append((k, v))

    def _key(row: tuple[str, str]) -> tuple[int, str]:
        k = row[0]
        if k.isdigit():
            return (0, f"{int(k):08d}")
        return (1, k)

    return sorted(rows, key=_key)


def validate_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    schema_version = str(tokens.get("schema_version") or "").strip()
    if schema_version != "md3-tailwind-v1":
        raise ValueError("schema_version must be md3-tailwind-v1")

    colors = _require_str_dict(_require_dict(tokens, "colors"), REQUIRED_COLOR_KEYS, section="colors")
    radii = _require_str_dict(_require_dict(tokens, "radii"), REQUIRED_RADII_KEYS, section="radii")
    shadows = _require_str_dict(_require_dict(tokens, "shadows"), REQUIRED_SHADOW_KEYS, section="shadows")
    typography = _require_str_dict(_require_dict(tokens, "typography"), REQUIRED_TYPO_KEYS, section="typography")
    spacing_raw = _require_dict(tokens, "spacing")
    spacing = _sorted_spacing_items(spacing_raw)
    if not spacing:
        raise ValueError("spacing must contain at least one token")

    return {
        "colors": colors,
        "radii": radii,
        "shadows": shadows,
        "typography": typography,
        "spacing": spacing,
    }


def build_css(tokens: dict[str, Any], *, source_path: str) -> str:
    cfg = validate_tokens(tokens)
    colors = cfg["colors"]
    radii = cfg["radii"]
    shadows = cfg["shadows"]
    typography = cfg["typography"]
    spacing = cfg["spacing"]

    lines: list[str] = []
    lines.append("/* generated_by=build_citizen_tailwind_md3_css.py */")
    lines.append(f"/* source={source_path} */")
    lines.append("")
    lines.append(":root {")

    for key in REQUIRED_COLOR_KEYS:
        lines.append(f"  --md3-color-{key.replace('_', '-')}: {colors[key]};")
    for key in REQUIRED_RADII_KEYS:
        lines.append(f"  --md3-radius-{key}: {radii[key]};")
    for key in REQUIRED_SHADOW_KEYS:
        lines.append(f"  --md3-shadow-{key}: {shadows[key]};")
    lines.append(f"  --md3-font-sans: {typography['sans']};")
    lines.append(f"  --md3-font-mono: {typography['mono']};")
    for key, value in spacing:
        lines.append(f"  --md3-space-{key}: {value};")

    # Bridge legacy citizen variables so existing UI styles inherit MD3 tokens.
    lines.append("")
    lines.append("  --ink: var(--md3-color-on-surface);")
    lines.append("  --ink-2: var(--md3-color-on-surface-variant);")
    lines.append("  --muted: var(--md3-color-on-surface-variant);")
    lines.append("  --muted-2: var(--md3-color-outline);")
    lines.append("  --panel: var(--md3-color-surface);")
    lines.append("  --panel-2: var(--md3-color-surface-container);")
    lines.append("  --line: color-mix(in srgb, var(--md3-color-outline) 35%, transparent);")
    lines.append("  --shadow: var(--md3-shadow-md);")
    lines.append("  --accent: var(--md3-color-primary);")
    lines.append("  --accent-2: var(--md3-color-secondary);")
    lines.append("  --ok: var(--md3-color-success);")
    lines.append("  --warn: var(--md3-color-warning);")
    lines.append("  --bad: var(--md3-color-error);")
    lines.append("  --chip: color-mix(in srgb, var(--md3-color-surface-container) 88%, white);")
    lines.append("  --sans: var(--md3-font-sans);")
    lines.append("  --mono: var(--md3-font-mono);")
    lines.append("  --radius: var(--md3-radius-lg);")
    lines.append("}")
    lines.append("")

    lines.extend(
        [
            "body {",
            "  font-family: var(--md3-font-sans);",
            "}",
            ".mono {",
            "  font-family: var(--md3-font-mono);",
            "}",
            ".card {",
            "  border-radius: var(--md3-radius-lg);",
            "  box-shadow: var(--md3-shadow-md);",
            "}",
            ".chip, .tag, .stanceChip {",
            "  border-radius: var(--md3-radius-full);",
            "}",
            ".btn {",
            "  border-radius: var(--md3-radius-md);",
            "  border-color: color-mix(in srgb, var(--md3-color-outline) 42%, transparent);",
            "  background: color-mix(in srgb, var(--md3-color-surface-container) 70%, white);",
            "}",
            ".btn:hover, .btn:focus {",
            "  box-shadow: 0 0 0 3px color-mix(in srgb, var(--md3-color-primary) 16%, transparent);",
            "}",
        ]
    )
    lines.append("")

    # Tailwind-style utility subset for reusable UI slices.
    lines.extend(
        [
            ".tw-font-sans { font-family: var(--md3-font-sans); }",
            ".tw-font-mono { font-family: var(--md3-font-mono); }",
            ".tw-bg-surface { background: var(--md3-color-surface); }",
            ".tw-bg-surface-container { background: var(--md3-color-surface-container); }",
            ".tw-bg-primary { background: var(--md3-color-primary); }",
            ".tw-text-primary { color: var(--md3-color-primary); }",
            ".tw-text-on-surface { color: var(--md3-color-on-surface); }",
            ".tw-text-muted { color: var(--md3-color-on-surface-variant); }",
            ".tw-border-outline { border-color: var(--md3-color-outline); }",
            ".tw-rounded-sm { border-radius: var(--md3-radius-sm); }",
            ".tw-rounded-md { border-radius: var(--md3-radius-md); }",
            ".tw-rounded-lg { border-radius: var(--md3-radius-lg); }",
            ".tw-rounded-full { border-radius: var(--md3-radius-full); }",
            ".tw-shadow-sm { box-shadow: var(--md3-shadow-sm); }",
            ".tw-shadow-md { box-shadow: var(--md3-shadow-md); }",
            ".tw-flex { display: flex; }",
            ".tw-grid { display: grid; }",
            ".tw-items-center { align-items: center; }",
            ".tw-justify-between { justify-content: space-between; }",
            ".tw-gap-2 { gap: var(--md3-space-2); }",
            ".tw-gap-3 { gap: var(--md3-space-3); }",
            ".tw-gap-4 { gap: var(--md3-space-4); }",
        ]
    )
    lines.append("")

    for key, _value in spacing:
        lines.append(f".tw-p-{key} {{ padding: var(--md3-space-{key}); }}")
        lines.append(f".tw-px-{key} {{ padding-left: var(--md3-space-{key}); padding-right: var(--md3-space-{key}); }}")
        lines.append(f".tw-py-{key} {{ padding-top: var(--md3-space-{key}); padding-bottom: var(--md3-space-{key}); }}")
    lines.append("")

    # Small component primitives for future slices.
    lines.extend(
        [
            ".md3-card {",
            "  background: var(--md3-color-surface);",
            "  border: 1px solid color-mix(in srgb, var(--md3-color-outline) 28%, transparent);",
            "  border-radius: var(--md3-radius-lg);",
            "  box-shadow: var(--md3-shadow-md);",
            "}",
            ".md3-chip {",
            "  background: var(--md3-color-surface-container);",
            "  color: var(--md3-color-on-surface-variant);",
            "  border: 1px solid color-mix(in srgb, var(--md3-color-outline) 24%, transparent);",
            "  border-radius: var(--md3-radius-full);",
            "}",
            ".md3-button {",
            "  background: color-mix(in srgb, var(--md3-color-surface-container) 76%, white);",
            "  color: var(--md3-color-on-surface);",
            "  border: 1px solid color-mix(in srgb, var(--md3-color-outline) 34%, transparent);",
            "  border-radius: var(--md3-radius-md);",
            "}",
            ".md3-button:hover, .md3-button:focus {",
            "  box-shadow: 0 0 0 3px color-mix(in srgb, var(--md3-color-primary) 16%, transparent);",
            "}",
            ".md3-button-primary {",
            "  background: var(--md3-color-primary);",
            "  color: var(--md3-color-on-primary);",
            "  border: 1px solid color-mix(in srgb, var(--md3-color-primary) 55%, black);",
            "}",
            ".md3-button-primary:hover, .md3-button-primary:focus {",
            "  filter: brightness(0.96);",
            "}",
            ".md3-tab {",
            "  border: 1px solid color-mix(in srgb, var(--md3-color-outline) 34%, transparent);",
            "  border-radius: var(--md3-radius-full);",
            "  background: var(--md3-color-surface-container);",
            "  color: var(--md3-color-on-surface-variant);",
            "  font-weight: 700;",
            "}",
            "select.md3-tab {",
            "  min-height: 40px;",
            "  padding: 8px 12px;",
            "}",
            ".md3-tab.active, .md3-tab[aria-selected=\"true\"], .md3-tab[aria-pressed=\"true\"] {",
            "  background: color-mix(in srgb, var(--md3-color-primary) 18%, white);",
            "  color: var(--md3-color-primary);",
            "  border-color: color-mix(in srgb, var(--md3-color-primary) 42%, transparent);",
            "}",
        ]
    )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tokens_path = Path(str(args.tokens).strip())
    out_path = Path(str(args.out).strip())

    if not tokens_path.exists():
        print(json.dumps({"error": f"tokens not found: {tokens_path}"}, ensure_ascii=False))
        return 2

    try:
        tokens = _load_json(tokens_path)
        css = build_css(tokens, source_path=str(tokens_path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 3

    current = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
    would_change = current != css

    if bool(args.check):
        payload = {
            "status": "ok" if not would_change else "drift",
            "tokens_path": str(tokens_path),
            "out_path": str(out_path),
            "would_change": bool(would_change),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 4 if would_change else 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(css, encoding="utf-8")
    payload = {
        "status": "ok",
        "tokens_path": str(tokens_path),
        "out_path": str(out_path),
        "bytes": len(css.encode("utf-8")),
        "would_change": bool(would_change),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import unicodedata
from typing import Any, Iterable


def now_utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def normalize_ws(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_key_part(value: str) -> str:
    cleaned = unicodedata.normalize("NFKD", value)
    cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
    cleaned = cleaned.lower()
    keep: list[str] = []
    for ch in cleaned:
        if ch.isalnum():
            keep.append(ch)
        elif ch in (" ", "-", "_", "/"):
            keep.append(" ")
    return normalize_ws("".join(keep))


def canonical_key(full_name: str, birth_date: str | None, territory_code: str | None) -> str:
    parts = [normalize_key_part(full_name)]
    if birth_date:
        parts.append(birth_date)
    if territory_code:
        parts.append(normalize_key_part(territory_code))
    return "|".join(parts)


def key_variants(key: str) -> set[str]:
    raw = key.lower().strip()
    normalized = normalize_key_part(key)
    values = {raw, normalized}
    variants: set[str] = set()
    for base in values:
        if not base:
            continue
        variants.add(base)
        variants.add(base.replace(" ", "_"))
        variants.add(base.replace(" ", "-"))
        variants.add(base.replace(" ", ""))
        variants.add(base.replace("_", ""))
        variants.add(base.replace("-", ""))
    return variants


def pick_value(record: dict[str, Any], candidates: Iterable[str]) -> str | None:
    normalized: dict[str, Any] = {}
    for k, v in record.items():
        k_str = str(k).strip()
        for variant in key_variants(k_str):
            normalized.setdefault(variant, v)

    for cand in candidates:
        for variant in key_variants(cand):
            if variant in normalized:
                value = normalized[variant]
                if value is None:
                    continue
                text = normalize_ws(str(value))
                if text:
                    return text
    return None


def parse_date_flexible(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if " " in text:
        text = text.split(" ", 1)[0].strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def clean_text(value: str | None) -> str:
    if value is None:
        return ""
    decoded = html.unescape(value)
    stripped = re.sub(r"<[^>]+>", " ", decoded)
    return normalize_ws(stripped)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=True, sort_keys=True)


def roman_to_int(value: str) -> int | None:
    text = normalize_ws(value).upper()
    if not text:
        return None
    valid = set("IVXLCDM")
    if any(ch not in valid for ch in text):
        return None
    mapping = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(text):
        cur = mapping[ch]
        if cur < prev:
            total -= cur
        else:
            total += cur
            prev = cur
    return total if total > 0 else None


def split_spanish_name(raw_name: str) -> tuple[str | None, str | None, str]:
    cleaned = normalize_ws(raw_name)
    if not cleaned:
        return None, None, ""
    if "," in cleaned:
        family, given = [normalize_ws(part) for part in cleaned.split(",", 1)]
        full = normalize_ws(f"{given} {family}")
        return given or None, family or None, full
    return None, None, cleaned


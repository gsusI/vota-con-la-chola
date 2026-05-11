from __future__ import annotations

import csv
import json
from typing import Any
import xml.etree.ElementTree as ET


def flatten_json_records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("results", "items", "data", "diputados", "dataset", "rows"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        nested_lists = [v for v in data.values() if isinstance(v, list)]
        for candidate in nested_lists:
            dict_rows = [item for item in candidate if isinstance(item, dict)]
            if dict_rows:
                return dict_rows
        return [data]
    return []


def parse_json_source(payload: bytes) -> list[dict[str, Any]]:
    parsed = json.loads(payload.decode("utf-8", errors="replace"))
    return flatten_json_records(parsed)


def decode_csv_payload(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            pass

    for encoding in ("cp1252", "latin-1"):
        decoded = payload.decode(encoding)
        if "\x00" in decoded:
            continue
        return decoded

    return payload.decode("utf-8", errors="replace")


def parse_csv_source(payload: bytes) -> list[dict[str, Any]]:
    text = decode_csv_payload(payload)
    lines = text.splitlines()
    if not lines:
        return []

    delimiter_override: str | None = None
    first_line = lines[0].strip().lower()
    if first_line.startswith("sep=") and len(first_line) >= 5:
        delimiter_override = first_line.split("=", 1)[1][:1]
        lines = lines[1:]

    sample = "\n".join(lines[:20])
    try:
        if delimiter_override:
            reader = csv.DictReader(lines, delimiter=delimiter_override)
        else:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t,")
            reader = csv.DictReader(lines, dialect=dialect)
    except csv.Error:
        reader = csv.DictReader(lines, delimiter=";")
    rows: list[dict[str, Any]] = []
    for row in reader:
        normalized_row = {str(k).strip(): (v if v is not None else "") for k, v in row.items()}
        if any(str(v).strip() for v in normalized_row.values()):
            rows.append(normalized_row)
    return rows


def xlsx_col_to_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in str(cell_ref or "") if ch.isalpha()).upper()
    if not letters:
        return -1
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def xml_root(payload: bytes) -> ET.Element:
    return ET.fromstring(payload.decode("utf-8", errors="replace"))

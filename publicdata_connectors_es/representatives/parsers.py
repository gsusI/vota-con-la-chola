from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from typing import Any

from publicdata_core.parsers import (
    flatten_json_records,
    local_name,
    parse_csv_source,
    parse_json_source,
    xlsx_col_to_index,
)

from publicdata_core.util import normalize_key_part, normalize_ws, parse_date_flexible, pick_value, stable_json

from .config import SPAIN_COUNTRY_NAMES


def parse_xlsx_source(payload: bytes) -> list[dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall(".//{*}si"):
                text = "".join((node.text or "") for node in si.findall(".//{*}t"))
                shared.append(text)

        sheets = sorted(
            name
            for name in zf.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        if not sheets:
            return []

        root = ET.fromstring(zf.read(sheets[0]))
        raw_rows: list[list[str]] = []
        for row in root.findall(".//{*}sheetData/{*}row"):
            row_values: dict[int, str] = {}
            max_idx = -1
            for cell in row.findall("{*}c"):
                idx = xlsx_col_to_index(cell.attrib.get("r", ""))
                if idx < 0:
                    idx = max_idx + 1

                cell_type = cell.attrib.get("t")
                value = ""
                if cell_type == "inlineStr":
                    node = cell.find("{*}is/{*}t")
                    value = (node.text or "") if node is not None else ""
                else:
                    node = cell.find("{*}v")
                    raw_value = (node.text or "").strip() if node is not None else ""
                    if cell_type == "s" and raw_value:
                        try:
                            value = shared[int(raw_value)]
                        except (ValueError, IndexError):
                            value = raw_value
                    else:
                        value = raw_value

                row_values[idx] = value
                if idx > max_idx:
                    max_idx = idx

            if max_idx < 0:
                continue
            raw_rows.append([row_values.get(i, "") for i in range(max_idx + 1)])

    if not raw_rows:
        return []

    header_idx = -1
    for i, values in enumerate(raw_rows[:20]):
        normalized = [normalize_key_part(v) for v in values if normalize_key_part(v)]
        if (
            "codigo ine" in normalized
            and "municipio" in normalized
            and "nombre" in normalized
            and "cargo" in normalized
        ):
            header_idx = i
            break
    if header_idx < 0:
        return []

    headers = [normalize_ws(v) for v in raw_rows[header_idx]]
    rows: list[dict[str, Any]] = []
    for values in raw_rows[header_idx + 1 :]:
        record: dict[str, Any] = {}
        non_empty = False
        for idx, key in enumerate(headers):
            key = key.strip()
            if not key:
                continue
            value = values[idx] if idx < len(values) else ""
            value_str = normalize_ws(str(value))
            record[key] = value_str
            if value_str:
                non_empty = True
        if non_empty and record:
            rows.append(record)
    return rows
def parse_europarl_xml(payload: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(payload.decode("utf-8", errors="replace"))
    rows: list[dict[str, Any]] = []
    for mep in root.findall(".//mep"):
        row: dict[str, Any] = {}
        for child in list(mep):
            key = local_name(child.tag)
            value = (child.text or "").strip()
            if value:
                row[key] = value
        if not row:
            continue
        country = normalize_key_part(row.get("country", ""))
        if country in SPAIN_COUNTRY_NAMES:
            rows.append(row)

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        fp = stable_json(row)
        if fp in seen:
            continue
        seen.add(fp)
        deduped.append(row)
    return deduped


def parse_asamblea_madrid_ocupaciones_csv(payload: bytes) -> list[dict[str, Any]]:
    rows = parse_csv_source(payload)
    if not rows:
        return rows

    max_leg = 0
    for row in rows:
        raw_leg = pick_value(row, ("LEGISLATURA", "legislatura")) or ""
        try:
            leg = int(raw_leg.strip())
        except ValueError:
            continue
        if leg > max_leg:
            max_leg = leg

    for row in rows:
        raw_leg = pick_value(row, ("LEGISLATURA", "legislatura")) or ""
        try:
            leg = int(raw_leg.strip())
        except ValueError:
            leg = 0

        raw_end = pick_value(row, ("FECHA_FIN", "fecha_fin", "fecha fin")) or ""
        raw_end_norm = normalize_ws(raw_end)
        end_date = parse_date_flexible(raw_end_norm)
        row["legislatura_int"] = leg
        row["is_active"] = bool(leg == max_leg and (raw_end_norm in {"", "-"} or end_date is None))
        row["max_legislatura_int"] = max_leg
    return rows

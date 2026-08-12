"""Bounded-page contract for the official BDNS concessions API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode

from .bdns_subsidies import BDNS_API_BASE, parse_bdns_records

BDNS_CONCESSIONS_ENDPOINT = f"{BDNS_API_BASE}/concesiones/busqueda"
MAX_PAGE_SIZE = 1_000


@dataclass(frozen=True)
class BdnsPage:
    page_number: int
    page_size: int
    number_of_elements: int
    total_elements: int
    total_pages: int
    first: bool
    last: bool
    records: list[dict[str, object]]


def build_bdns_concessions_url(
    *,
    page: int,
    page_size: int,
    date_from: str = "",
    date_to: str = "",
) -> str:
    if int(page) < 0:
        raise ValueError("page must be >= 0")
    if int(page_size) < 1 or int(page_size) > MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    params = {
        "vpd": "GE",
        "page": int(page),
        "pageSize": int(page_size),
        "order": "fechaConcesion",
        "direccion": "desc",
    }
    if str(date_from or "").strip():
        params["fechaDesde"] = str(date_from).strip()
    if str(date_to or "").strip():
        params["fechaHasta"] = str(date_to).strip()
    query = urlencode(params)
    return f"{BDNS_CONCESSIONS_ENDPOINT}?{query}"


def parse_bdns_page(
    payload: bytes,
    *,
    feed_url: str,
    content_type: str | None,
    expected_page: int | None = None,
    expected_page_size: int | None = None,
) -> BdnsPage:
    try:
        data = json.loads(payload.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid BDNS page JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("content"), list):
        raise TypeError("BDNS page lacks a content array")

    page_number = int(data.get("number") or 0)
    page_size = int(data.get("size") or len(data["content"]))
    number_of_elements = int(data.get("numberOfElements") or len(data["content"]))
    total_elements = int(data.get("totalElements") or 0)
    total_pages = int(data.get("totalPages") or 0)
    if expected_page is not None and page_number != int(expected_page):
        raise RuntimeError(
            f"BDNS page mismatch: expected={int(expected_page)} observed={page_number}"
        )
    if expected_page_size is not None and page_size != int(expected_page_size):
        raise RuntimeError(
            "BDNS page-size mismatch: "
            f"expected={int(expected_page_size)} observed={page_size}"
        )
    if number_of_elements != len(data["content"]):
        raise RuntimeError(
            "BDNS page count mismatch: "
            f"numberOfElements={number_of_elements} content={len(data['content'])}"
        )
    if total_elements < number_of_elements or total_pages < (
        1 if total_elements else 0
    ):
        raise RuntimeError("BDNS page metadata is internally inconsistent")

    records = (
        parse_bdns_records(
            payload,
            feed_url=feed_url,
            content_type=content_type,
        )
        if number_of_elements > 0
        else []
    )
    if len(records) != number_of_elements:
        raise RuntimeError(
            "BDNS normalized-record mismatch: "
            f"normalized={len(records)} content={number_of_elements}"
        )
    return BdnsPage(
        page_number=page_number,
        page_size=page_size,
        number_of_elements=number_of_elements,
        total_elements=total_elements,
        total_pages=total_pages,
        first=bool(data.get("first")),
        last=bool(data.get("last")),
        records=records,
    )

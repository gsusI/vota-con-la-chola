from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from etl.politicos_es.util import normalize_ws, now_utc_iso, sha256_bytes, stable_json

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes, payload_looks_like_html
from ..raw import raw_output_path
from ..types import Extracted
from .base import BaseConnector


SENADO_BASE = "https://www.senado.es"
SENADO_VOTACIONES_CATALOG_URL = (
    "https://www.senado.es/web/relacionesciudadanos/datosabiertos/catalogodatos/votaciones/index.html?legis=15"
)
LEGS_SELECT_RE = re.compile(r'<select[^>]*id="legis"[^>]*>(?P<body>.*?)</select>', re.I | re.S)
OPTION_VALUE_RE = re.compile(r'<option[^>]*value="(?P<v>\d+)"', re.I)


def _extract_legislature(url: str) -> str | None:
    try:
        qs = parse_qs(urlparse(url).query)
        vals = qs.get("legis") or []
        if vals:
            return normalize_ws(vals[0]) or None
    except Exception:  # noqa: BLE001
        return None
    return None


def _extract_legislatures_from_catalog_html(html: str) -> list[int]:
    m = LEGS_SELECT_RE.search(html)
    if not m:
        return []
    vals = [int(mm.group("v")) for mm in OPTION_VALUE_RE.finditer(m.group("body"))]
    seen: set[int] = set()
    out: list[int] = []
    for v in vals:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _parse_leg_filter(value: Any) -> list[int]:
    txt = normalize_ws(str(value or ""))
    if not txt:
        return []
    out: list[int] = []
    for token in re.split(r"[,\s;]+", txt):
        t = normalize_ws(token)
        if not t:
            continue
        if t.isdigit():
            out.append(int(t))
    return out


def _set_legis_query(url: str, leg: int) -> str:
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    q["legis"] = [str(leg)]
    new_q = urlencode(q, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_q, parsed.fragment))


def _parse_vote_ids_from_url(url: str | None) -> tuple[int | None, int | None]:
    if not url:
        return None, None
    try:
        qs = parse_qs(urlparse(url).query)
        id1 = qs.get("id1", [None])[0]
        id2 = qs.get("id2", [None])[0]
        return int(id1) if id1 and str(id1).isdigit() else None, int(id2) if id2 and str(id2).isdigit() else None
    except Exception:  # noqa: BLE001
        return None, None


def _records_from_tipo9_xml(payload: bytes, source_url: str) -> list[dict[str, Any]]:
    if not payload:
        return []
    if payload_looks_like_html(payload):
        raise RuntimeError(f"XML inesperado para Senado iniciativas: HTML recibido {source_url!r}")
    root = ET.fromstring(payload)
    if root.tag != "listaIniciativasLegislativas":
        raise RuntimeError(f"XML inesperado para Senado iniciativas: root={root.tag!r}")

    legislature_from_url = _extract_legislature(source_url)
    out: list[dict[str, Any]] = []

    for node in root.findall("./iniciativa"):
        tipo_ex = normalize_ws(str(node.findtext("tipoExpediente") or "")) or None
        num_ex = normalize_ws(str(node.findtext("numeroExpediente") or "")) or None
        if not tipo_ex or not num_ex:
            continue
        expediente = f"{tipo_ex}/{num_ex}"

        iniciativa_url_raw = normalize_ws(str(node.findtext("urlPagina") or "")) or None
        iniciativa_url = urljoin(SENADO_BASE, iniciativa_url_raw) if iniciativa_url_raw else None

        detail_file_url_raw = normalize_ws(str(node.findtext("./fichero/fichUrl") or "")) or None
        detail_file_url = urljoin(SENADO_BASE, detail_file_url_raw) if detail_file_url_raw else None

        enmiendas_title = normalize_ws(str(node.findtext("./listaEnmiendas/tituloListaEnm") or "")) or None
        enmiendas_url_raw = normalize_ws(str(node.findtext("./listaEnmiendas/urlListaEnm") or "")) or None
        enmiendas_url = urljoin(SENADO_BASE, enmiendas_url_raw) if enmiendas_url_raw else None

        enmiendas_file_url_raw = (
            normalize_ws(str(node.findtext("./listaEnmiendas/fichGenEnmiendas/fichUrlEnmiendas") or "")) or None
        )
        enmiendas_file_url = urljoin(SENADO_BASE, enmiendas_file_url_raw) if enmiendas_file_url_raw else None

        votaciones_file_url_raw = normalize_ws(
            str(node.findtext("./votaciones/fichGenVotaciones/fichUrlVotaciones") or "")
        ) or None
        votaciones_file_url = urljoin(SENADO_BASE, votaciones_file_url_raw) if votaciones_file_url_raw else None

        legislature = normalize_ws(str(node.findtext("legislatura") or "")) or legislature_from_url
        if not legislature:
            legislature = (
                _extract_legislature(iniciativa_url_raw or "")
                or _extract_legislature(detail_file_url_raw or "")
                or _extract_legislature(votaciones_file_url_raw or "")
            )
        title = normalize_ws(str(node.findtext("titulo") or "")) or None

        vote_refs: list[dict[str, Any]] = []
        for vote in node.findall("./votaciones/votacion"):
            vote_title = normalize_ws(str(vote.findtext("tituloVotacion") or "")) or None
            vote_url_raw = normalize_ws(str(vote.findtext("urlVotacion") or "")) or None
            vote_url = urljoin(SENADO_BASE, vote_url_raw) if vote_url_raw else None

            vote_file_url_raw = normalize_ws(str(vote.findtext("./fichVotacion/fichUrlVotacion") or "")) or None
            vote_file_url = urljoin(SENADO_BASE, vote_file_url_raw) if vote_file_url_raw else None

            session_id, vote_id = _parse_vote_ids_from_url(vote_url)
            vote_refs.append(
                {
                    "vote_title": vote_title,
                    "vote_url": vote_url,
                    "vote_file_url": vote_file_url,
                    "session_id": session_id,
                    "vote_id": vote_id,
                }
            )

        payload_item = {
            "legislature": legislature,
            "tipo_expediente": tipo_ex,
            "numero_expediente": num_ex,
            "expediente": expediente,
            "iniciativa_title": title,
            "iniciativa_url": iniciativa_url,
            "detail_file_url": detail_file_url,
            "enmiendas_title": enmiendas_title,
            "enmiendas_url": enmiendas_url,
            "enmiendas_file_url": enmiendas_file_url,
            "votaciones_file_url": votaciones_file_url,
            "vote_refs": vote_refs,
            "source_tipo9_url": source_url,
        }
        out.append(
            {
                "detail_url": source_url,
                "legislature": legislature,
                "payload": payload_item,
            }
        )

    return out


class SenadoIniciativasConnector(BaseConnector):
    source_id = "senado_iniciativas"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or SOURCE_CONFIG[self.source_id]["default_url"]

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
        options: dict[str, Any] | None = None,
    ) -> Extracted:
        options = dict(options or {})
        max_records = options.get("max_records")
        leg_filter = _parse_leg_filter(options.get("senado_legs"))
        records: list[dict[str, Any]] = []
        content_type = None

        if from_file:
            paths: list[Path]
            if from_file.is_dir():
                paths = sorted([p for p in from_file.glob("*.xml") if p.is_file()])
                note = "from-dir"
            else:
                paths = [from_file]
                note = "from-file"

            for p in paths:
                try:
                    rows = _records_from_tipo9_xml(p.read_bytes(), f"file://{p.resolve()}")
                except Exception as exc:  # noqa: BLE001
                    if strict_network:
                        raise
                    note = f"from-file-partial:{type(exc).__name__}: {exc}"
                    continue
                if isinstance(max_records, int) and max_records > 0:
                    remaining = max_records - len(records)
                    if remaining <= 0:
                        break
                    rows = rows[:remaining]
                records.extend(rows)
                if isinstance(max_records, int) and max_records > 0 and len(records) >= max_records:
                    break

            meta = {
                "source": "senado_iniciativas_from_file",
                "paths": [str(p) for p in paths],
                "records": len(records),
            }
            payload_bytes = stable_json(meta).encode("utf-8")
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(payload_bytes)
            return Extracted(
                source_id=self.source_id,
                source_url=f"file://{from_file.resolve()}",
                resolved_url=f"file://{from_file.resolve()}",
                fetched_at=now_utc_iso(),
                raw_path=raw_path,
                content_sha256=sha256_bytes(payload_bytes),
                content_type=None,
                bytes=len(payload_bytes),
                note=note,
                payload=payload_bytes,
                records=records,
            )

        resolved_url = self.resolve_url(url_override, timeout)
        target_legs: list[int]
        if leg_filter:
            target_legs = sorted({int(v) for v in leg_filter if int(v) >= 0}, reverse=True)
        else:
            catalog_legs: list[int] = []
            try:
                catalog_html = http_get_bytes(
                    SENADO_VOTACIONES_CATALOG_URL,
                    timeout,
                    headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                )[0].decode("utf-8", errors="replace")
                catalog_legs = _extract_legislatures_from_catalog_html(catalog_html)
            except Exception:  # noqa: BLE001
                catalog_legs = []
            default_leg = _extract_legislature(resolved_url)
            target_legs = sorted(
                {int(v) for v in (catalog_legs or ([int(default_leg)] if default_leg and default_leg.isdigit() else [15]))},
                reverse=True,
            )

        failures: list[str] = []
        for leg in target_legs:
            list_url = _set_legis_query(resolved_url, leg)
            try:
                xml_bytes, ct = http_get_bytes(
                    list_url,
                    timeout,
                    headers={"Accept": "application/xml,text/xml,*/*"},
                )
                if ct and "xml" not in ct.lower():
                    raise RuntimeError(f"content_type inesperado: {ct}")
                content_type = ct or content_type
                rows = _records_from_tipo9_xml(xml_bytes, list_url)
                if isinstance(max_records, int) and max_records > 0:
                    remaining = max_records - len(records)
                    if remaining <= 0:
                        break
                    rows = rows[:remaining]
                records.extend(rows)
                if isinstance(max_records, int) and max_records > 0 and len(records) >= max_records:
                    break
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{list_url} -> {type(exc).__name__}: {exc}")
                if strict_network:
                    raise

        meta = {
            "source": "senado_iniciativas_catalog",
            "list_url": resolved_url,
            "target_legs": target_legs,
            "records": len(records),
            "failures": failures,
        }
        payload_bytes = stable_json(meta).encode("utf-8")
        raw_path = raw_output_path(raw_dir, self.source_id, "json")
        raw_path.write_bytes(payload_bytes)

        note = "network"
        if failures:
            note = "network-partial"

        return Extracted(
            source_id=self.source_id,
            source_url=resolved_url,
            resolved_url=resolved_url,
            fetched_at=now_utc_iso(),
            raw_path=raw_path,
            content_sha256=sha256_bytes(payload_bytes),
            content_type=content_type,
            bytes=len(payload_bytes),
            note=note,
            payload=payload_bytes,
            records=records,
        )

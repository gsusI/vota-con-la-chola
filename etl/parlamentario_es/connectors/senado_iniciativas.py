from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from etl.politicos_es.util import normalize_ws, now_utc_iso, sha256_bytes, stable_json

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes
from ..raw import raw_output_path
from ..types import Extracted
from .base import BaseConnector


SENADO_BASE = "https://videoservlet.senado.es"


def _extract_legislature(url: str) -> str | None:
    try:
        qs = parse_qs(urlparse(url).query)
        vals = qs.get("legis") or []
        if vals:
            return normalize_ws(vals[0]) or None
    except Exception:  # noqa: BLE001
        return None
    return None


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
        _ = strict_network
        options = dict(options or {})
        max_records = options.get("max_records")
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
                rows = _records_from_tipo9_xml(p.read_bytes(), f"file://{p.resolve()}")
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
        xml_bytes, content_type = http_get_bytes(
            resolved_url,
            timeout,
            headers={"Accept": "application/xml,text/xml,*/*"},
        )
        if content_type and "xml" not in content_type.lower():
            raise RuntimeError(f"content_type inesperado para Senado iniciativas: {content_type}")
        records = _records_from_tipo9_xml(xml_bytes, resolved_url)
        if isinstance(max_records, int) and max_records > 0:
            records = records[:max_records]

        meta = {
            "source": "senado_iniciativas_catalog",
            "list_url": resolved_url,
            "records": len(records),
        }
        payload_bytes = stable_json(meta).encode("utf-8")
        raw_path = raw_output_path(raw_dir, self.source_id, "json")
        raw_path.write_bytes(payload_bytes)

        return Extracted(
            source_id=self.source_id,
            source_url=resolved_url,
            resolved_url=resolved_url,
            fetched_at=now_utc_iso(),
            raw_path=raw_path,
            content_sha256=sha256_bytes(payload_bytes),
            content_type=content_type,
            bytes=len(payload_bytes),
            note="network",
            payload=payload_bytes,
            records=records,
        )

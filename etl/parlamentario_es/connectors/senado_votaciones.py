from __future__ import annotations

import html as htmlmod
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from etl.politicos_es.util import normalize_key_part, normalize_ws, now_utc_iso, parse_date_flexible, sha256_bytes, stable_json

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes, payload_looks_like_html
from ..raw import raw_output_path
from ..types import Extracted
from .base import BaseConnector


SENADO_BASE = "https://www.senado.es"
SENADO_TIPO9_URL = f"{SENADO_BASE}/web/ficopendataservlet?tipoFich=9&legis={{leg}}"
SENADO_MONTHS = {
    "ENE": "01",
    "FEB": "02",
    "MAR": "03",
    "ABR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AGO": "08",
    "SEP": "09",
    "OCT": "10",
    "NOV": "11",
    "DIC": "12",
}
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


def _to_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    txt = normalize_ws(str(value))
    if not txt or not txt.isdigit():
        return None
    return int(txt)


def _parse_senado_vote_date(value: str | None) -> str | None:
    txt = normalize_ws(value)
    if not txt:
        return None
    direct = parse_date_flexible(txt)
    if direct:
        return direct

    m = re.match(r"^(\d{1,2})-([A-Z]{3})-(\d{4})$", txt.upper())
    if m:
        dd = int(m.group(1))
        mm = SENADO_MONTHS.get(m.group(2))
        yy = int(m.group(3))
        if mm:
            return f"{yy:04d}-{mm}-{dd:02d}"
    return None


def _session_vote_file_url_candidates(
    host_base: str,
    legislature: str | None,
    session_id: int | None,
    vote_id: int | None,
    vote_file_url: str | None,
) -> list[str]:
    if not legislature:
        return []

    host = host_base.rstrip("/")
    base = f"{host}/legis{legislature}/votaciones"
    out: list[str] = []

    vote_file = normalize_ws(str(vote_file_url or ""))
    if vote_file and not vote_file.lower().startswith("http"):
        # Upstream XML sometimes provides relative URLs.
        if vote_file.startswith("/") or "/legis" in vote_file:
            vote_file = urljoin(host + "/", vote_file)
        else:
            vote_file = urljoin(base + "/", vote_file)
    if vote_file:
        out.append(vote_file)

    if session_id is not None and vote_id is not None:
        out.append(f"{base}/ses_{session_id}_{vote_id}.xml")
        if session_id != vote_id:
            out.append(f"{base}/ses_{vote_id}_{session_id}.xml")

    if session_id is not None:
        out.append(f"{base}/ses_{session_id}.xml")

    if vote_id is not None:
        out.append(f"{base}/ses_{vote_id}.xml")

    deduped: list[str] = []
    for u in out:
        if u and u not in deduped:
            deduped.append(u)
    return deduped


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


def _tipo12_urls_from_tipo9_xml(payload: bytes) -> list[str]:
    if not payload:
        return []
    if payload_looks_like_html(payload):
        raise RuntimeError("XML inesperado para tipoFich=9: HTML recibido")
    root = ET.fromstring(payload)
    if root.tag != "listaIniciativasLegislativas":
        raise RuntimeError(f"XML inesperado para tipoFich=9: root={root.tag!r}")
    out: list[str] = []
    for node in root.findall("./iniciativa"):
        url_raw_txt = node.findtext("./votaciones/fichGenVotaciones/fichUrlVotaciones")
        url_raw = normalize_ws(str(url_raw_txt or "")) or None
        if not url_raw:
            continue
        out.append(urljoin(SENADO_BASE, url_raw))
    # deterministic dedupe
    seen: set[str] = set()
    deduped: list[str] = []
    for u in out:
        if u in seen:
            continue
        seen.add(u)
        deduped.append(u)
    return deduped


def _parse_sesion_vote_xml(payload: bytes) -> dict[str, Any]:
    if not payload:
        return {"session_date": None, "votes": []}
    if payload_looks_like_html(payload):
        raise RuntimeError("XML de sesion inesperado: HTML recibido")
    root = ET.fromstring(payload)
    if root.tag != "main":
        raise RuntimeError(f"XML de sesion inesperado: root={root.tag!r}")

    sesion = root.find("./sesion")
    session_date_iso = _parse_senado_vote_date(sesion.findtext("fecha_sesion") if sesion is not None else None)

    votes: list[dict[str, Any]] = []
    for node in root.findall(".//votacion"):
        tit_vot = normalize_ws(str(node.findtext("tit_vot") or "")) or None
        tit_sec = normalize_ws(str(node.findtext("tit_sec") or "")) or None
        num_vot = _to_int(node.findtext("num_vot"))
        cod_vot = _to_int(node.findtext("CodVotacion"))
        num_exp = normalize_ws(str(node.findtext("num_exp") or "")) or None
        vote_date = _parse_senado_vote_date(node.findtext("fecha_v")) or session_date_iso

        members: list[dict[str, Any]] = []
        # Senado XML uses mixed-case tags (e.g. <Resultado><VotoSenador>...</VotoSenador></Resultado>).
        # Using ".//VotoSenador" keeps us resilient across legislatures.
        for row in node.findall(".//VotoSenador"):
            nombre = normalize_ws(str(row.findtext("nombre") or "")) or None
            apellidos = normalize_ws(str(row.findtext("apellidos") or "")) or None
            full_name = None
            if nombre and apellidos:
                full_name = normalize_ws(f"{nombre} {apellidos}")
            else:
                full_name = nombre or apellidos
            members.append(
                {
                    "seat": normalize_ws(str(row.findtext("escano") or "")) or None,
                    "group": normalize_ws(str(row.findtext("grupo") or "")) or None,
                    "member_name": full_name,
                    "vote_choice": normalize_ws(str(row.findtext("voto") or "")) or None,
                }
            )
        for row in node.findall("./ausentes/ausencia"):
            nombre = normalize_ws(str(row.findtext("nombre") or "")) or None
            apellidos = normalize_ws(str(row.findtext("apellidos") or "")) or None
            full_name = None
            if nombre and apellidos:
                full_name = normalize_ws(f"{nombre} {apellidos}")
            else:
                full_name = nombre or apellidos
            members.append(
                {
                    "seat": normalize_ws(str(row.findtext("escano") or "")) or None,
                    "group": normalize_ws(str(row.findtext("grupo") or "")) or None,
                    "member_name": full_name,
                    "vote_choice": "AUSENTE",
                }
            )

        votes.append(
            {
                "num_vot": num_vot,
                "cod_votacion": cod_vot,
                "num_exp": num_exp,
                "title": tit_vot,
                "section_title": tit_sec,
                "vote_date": vote_date,
                "totals_present": _to_int(node.findtext("tot_presentes")),
                "totals_yes": _to_int(node.findtext("tot_afirmativos")),
                "totals_no": _to_int(node.findtext("tot_negativos")),
                "totals_abstain": _to_int(node.findtext("tot_abstenciones")),
                "totals_no_vote": _to_int(node.findtext("tot_novotan")),
                "totals_absent": _to_int(node.findtext("tot_ausentes")),
                "member_votes": members,
                "_title_key": normalize_key_part(tit_vot or ""),
                "_section_key": normalize_key_part(tit_sec or ""),
            }
        )

    return {"session_date": session_date_iso, "votes": votes}


def _pick_sesion_vote(record_payload: dict[str, Any], session_votes: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None, float | None]:
    if not session_votes:
        return None, None, None

    tipo_ex = normalize_ws(str(record_payload.get("tipo_expediente") or "")) or None
    num_ex = normalize_ws(str(record_payload.get("numero_expediente") or "")) or None
    target_exp = f"{tipo_ex}/{num_ex}" if (tipo_ex and num_ex) else None
    target_title = normalize_key_part(str(record_payload.get("vote_title") or ""))
    vote_id = _to_int(record_payload.get("vote_id"))

    pool = list(session_votes)
    used_exp = False
    if target_exp:
        by_exp = [c for c in pool if normalize_ws(c.get("num_exp")) == target_exp]
        if by_exp:
            pool = by_exp
            used_exp = True

    if target_title:
        exact = [c for c in pool if target_title and target_title in {c.get("_title_key") or "", c.get("_section_key") or ""}]
        if len(exact) == 1:
            return exact[0], "exp+title_exact" if used_exp else "title_exact", 1.0 if used_exp else 0.9
        if len(exact) > 1:
            pool = exact

        contains = [
            c
            for c in pool
            if target_title in (c.get("_title_key") or "")
            or target_title in (c.get("_section_key") or "")
            or (c.get("_title_key") or "") in target_title
        ]
        if len(contains) == 1:
            return contains[0], "exp+title_contains" if used_exp else "title_contains", 0.85 if used_exp else 0.72
        if len(contains) > 1:
            pool = contains

    if vote_id is not None:
        by_cod = [c for c in pool if c.get("cod_votacion") == vote_id]
        if len(by_cod) == 1:
            return by_cod[0], "exp+cod_votacion" if used_exp else "cod_votacion", 0.95 if used_exp else 0.75
        if len(by_cod) > 1:
            pool = by_cod

        by_num = [c for c in pool if c.get("num_vot") == vote_id]
        if len(by_num) == 1:
            return by_num[0], "exp+num_vot" if used_exp else "num_vot", 0.8 if used_exp else 0.65

    if len(pool) == 1:
        return pool[0], "exp_unique" if used_exp else "session_unique", 0.7 if used_exp else 0.55
    return None, None, None


def _records_from_tipo12_xml(payload: bytes, source_url: str) -> list[dict[str, Any]]:
    if not payload:
        return []
    if payload_looks_like_html(payload):
        raise RuntimeError(f"XML inesperado para Senado votaciones: HTML recibido {source_url!r}")
    root = ET.fromstring(payload)
    if root.tag != "iniciativaVotaciones":
        raise RuntimeError(f"XML inesperado para Senado votaciones: root={root.tag!r}")

    leg = _extract_legislature(source_url)
    tipo_ex = normalize_ws(root.findtext("tipoExpediente"))
    num_ex = normalize_ws(root.findtext("numeroExpediente"))
    iniciativa_title = normalize_ws(root.findtext("titulo"))
    iniciativa_url_raw = normalize_ws(root.findtext("urlPagina"))
    iniciativa_url = urljoin(SENADO_BASE, iniciativa_url_raw) if iniciativa_url_raw else None

    records: list[dict[str, Any]] = []
    for v in root.findall("./votaciones/votacion"):
        vote_title = normalize_ws(v.findtext("tituloVotacion"))
        vote_url_raw = normalize_ws(v.findtext("urlVotacion"))
        vote_url = urljoin(SENADO_BASE, vote_url_raw) if vote_url_raw else None
        if not leg:
            leg = _extract_legislature(iniciativa_url_raw or "") or _extract_legislature(vote_url_raw or "")
        fich = v.find("fichGenVotacion")
        vote_file_url = None
        vote_file_format = None
        if fich is not None:
            vote_file_url = normalize_ws(fich.findtext("fichUrlVotacion")) or None
            vote_file_format = normalize_ws(fich.findtext("fichFormatoVotacion")) or None

        session_id, vote_id = _parse_vote_ids_from_url(vote_url)
        record_payload = {
            "legislature": leg,
            "tipo_expediente": tipo_ex,
            "numero_expediente": num_ex,
            "iniciativa_title": iniciativa_title,
            "iniciativa_url": iniciativa_url,
            "vote_title": vote_title,
            "vote_url": vote_url,
            "vote_file_url": vote_file_url,
            "vote_file_format": vote_file_format,
            "session_id": session_id,
            "vote_id": vote_id,
            "source_tipo12_url": source_url,
        }
        records.append(
            {
                "detail_url": source_url,
                "legislature": leg,
                "payload": record_payload,
            }
        )
    return records


def _find_local_session_xml(
    detail_dir: Path,
    session_id: int,
    vote_id: int | None = None,
    *,
    session_url: str | None = None,
) -> Path | None:
    candidate_names: list[str] = []
    if vote_id is not None:
        candidate_names.append(f"ses_{session_id}_{vote_id}.xml")
        candidate_names.append(f"ses_{vote_id}_{session_id}.xml")
    candidate_names.append(f"ses_{session_id}.xml")

    preferred_dirs: list[Path] = []
    if session_url:
        try:
            parsed = urlparse(session_url)
            basename = Path(parsed.path).name
        except Exception:  # noqa: BLE001
            basename = ""
        if basename and basename not in candidate_names:
            candidate_names.insert(0, basename)

        m = re.search(r"/legis(\d+)/votaciones/", session_url, flags=re.I)
        if m:
            preferred_dirs.append(detail_dir / f"legis{m.group(1)}")
    preferred_dirs.append(detail_dir)

    for root in preferred_dirs:
        for name in candidate_names:
            direct = root / name
            if direct.exists() and direct.is_file():
                return direct

    # Last resort: recursive search (slower, but keeps backward compat with older folder layouts).
    for name in candidate_names:
        matches = sorted(detail_dir.glob(f"**/{name}"))
        if matches:
            return matches[0]

    return None


def _load_session_vote_info(
    session_url: str,
    *,
    timeout: int,
    detail_dir: Path | None,
    session_id: int | None,
    vote_id: int | None,
    detail_cookie: str | None,
) -> dict[str, Any]:
    session_info: dict[str, Any] = {"ok": False, "votes": [], "error": None, "source": None}
    if not session_url:
        session_info["error"] = "network-detail: empty-session-url"
        return session_info

    bad_local_path: Path | None = None
    if detail_dir is not None:
        local_path = _find_local_session_xml(
            detail_dir,
            session_id or 0,
            vote_id,
            session_url=session_url,
        )
        if local_path is not None:
            try:
                parsed = _parse_sesion_vote_xml(local_path.read_bytes())
                # Some cached files are valid XML but contain zero votes (typically an HTML-ish placeholder
                # or truncated payload from a previous run). Treat that as cache miss and retry network.
                if parsed.get("votes"):
                    return {
                        "ok": True,
                        "votes": parsed["votes"],
                        "session_date": parsed["session_date"],
                        "error": None,
                        "source": str(local_path),
                    }
                bad_local_path = local_path
                session_info["error"] = "local-empty: no-votes"
            except Exception as exc:  # noqa: BLE001
                bad_local_path = local_path
                session_info["error"] = f"local-parse: {type(exc).__name__}: {exc}"

    try:
        headers = {"Accept": "application/xml,text/xml,*/*"}
        cookie = (detail_cookie or "").strip()
        if cookie:
            headers["Cookie"] = cookie
        session_bytes, ct = http_get_bytes(session_url, timeout, headers=headers)
        if ct and "xml" not in ct.lower():
            raise RuntimeError(f"content_type inesperado: {ct}")
        parsed = _parse_sesion_vote_xml(session_bytes)

        saved_path: Path | None = None
        if detail_dir is not None:
            try:
                parsed_url = urlparse(session_url)
                filename = Path(parsed_url.path).name
                if not filename:
                    if session_id is not None and vote_id is not None:
                        filename = f"ses_{session_id}_{vote_id}.xml"
                    elif session_id is not None:
                        filename = f"ses_{session_id}.xml"
                    else:
                        filename = f"ses_{sha256_bytes(session_url.encode('utf-8'))[:12]}.xml"
                if not filename.lower().endswith(".xml"):
                    filename = f"{filename}.xml"

                m = re.search(r"/legis(\d+)/votaciones/", parsed_url.path, flags=re.I)
                out_dir = detail_dir / (f"legis{m.group(1)}" if m else "legisunknown")
                out_dir.mkdir(parents=True, exist_ok=True)

                out_path = bad_local_path or (out_dir / filename)
                if bad_local_path is not None or not out_path.exists():
                    tmp_path = out_path.with_suffix(out_path.suffix + f".tmp{os.getpid()}")
                    tmp_path.write_bytes(session_bytes)
                    try:
                        tmp_path.replace(out_path)
                    except FileExistsError:
                        try:
                            tmp_path.unlink(missing_ok=True)
                        except Exception:  # noqa: BLE001
                            pass
                saved_path = out_path if out_path.exists() else None
            except Exception:  # noqa: BLE001
                saved_path = None

        return {
            "ok": True,
            "votes": parsed["votes"],
            "session_date": parsed["session_date"],
            "error": None,
            "source": str(saved_path) if saved_path is not None else session_url,
        }
    except Exception as exc:  # noqa: BLE001
        session_info["error"] = f"network-detail: {type(exc).__name__}: {exc}"
        return session_info


def _enrich_senado_record_with_details(
    rec: dict[str, Any],
    *,
    timeout: int,
    session_cache: dict[str, dict[str, Any]],
    detail_dir: Path | None,
    detail_host: str,
    detail_cookie: str | None,
    detail_failures: list[str],
) -> None:
    # Backward compat: older stored payloads were "flat" dicts (no {"payload": {...}} wrapper).
    # In that case, mutate `rec` directly so the caller can persist enriched fields.
    payload_obj = rec.get("payload")
    if payload_obj is None:
        payload: dict[str, Any] = rec
    elif isinstance(payload_obj, dict):
        payload = payload_obj
    else:
        return

    leg = normalize_ws(str(payload.get("legislature") or rec.get("legislature") or "")) or None
    session_id = _to_int(payload.get("session_id") or rec.get("session_id"))
    if not leg or session_id is None:
        return

    vote_id = _to_int(payload.get("vote_id") or rec.get("vote_id"))
    candidate_urls = _session_vote_file_url_candidates(
        detail_host,
        leg,
        session_id,
        vote_id,
        str(payload.get("vote_file_url") or ""),
    )
    if candidate_urls:
        payload["session_vote_file_urls"] = candidate_urls
        payload["session_vote_file_url"] = candidate_urls[0]

    first_successful_session_info: dict[str, Any] | None = None
    for session_url in candidate_urls:
        if not session_url:
            continue
        session_info = session_cache.get(session_url)
        if session_info is None:
            session_info = _load_session_vote_info(
                session_url,
                timeout=timeout,
                detail_dir=detail_dir,
                session_id=session_id,
                vote_id=vote_id,
                detail_cookie=detail_cookie,
            )
            session_cache[session_url] = session_info

        if session_info.get("ok"):
            # Prefer a successful session that actually contains votes for fallback parsing.
            if first_successful_session_info is None:
                first_successful_session_info = session_info
            elif (not (first_successful_session_info.get("votes") or [])) and (session_info.get("votes") or []):
                first_successful_session_info = session_info

            candidate, method, confidence = _pick_sesion_vote(payload, session_info.get("votes") or [])
            if candidate is not None:
                payload["detail_source"] = session_info.get("source")
                payload["detail_match_method"] = method
                payload["detail_match_confidence"] = confidence
                payload["matched_num_vot"] = candidate.get("num_vot")
                payload["matched_cod_votacion"] = candidate.get("cod_votacion")
                payload["vote_date"] = candidate.get("vote_date") or session_info.get("session_date")
                payload["totals_present"] = candidate.get("totals_present")
                payload["totals_yes"] = candidate.get("totals_yes")
                payload["totals_no"] = candidate.get("totals_no")
                payload["totals_abstain"] = candidate.get("totals_abstain")
                payload["totals_no_vote"] = candidate.get("totals_no_vote")
                payload["totals_absent"] = candidate.get("totals_absent")
                payload["member_votes"] = candidate.get("member_votes") or []
                return

            session_votes = session_info.get("votes") or []
            has_nominal_data = any(
                bool(v.get("member_votes"))
                or v.get("totals_yes") is not None
                or v.get("totals_no") is not None
                or v.get("totals_abstain") is not None
                or v.get("totals_no_vote") is not None
                for v in session_votes
            )
            if has_nominal_data:
                break

    if first_successful_session_info is None:
        for session_info in session_cache.values():
            err = session_info.get("error")
            if err:
                payload["detail_error"] = err
                detail_failures.append(f"leg={leg} ses={session_id}: {err}")
                break
        if payload.get("detail_error") is None:
            payload["detail_error"] = "no-match-in-session-xml"
        return

    votes = first_successful_session_info.get("votes") or []
    session_info_source = first_successful_session_info.get("source")
    payload["detail_source"] = session_info_source
    payload["detail_match_method"] = payload.get("detail_match_method") or "fallback_session_first_vote"
    payload["detail_match_confidence"] = payload.get("detail_match_confidence") or 0.4

    candidate, method, confidence = _pick_sesion_vote(payload, votes)
    if not candidate:
        payload["detail_error"] = "no-match-in-session-xml"
        if votes:
            fallback = votes[0]
            payload["totals_present"] = fallback.get("totals_present")
            payload["totals_yes"] = fallback.get("totals_yes")
            payload["totals_no"] = fallback.get("totals_no")
            payload["totals_abstain"] = fallback.get("totals_abstain")
            payload["totals_no_vote"] = fallback.get("totals_no_vote")
            payload["totals_absent"] = fallback.get("totals_absent")
            payload["member_votes"] = fallback.get("member_votes") or []
            payload["vote_date"] = payload.get("vote_date") or first_successful_session_info.get("session_date")
        return

    payload["detail_match_method"] = method
    payload["detail_match_confidence"] = confidence
    payload["matched_num_vot"] = candidate.get("num_vot")
    payload["matched_cod_votacion"] = candidate.get("cod_votacion")
    payload["vote_date"] = candidate.get("vote_date") or first_successful_session_info.get("session_date")
    payload["totals_present"] = candidate.get("totals_present")
    payload["totals_yes"] = candidate.get("totals_yes")
    payload["totals_no"] = candidate.get("totals_no")
    payload["totals_abstain"] = candidate.get("totals_abstain")
    payload["totals_no_vote"] = candidate.get("totals_no_vote")
    payload["totals_absent"] = candidate.get("totals_absent")
    payload["member_votes"] = candidate.get("member_votes") or []


class SenadoVotacionesConnector(BaseConnector):
    source_id = "senado_votaciones"

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
        max_votes = options.get("max_votes")
        leg_filter = _parse_leg_filter(options.get("senado_legs"))
        detail_dir_opt = options.get("senado_detail_dir") or os.getenv("SENADO_DETAIL_DIR")
        detail_dir = Path(str(detail_dir_opt)) if detail_dir_opt else None
        detail_host = normalize_ws(str(options.get("senado_detail_host") or SENADO_BASE)) or SENADO_BASE
        detail_cookie = normalize_ws(str(options.get("senado_detail_cookie") or "")) or os.getenv("SENADO_DETAIL_COOKIE")
        skip_details_opt = options.get("senado_skip_details", None)
        if skip_details_opt is None:
            # Auto mode: details are expensive/fragile over the network; only try them if the
            # caller provided a reproducible cache dir or an explicit cookie.
            skip_details = not bool(detail_dir or detail_cookie)
        else:
            skip_details = bool(skip_details_opt)
        content_type = None
        records: list[dict[str, Any]] = []
        session_cache: dict[str, dict[str, Any]] = {}
        detail_failures: list[str] = []
        detail_hits = 0

        if from_file:
            paths: list[Path]
            if from_file.is_dir():
                paths = sorted([p for p in from_file.glob("*.xml") if p.is_file()])
                note = "from-dir"
            else:
                paths = [from_file]
                note = "from-file"

            for p in paths:
                xml_bytes = p.read_bytes()
                rows = _records_from_tipo12_xml(xml_bytes, f"file://{p.resolve()}")
                for rec in rows:
                    if isinstance(max_votes, int) and max_votes > 0 and len(records) >= max_votes:
                        break
                    if not skip_details:
                        _enrich_senado_record_with_details(
                            rec,
                            timeout=timeout,
                            session_cache=session_cache,
                            detail_dir=detail_dir,
                            detail_host=detail_host,
                            detail_cookie=detail_cookie,
                            detail_failures=detail_failures,
                        )
                        if (rec.get("payload") or {}).get("member_votes"):
                            detail_hits += 1
                    records.append(rec)

            meta = {
                "source": "senado_votaciones_from_file",
                "paths": [str(p) for p in paths],
                "vote_records": len(records),
                "detail_hits": detail_hits,
                "detail_failures": detail_failures,
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
        html_text = ""
        catalog_failures: list[str] = []
        if not leg_filter:
            try:
                html_bytes, content_type = http_get_bytes(
                    resolved_url,
                    timeout,
                    headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                )
                html_text = html_bytes.decode("utf-8", errors="replace")
            except Exception as exc:  # noqa: BLE001
                catalog_failures.append(f"{resolved_url} -> {type(exc).__name__}: {exc}")
                if strict_network:
                    raise

        target_legs = leg_filter or _extract_legislatures_from_catalog_html(html_text)
        if not target_legs:
            # Conservative fallback: try a reasonable range of legislatures (newest first).
            target_legs = list(range(25, 0, -1))
        target_legs = sorted({int(v) for v in target_legs if int(v) >= 0}, reverse=True)
        if isinstance(max_votes, int) and max_votes > 0 and not leg_filter and len(target_legs) > 1:
            # Debug/minimum runs: avoid crawling the full historical catalog just to fetch a few votes.
            target_legs = target_legs[:1]

        tipo12_urls: list[str] = []
        seen_tipo12: set[str] = set()
        for leg in target_legs:
            catalog_url = _set_legis_query(resolved_url, leg)
            leg_html = html_text if html_text and catalog_url == resolved_url else None
            if leg_html is None:
                try:
                    leg_html = http_get_bytes(
                        catalog_url,
                        timeout,
                        headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                    )[0].decode("utf-8", errors="replace")
                except Exception as exc:  # noqa: BLE001
                    catalog_failures.append(f"{catalog_url} -> {type(exc).__name__}: {exc}")
                    if strict_network:
                        raise
                    continue
            hrefs = re.findall(r'href="([^"]*tipoFich=12[^"]*)"', leg_html, flags=re.I)
            for href in hrefs:
                clean = htmlmod.unescape(href)
                clean = re.sub(r";jsessionid=[^?]+", "", clean, flags=re.I)
                url = urljoin(SENADO_BASE, clean)
                if url in seen_tipo12:
                    continue
                seen_tipo12.add(url)
                tipo12_urls.append(url)

        # Also derive tipoFich=12 URLs from tipoFich=9 XML (more complete than HTML in practice).
        tipo9_failures: list[str] = []
        tipo12_from_tipo9 = 0
        for leg in target_legs:
            tipo9_url = SENADO_TIPO9_URL.format(leg=leg)
            try:
                tipo9_bytes, tipo9_ct = http_get_bytes(
                    tipo9_url,
                    timeout,
                    headers={"Accept": "application/xml,text/xml,*/*"},
                )
                if tipo9_ct and "xml" not in tipo9_ct.lower():
                    raise RuntimeError(f"content_type inesperado: {tipo9_ct}")
                for u in _tipo12_urls_from_tipo9_xml(tipo9_bytes):
                    if u in seen_tipo12:
                        continue
                    seen_tipo12.add(u)
                    tipo12_urls.append(u)
                    tipo12_from_tipo9 += 1
            except Exception as exc:  # noqa: BLE001
                tipo9_failures.append(f"{tipo9_url} -> {type(exc).__name__}: {exc}")
                if strict_network:
                    raise

        detail_fetch_failures: list[str] = []
        for u in tipo12_urls:
            if isinstance(max_votes, int) and max_votes > 0 and len(records) >= max_votes:
                break
            try:
                xml_bytes, ct = http_get_bytes(u, timeout, headers={"Accept": "application/xml,text/xml,*/*"})
                if ct and "xml" not in ct.lower():
                    raise RuntimeError(f"content_type inesperado: {ct}")
                rows = _records_from_tipo12_xml(xml_bytes, u)
                if isinstance(max_votes, int) and max_votes > 0:
                    remaining = max_votes - len(records)
                    if remaining <= 0:
                        break
                    rows = rows[:remaining]
                for rec in rows:
                    if not skip_details:
                        _enrich_senado_record_with_details(
                            rec,
                            timeout=timeout,
                            session_cache=session_cache,
                            detail_dir=detail_dir,
                            detail_host=detail_host,
                            detail_cookie=detail_cookie,
                            detail_failures=detail_failures,
                        )
                        if (rec.get("payload") or {}).get("member_votes"):
                            detail_hits += 1
                    records.append(rec)
            except Exception as exc:  # noqa: BLE001
                detail_fetch_failures.append(f"{u} -> {type(exc).__name__}: {exc}")
                if strict_network:
                    raise

        meta = {
            "source": "senado_votaciones_catalog",
            "list_url": resolved_url,
            "target_legs": target_legs,
            "tipo12_urls_total": len(tipo12_urls),
            "tipo12_from_tipo9": tipo12_from_tipo9,
            "vote_records": len(records),
            "detail_hits": detail_hits,
            "detail_failures": detail_failures,
            "catalog_failures": catalog_failures,
            "tipo9_failures": tipo9_failures,
            "detail_fetch_failures": detail_fetch_failures,
        }
        payload_bytes = stable_json(meta).encode("utf-8")
        raw_path = raw_output_path(raw_dir, self.source_id, "json")
        raw_path.write_bytes(payload_bytes)

        note = "network"
        if catalog_failures or tipo9_failures or detail_fetch_failures:
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

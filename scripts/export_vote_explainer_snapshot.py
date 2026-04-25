#!/usr/bin/env python3
"""Exporta artefactos estaticos para /vote-explainer/ desde votes-preview.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


DEFAULT_SOURCE_JSON = Path("ui/gh-pages-next/public/explorer-votaciones/data/votes-preview.json")
DEFAULT_SITE_ORIGIN = "https://gsusI.github.io"
DEFAULT_SITE_BASE_PATH = "/vota-con-la-chola"


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def slugify(value: str) -> str:
    raw = safe_text(value).lower()
    if not raw:
        return "unknown-source"
    return re.sub(r"[^a-z0-9_-]+", "-", raw).strip("-") or "unknown-source"


def parse_iso_date(value: str) -> date | None:
    text = safe_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_iso_datetime(value: str) -> datetime | None:
    text = safe_text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_flag_text(value: str) -> str:
    text = safe_text(value).lower()
    return (
        text.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def chamber_from_source_id(source_id: str) -> str:
    source = safe_text(source_id)
    if source == "congreso_votaciones":
        return "Congreso"
    if source == "senado_votaciones":
        return "Senado"
    return "Institucion parlamentaria"


def compact_vote_date(value: str) -> str:
    parsed = parse_iso_date(value)
    return parsed.strftime("%Y%m%d") if parsed else "undated"


def build_public_vote_id(source_id: str, vote_date: str, vote_event_id: str) -> str:
    short_hash = hashlib.sha1(safe_text(vote_event_id).encode("utf-8")).hexdigest()[:10]
    return f"{slugify(source_id)}--{compact_vote_date(vote_date)}--{short_hash}"


def format_vote_counts_short(totals: dict[str, Any]) -> str:
    parts = [
        f"Si {int(totals.get('yes') or 0)}",
        f"No {int(totals.get('no') or 0)}",
        f"Abstencion {int(totals.get('abstain') or 0)}",
    ]
    no_vote = int(totals.get("no_vote") or 0)
    if no_vote > 0:
        parts.append(f"No vota {no_vote}")
    return " · ".join(parts)


def derive_result(event: dict[str, Any]) -> dict[str, str]:
    totals = event.get("totals") or {}
    yes = int(totals.get("yes") or 0)
    no = int(totals.get("no") or 0)
    assent = normalize_flag_text(event.get("assentimiento") or "")

    if assent and assent not in {"", "no", "false", "0"}:
        return {
            "status": "assent",
            "label": "Aprobada por asentimiento",
            "confidence": "high",
            "summary_text": "Aprobada por asentimiento.",
        }
    if yes > no:
        return {
            "status": "approved",
            "label": "Aprobada en esta votacion",
            "confidence": "medium",
            "summary_text": format_vote_counts_short(totals),
        }
    if no > yes:
        return {
            "status": "rejected",
            "label": "Rechazada en esta votacion",
            "confidence": "medium",
            "summary_text": format_vote_counts_short(totals),
        }
    if yes == no and yes > 0:
        return {
            "status": "tie_or_unclear",
            "label": "Empate o resultado no concluyente",
            "confidence": "low",
            "summary_text": format_vote_counts_short(totals),
        }
    return {
        "status": "unknown",
        "label": "Resultado no derivable automaticamente",
        "confidence": "low",
        "summary_text": format_vote_counts_short(totals),
    }


def derive_primary_source_url(event: dict[str, Any], initiative: dict[str, Any] | None) -> str:
    source_url = safe_text(event.get("source_url"))
    if source_url:
        return source_url
    initiative_url = safe_text((initiative or {}).get("url"))
    if initiative_url:
        return initiative_url
    vote_event_id = safe_text(event.get("vote_event_id"))
    if vote_event_id.startswith("url:"):
        return vote_event_id[4:]
    return ""


def is_partial_vote(event: dict[str, Any], initiative: dict[str, Any] | None) -> bool:
    subgroup_title = safe_text(event.get("subgroup_title"))
    subgroup_text = safe_text(event.get("subgroup_text"))
    if subgroup_title or subgroup_text:
        return True
    title = normalize_flag_text(event.get("title") or "")
    initiative_title = normalize_flag_text((initiative or {}).get("title") or "")
    if title.startswith("resto del "):
        return True
    if "enmienda" in title or "veto" in title:
        return True
    if initiative_title and title and title != initiative_title and "votacion final" not in title:
        if "resto" in title or "turno" in title or "apartado" in title:
            return True
    return False


def derive_freshness(snapshot_as_of_date: str, generated_at: str) -> dict[str, Any]:
    parsed_as_of = parse_iso_date(snapshot_as_of_date)
    parsed_generated = parse_iso_datetime(generated_at)
    if not parsed_as_of or not parsed_generated:
        return {
            "tier": "unknown",
            "label": "desconocida",
            "should_warn": True,
            "data_age_days": None,
            "detail": "desconocida · faltan fechas consistentes para evaluar la frescura",
        }

    generated_date = parsed_generated.date()
    if generated_date < parsed_as_of:
        return {
            "tier": "future",
            "label": "futura",
            "should_warn": True,
            "data_age_days": (parsed_as_of - generated_date).days,
            "detail": "futura · inconsistencia temporal detectada; no usar para rankings hasta corregir el snapshot",
        }

    age_days = (generated_date - parsed_as_of).days
    if age_days <= 7:
        return {
            "tier": "fresh",
            "label": "reciente",
            "should_warn": False,
            "data_age_days": age_days,
            "detail": "reciente · sin advertencia de antiguedad",
        }
    if age_days <= 30:
        return {
            "tier": "aging",
            "label": "vigente",
            "should_warn": True,
            "data_age_days": age_days,
            "detail": f"vigente · con advertencia de antiguedad ({age_days} dias) por no refresco reciente",
        }
    return {
        "tier": "stale",
        "label": "antigua",
        "should_warn": True,
        "data_age_days": age_days,
        "detail": f"antigua · la evidencia puede haber cambiado de forma material desde el corte ({age_days} dias)",
    }


def append_caveat(items: list[dict[str, str]], code: str, severity: str, label: str, detail: str) -> None:
    items.append(
        {
            "code": code,
            "severity": severity,
            "label": label,
            "detail": detail,
        }
    )


def build_caveats(
    event: dict[str, Any],
    initiative: dict[str, Any] | None,
    result: dict[str, str],
    freshness: dict[str, Any],
) -> list[dict[str, str]]:
    caveats: list[dict[str, str]] = []
    groups = event.get("group_breakdown") or []
    totals = event.get("totals") or {}
    grouped_total = sum(int((group or {}).get("total") or 0) for group in groups)
    present = int(totals.get("present") or 0)

    freshness_tier = safe_text(freshness.get("tier"))
    if freshness_tier == "aging":
        append_caveat(
            caveats,
            "aging_snapshot",
            "warn",
            "Snapshot vigente con advertencia",
            safe_text(freshness.get("detail")) or "La señal no es de ultima hora; prioriza abrir evidencia.",
        )
    elif freshness_tier == "stale":
        append_caveat(
            caveats,
            "stale_snapshot",
            "warn",
            "Snapshot antigua",
            safe_text(freshness.get("detail")) or "La evidencia puede haber cambiado de forma material desde el corte.",
        )
    elif freshness_tier == "future":
        append_caveat(
            caveats,
            "future_snapshot",
            "block",
            "Inconsistencia temporal del snapshot",
            safe_text(freshness.get("detail")) or "No usar para claims concluyentes hasta corregir el snapshot.",
        )
    elif freshness_tier == "unknown":
        append_caveat(
            caveats,
            "unknown_snapshot",
            "block",
            "Frescura desconocida",
            safe_text(freshness.get("detail")) or "Faltan fechas consistentes para evaluar la frescura.",
        )

    if not initiative:
        append_caveat(
            caveats,
            "initiative_missing",
            "warn",
            "Iniciativa oficial no enlazada",
            "Todavia no enlazamos una iniciativa oficial para esta votacion en el snapshot publico.",
        )

    if not safe_text(event.get("source_url")):
        append_caveat(
            caveats,
            "event_source_url_missing",
            "warn",
            "Falta enlace oficial directo del evento",
            "No tenemos una URL oficial directa del evento en este snapshot; usa los enlaces alternativos y el explorer para auditar.",
        )

    if safe_text(result.get("confidence")) != "high":
        append_caveat(
            caveats,
            "derived_result",
            "warn",
            "Resultado derivado",
            "El resultado se infiere de los totales de esta votacion concreta y debe contrastarse con la fuente oficial.",
        )

    if is_partial_vote(event, initiative):
        append_caveat(
            caveats,
            "subvote_not_whole_file",
            "warn",
            "Votacion parcial del expediente",
            "Esta pagina resume esta votacion concreta, no todo el expediente.",
        )

    if groups and present > 0 and grouped_total < present:
        append_caveat(
            caveats,
            "group_breakdown_partial",
            "info",
            "Desglose de grupos parcial",
            "El desglose publico de grupos es un resumen parcial y no equivale a un roll-call completo del hemiciclo.",
        )

    return caveats


def build_social_fields(
    headline: str,
    chamber: str,
    vote_date: str,
    totals: dict[str, Any],
    canonical_url: str,
) -> dict[str, str]:
    short_headline = headline[:110].rstrip()
    title = f"¿Que se voto? {short_headline} | Vota Con La Chola"
    description = f"{chamber} · {vote_date or 'sin fecha'} · {format_vote_counts_short(totals)}. Fuente oficial y caveats visibles."
    return {
        "title": title,
        "description": description,
        "canonical_url": canonical_url,
    }


def build_vote_payload(
    event: dict[str, Any],
    *,
    generated_at: str,
    snapshot_as_of_date: str,
    source_snapshot_path: str,
    site_origin: str,
    site_base_path: str,
) -> dict[str, Any]:
    initiative = event.get("initiative") if isinstance(event.get("initiative"), dict) else None
    public_vote_id = build_public_vote_id(
        safe_text(event.get("source_id")),
        safe_text(event.get("vote_date")),
        safe_text(event.get("vote_event_id")),
    )
    canonical_path = f"/vote-explainer/{public_vote_id}/"
    canonical_url = f"{site_origin.rstrip('/')}{site_base_path.rstrip('/')}{canonical_path}"
    chamber = chamber_from_source_id(event.get("source_id") or "")
    result = derive_result(event)
    freshness = derive_freshness(snapshot_as_of_date, generated_at)
    caveats = build_caveats(event, initiative, result, freshness)
    primary_source_url = derive_primary_source_url(event, initiative)
    headline = (
        safe_text((initiative or {}).get("title"))
        or safe_text(event.get("title"))
        or safe_text(event.get("expediente_text"))
        or safe_text(event.get("vote_event_id"))
    )
    subtitle = (
        safe_text(event.get("subgroup_title"))
        or safe_text(event.get("subgroup_text"))
        or safe_text((initiative or {}).get("expediente"))
    )

    payload = {
        "meta": {
            "schema_version": "vote_explainer_v1",
            "public_vote_id": public_vote_id,
            "vote_event_id": safe_text(event.get("vote_event_id")),
            "canonical_path": canonical_path,
            "generated_at": generated_at,
            "snapshot_as_of_date": snapshot_as_of_date,
            "source_snapshot_path": source_snapshot_path,
            "static_snapshot": True,
            "freshness": freshness,
        },
        "event": {
            "source_id": safe_text(event.get("source_id")),
            "source_name": safe_text(event.get("source_name")),
            "source_url": safe_text(event.get("source_url")),
            "primary_source_url": primary_source_url,
            "chamber": chamber,
            "vote_date": safe_text(event.get("vote_date")),
            "title": safe_text(event.get("title")),
            "expediente_text": safe_text(event.get("expediente_text")),
            "subgroup_title": safe_text(event.get("subgroup_title")),
            "subgroup_text": safe_text(event.get("subgroup_text")),
            "assentimiento": safe_text(event.get("assentimiento")),
            "headline": headline,
            "subtitle": subtitle,
        },
        "result": result,
        "totals": {
            "present": int((event.get("totals") or {}).get("present") or 0),
            "yes": int((event.get("totals") or {}).get("yes") or 0),
            "no": int((event.get("totals") or {}).get("no") or 0),
            "abstain": int((event.get("totals") or {}).get("abstain") or 0),
            "no_vote": int((event.get("totals") or {}).get("no_vote") or 0),
        },
        "initiative": initiative,
        "groups": event.get("group_breakdown") or [],
        "citizen_implication": event.get("citizen_implication"),
        "caveats": caveats,
        "audit_links": {
            "explorer_votaciones": f"/explorer-votaciones/?q={quote(safe_text(event.get('vote_event_id')))}",
            "explorer_source": primary_source_url,
            "initiative_url": safe_text((initiative or {}).get("url")),
            "source_snapshot": source_snapshot_path,
        },
        "social": build_social_fields(
            headline=headline,
            chamber=chamber,
            vote_date=safe_text(event.get("vote_date")),
            totals={
                "yes": int((event.get("totals") or {}).get("yes") or 0),
                "no": int((event.get("totals") or {}).get("no") or 0),
                "abstain": int((event.get("totals") or {}).get("abstain") or 0),
                "no_vote": int((event.get("totals") or {}).get("no_vote") or 0),
            },
            canonical_url=canonical_url,
        ),
    }
    return payload


def build_manifest(payloads: list[dict[str, Any]], *, generated_at: str, snapshot_as_of_date: str) -> dict[str, Any]:
    def pick_top_caveat(item: dict[str, Any]) -> dict[str, str] | None:
        caveats = item.get("caveats") or []
        if not caveats:
            return None
        for severity in ("block", "warn", "info"):
            for caveat in caveats:
                if safe_text(caveat.get("severity")) == severity:
                    return {
                        "code": safe_text(caveat.get("code")),
                        "label": safe_text(caveat.get("label")),
                        "severity": severity,
                    }
        return None

    return {
        "meta": {
            "schema_version": "vote_explainer_manifest_v1",
            "generated_at": generated_at,
            "snapshot_as_of_date": snapshot_as_of_date,
            "total_votes": len(payloads),
            "demo_public_vote_id": safe_text(payloads[0]["meta"].get("public_vote_id")) if payloads else "",
        },
        "votes": [
            {
                "public_vote_id": safe_text(item["meta"].get("public_vote_id")),
                "canonical_path": safe_text(item["meta"].get("canonical_path")),
                "vote_event_id": safe_text(item["meta"].get("vote_event_id")),
                "vote_date": safe_text(item["event"].get("vote_date")),
                "chamber": safe_text(item["event"].get("chamber")),
                "headline": safe_text(item["event"].get("headline")),
                "subtitle": safe_text(item["event"].get("subtitle")),
                "result_label": safe_text(item["result"].get("label")),
                "summary_text": safe_text(item["result"].get("summary_text")),
                "primary_source_url": safe_text(item["event"].get("primary_source_url")),
                "caveat_codes": [safe_text(caveat.get("code")) for caveat in item.get("caveats") or []],
                "top_caveat": pick_top_caveat(item),
            }
            for item in payloads
        ],
    }


def load_source_payload(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    events = raw.get("events")
    if not isinstance(events, list):
        raise ValueError("source-json must include an events array")
    return raw


def export_vote_explainer_snapshot(
    *,
    source_json_path: Path,
    out_dir: Path,
    snapshot_as_of_date: str,
    generated_at: str,
    source_snapshot_path: str,
    site_origin: str,
    site_base_path: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_payload = load_source_payload(source_json_path)
    events = source_payload.get("events") or []
    if not snapshot_as_of_date:
        snapshot_as_of_date = safe_text(source_payload.get("meta", {}).get("snapshot_as_of_date"))
    if not snapshot_as_of_date:
        dated = [parse_iso_date(safe_text(event.get("vote_date"))) for event in events]
        dated = [item for item in dated if item is not None]
        snapshot_as_of_date = max(dated).isoformat() if dated else ""

    payloads = [
        build_vote_payload(
            event,
            generated_at=generated_at,
            snapshot_as_of_date=snapshot_as_of_date,
            source_snapshot_path=source_snapshot_path,
            site_origin=site_origin,
            site_base_path=site_base_path,
        )
        for event in events
        if isinstance(event, dict)
    ]
    manifest = build_manifest(payloads, generated_at=generated_at, snapshot_as_of_date=snapshot_as_of_date)

    out_dir.mkdir(parents=True, exist_ok=True)
    for old_json in out_dir.glob("*.json"):
        old_json.unlink()
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for payload in payloads:
        public_vote_id = safe_text(payload["meta"].get("public_vote_id"))
        if not public_vote_id:
            continue
        (out_dir / f"{public_vote_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return manifest, payloads


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta JSON estatico por voto para /vote-explainer/")
    parser.add_argument("--source-json", default=str(DEFAULT_SOURCE_JSON), help="Ruta al votes-preview.json fuente")
    parser.add_argument("--out-dir", required=True, help="Directorio de salida")
    parser.add_argument("--snapshot-as-of-date", default="", help="Fecha de corte YYYY-MM-DD")
    parser.add_argument("--generated-at", default="", help="Timestamp ISO 8601 UTC")
    parser.add_argument(
        "--source-snapshot-path",
        default="/explorer-votaciones/data/votes-preview.json",
        help="Ruta web publica al snapshot fuente",
    )
    parser.add_argument("--site-origin", default=DEFAULT_SITE_ORIGIN, help="Origen del sitio publico")
    parser.add_argument("--site-base-path", default=DEFAULT_SITE_BASE_PATH, help="Base path publica del sitio")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_json_path = Path(args.source_json)
    out_dir = Path(args.out_dir)
    if not source_json_path.exists():
        print(f"ERROR: no existe el source-json -> {source_json_path}")
        return 2

    generated_at = safe_text(args.generated_at) or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest, payloads = export_vote_explainer_snapshot(
        source_json_path=source_json_path,
        out_dir=out_dir,
        snapshot_as_of_date=safe_text(args.snapshot_as_of_date),
        generated_at=generated_at,
        source_snapshot_path=safe_text(args.source_snapshot_path) or "/explorer-votaciones/data/votes-preview.json",
        site_origin=safe_text(args.site_origin) or DEFAULT_SITE_ORIGIN,
        site_base_path=safe_text(args.site_base_path) or DEFAULT_SITE_BASE_PATH,
    )
    print(
        "OK vote explainer snapshot -> "
        f"{out_dir} (votes={len(payloads)} demo={safe_text(manifest.get('meta', {}).get('demo_public_vote_id'))})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

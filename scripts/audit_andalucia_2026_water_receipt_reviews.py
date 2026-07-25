#!/usr/bin/env python3
"""Audit structured, independent reviews left on the water-receipt issue."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REVIEW_MARKER = "<!-- andalucia-water-review:v1 -->"
STATUS_MARKER = "<!-- andalucia-water-review-status:v1 -->"
DEFAULT_ISSUE_URL = (
    "https://github.com/gsusI/vota-con-la-chola/issues/20"
)
REQUIRED_FIELDS = {
    "pista",
    "veredicto",
    "compromiso",
    "evidencia",
    "detalle",
}
TRACKS = {
    "declaraciones": "Declaraciones",
    "ventana-evidencia": "Ventana de evidencia",
    "clasificacion": "Clasificación",
    "responsabilidad": "Responsabilidad",
    "uso-ciudadano": "Uso ciudadano",
}
VERDICTS = {
    "correcto",
    "correccion-necesaria",
    "evidencia-adicional",
}
INTERNAL_ASSOCIATIONS = {
    "OWNER",
    "MEMBER",
    "COLLABORATOR",
}
OFFICIAL_HOST_PATTERN = re.compile(
    r"https://(?:[a-z0-9.-]+\.)?"
    r"(?:juntadeandalucia\.es|parlamentodeandalucia\.es)"
    r"(?:[/:?#]|$)",
    re.IGNORECASE,
)
FIELD_PATTERN = re.compile(
    r"^\s*(pista|veredicto|compromiso|evidencia|detalle)\s*:\s*(.*?)\s*$",
    re.IGNORECASE,
)


def _flatten_comments(raw: object) -> list[dict]:
    if isinstance(raw, dict):
        raw = raw.get("comments", [])
    if not isinstance(raw, list):
        raise ValueError("comments payload must be an array")
    comments: list[dict] = []
    for item in raw:
        if isinstance(item, list):
            comments.extend(
                child for child in item if isinstance(child, dict)
            )
        elif isinstance(item, dict):
            comments.append(item)
    return comments


def load_comments(path: Path) -> list[dict]:
    return _flatten_comments(json.loads(path.read_text(encoding="utf-8")))


def _comment_order(comment: dict) -> tuple[str, str, int]:
    return (
        str(comment.get("updated_at") or ""),
        str(comment.get("created_at") or ""),
        int(comment.get("id") or 0),
    )


def _parse_fields(body: str) -> tuple[dict[str, str] | None, str | None]:
    if REVIEW_MARKER not in body:
        return None, "missing_review_marker"
    fields: dict[str, str] = {}
    marker_tail = body.split(REVIEW_MARKER, 1)[1]
    for line in marker_tail.splitlines():
        match = FIELD_PATTERN.match(line)
        if not match:
            continue
        key = match.group(1).lower()
        if key in fields:
            return None, f"duplicate_field:{key}"
        fields[key] = match.group(2).strip()
    missing = sorted(REQUIRED_FIELDS - fields.keys())
    if missing:
        return None, f"missing_fields:{','.join(missing)}"
    return fields, None


def _reject_reason(
    comment: dict,
    *,
    excluded_logins: set[str],
) -> str | None:
    user = comment.get("user")
    if not isinstance(user, dict):
        return "missing_author"
    login = str(user.get("login") or "").strip()
    if not login:
        return "missing_author"
    normalized_login = login.casefold()
    user_type = str(user.get("type") or "").casefold()
    if user_type == "bot" or normalized_login.endswith("[bot]"):
        return "bot_author"
    if normalized_login in excluded_logins:
        return "excluded_author"
    association = str(comment.get("author_association") or "").upper()
    if association in INTERNAL_ASSOCIATIONS:
        return f"internal_author:{association.lower()}"
    return None


def parse_review(
    comment: dict,
    *,
    excluded_logins: set[str],
) -> tuple[dict | None, str | None]:
    author_reason = _reject_reason(
        comment,
        excluded_logins=excluded_logins,
    )
    if author_reason:
        return None, author_reason

    body = str(comment.get("body") or "")
    fields, field_error = _parse_fields(body)
    if field_error:
        return None, field_error
    assert fields is not None

    track = fields["pista"].casefold()
    verdict = fields["veredicto"].casefold()
    if track not in TRACKS:
        return None, f"unsupported_track:{track}"
    if verdict not in VERDICTS:
        return None, f"unsupported_verdict:{verdict}"
    if len(fields["compromiso"]) < 3:
        return None, "commitment_scope_too_short"
    if len(fields["evidencia"]) < 8:
        return None, "evidence_too_short"
    if len(fields["detalle"]) < 30:
        return None, "detail_too_short"
    if (
        track != "uso-ciudadano"
        and not OFFICIAL_HOST_PATTERN.search(fields["evidencia"])
    ):
        return None, "official_evidence_url_required"

    user = comment["user"]
    return {
        "comment_id": int(comment.get("id") or 0),
        "comment_url": str(comment.get("html_url") or ""),
        "reviewer_login": str(user["login"]),
        "track": track,
        "track_label": TRACKS[track],
        "verdict": verdict,
        "commitment_scope": fields["compromiso"],
        "evidence": fields["evidencia"],
        "detail": fields["detalle"],
        "created_at": str(comment.get("created_at") or ""),
        "updated_at": str(comment.get("updated_at") or ""),
    }, None


def build_audit(
    comments: list[dict],
    *,
    excluded_logins: set[str] | None = None,
    required_reviewers: int = 5,
    issue_url: str = DEFAULT_ISSUE_URL,
) -> dict:
    if required_reviewers < 1:
        raise ValueError("required_reviewers must be positive")
    normalized_exclusions = {
        login.strip().casefold()
        for login in (excluded_logins or set())
        if login.strip()
    }
    valid_reviews: list[dict] = []
    rejected_comments: list[dict] = []
    for comment in comments:
        review, reason = parse_review(
            comment,
            excluded_logins=normalized_exclusions,
        )
        if review:
            valid_reviews.append(review)
        else:
            rejected_comments.append(
                {
                    "comment_id": int(comment.get("id") or 0),
                    "comment_url": str(comment.get("html_url") or ""),
                    "reason": reason,
                }
            )

    active_by_reviewer_track: dict[tuple[str, str], dict] = {}
    for review in sorted(
        valid_reviews,
        key=lambda item: (
            item["updated_at"],
            item["created_at"],
            item["comment_id"],
        ),
    ):
        key = (review["reviewer_login"].casefold(), review["track"])
        active_by_reviewer_track[key] = review
    active_reviews = sorted(
        active_by_reviewer_track.values(),
        key=lambda item: (
            item["reviewer_login"].casefold(),
            item["track"],
        ),
    )

    reviewer_map: dict[str, dict] = {}
    for review in active_reviews:
        login_key = review["reviewer_login"].casefold()
        reviewer = reviewer_map.setdefault(
            login_key,
            {
                "login": review["reviewer_login"],
                "tracks": [],
                "review_urls": [],
                "verdicts": [],
            },
        )
        reviewer["tracks"].append(review["track"])
        if review["comment_url"]:
            reviewer["review_urls"].append(review["comment_url"])
        reviewer["verdicts"].append(review["verdict"])

    reviewers = sorted(
        reviewer_map.values(),
        key=lambda item: item["login"].casefold(),
    )
    tracks_covered = sorted({review["track"] for review in active_reviews})
    missing_tracks = sorted(set(TRACKS) - set(tracks_covered))
    changes_requested = [
        review
        for review in active_reviews
        if review["verdict"] != "correcto"
    ]

    reviewer_threshold_met = len(reviewers) >= required_reviewers
    track_threshold_met = not missing_tracks
    no_open_findings = not changes_requested
    if not reviewer_threshold_met:
        status = "pending_reviewers"
    elif not track_threshold_met:
        status = "pending_tracks"
    elif not no_open_findings:
        status = "changes_requested"
    else:
        status = "verified"

    return {
        "schema_version": "andalucia_water_community_review_v1",
        "issue_url": issue_url,
        "status": status,
        "review_gate_complete": status == "verified",
        "required_reviewers": required_reviewers,
        "valid_reviewers_total": len(reviewers),
        "valid_review_comments_total": len(active_reviews),
        "rejected_comments_total": len(rejected_comments),
        "tracks_required_total": len(TRACKS),
        "tracks_covered_total": len(tracks_covered),
        "tracks_covered": tracks_covered,
        "missing_tracks": missing_tracks,
        "open_findings_total": len(changes_requested),
        "reviewers": reviewers,
        "active_reviews": active_reviews,
        "open_findings": changes_requested,
        "rejected_comments": rejected_comments,
    }


def render_markdown(audit: dict) -> str:
    track_lines = []
    covered = set(audit["tracks_covered"])
    for track, label in TRACKS.items():
        marker = "x" if track in covered else " "
        track_lines.append(f"- [{marker}] `{track}` — {label}")

    if audit["reviewers"]:
        reviewer_lines = [
            f"- @{item['login']}: {', '.join(f'`{track}`' for track in item['tracks'])}"
            for item in audit["reviewers"]
        ]
    else:
        reviewer_lines = ["- Ninguna revisión independiente válida todavía."]

    if audit["open_findings"]:
        finding_lines = [
            (
                f"- @{item['reviewer_login']} / `{item['track']}`: "
                f"`{item['verdict']}`"
            )
            for item in audit["open_findings"]
        ]
    else:
        finding_lines = ["- Ningún hallazgo abierto en las revisiones válidas."]

    return "\n".join(
        [
            STATUS_MARKER,
            "## Estado verificable de la revisión",
            "",
            (
                f"**{audit['valid_reviewers_total']}/"
                f"{audit['required_reviewers']} revisores independientes** · "
                f"**{audit['tracks_covered_total']}/"
                f"{audit['tracks_required_total']} pistas cubiertas** · "
                f"**{audit['open_findings_total']} hallazgos abiertos**"
            ),
            "",
            f"Estado de máquina: `{audit['status']}`.",
            "",
            "### Cobertura",
            "",
            *track_lines,
            "",
            "### Revisores válidos",
            "",
            *reviewer_lines,
            "",
            "### Hallazgos",
            "",
            *finding_lines,
            "",
            (
                "El contador excluye bots, propietario, miembros y colaboradores; "
                "deduplica por revisor y pista; y conserva la revisión válida más "
                "reciente de cada par."
            ),
        ]
    ) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comments-json", type=Path, required=True)
    parser.add_argument("--status-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--issue-url", default=DEFAULT_ISSUE_URL)
    parser.add_argument("--required-reviewers", type=int, default=5)
    parser.add_argument("--exclude-login", action="append", default=[])
    parser.add_argument("--fail-unless-complete", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = build_audit(
        load_comments(args.comments_json),
        excluded_logins=set(args.exclude_login),
        required_reviewers=args.required_reviewers,
        issue_url=args.issue_url,
    )
    encoded = json.dumps(
        audit,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.status_out:
        args.status_out.parent.mkdir(parents=True, exist_ok=True)
        args.status_out.write_text(encoded, encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(
            render_markdown(audit),
            encoding="utf-8",
        )
    print(encoded, end="")
    return 1 if args.fail_unless_complete and not audit["review_gate_complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

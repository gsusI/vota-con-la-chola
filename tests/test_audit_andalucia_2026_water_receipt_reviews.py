import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "scripts/audit_andalucia_2026_water_receipt_reviews.py"
)
SPEC = importlib.util.spec_from_file_location(
    "water_receipt_review_auditor",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def review_comment(
    comment_id,
    login,
    track,
    *,
    verdict="correcto",
    association="NONE",
    user_type="User",
    evidence=None,
    detail=None,
    updated_at=None,
):
    if evidence is None:
        evidence = (
            "https://www.juntadeandalucia.es/boja/2026/512/1"
            if track != "uso-ciudadano"
            else "iPhone 13, Safari, anchura 390 px"
        )
    if detail is None:
        detail = (
            "Contrasté el contenido, el localizador y el límite publicado "
            "sin encontrar una afirmación más fuerte que la evidencia."
        )
    body = "\n".join(
        [
            MODULE.REVIEW_MARKER,
            f"pista: {track}",
            f"veredicto: {verdict}",
            "compromiso: todos",
            f"evidencia: {evidence}",
            f"detalle: {detail}",
        ]
    )
    timestamp = updated_at or f"2026-07-{comment_id + 10:02d}T10:00:00Z"
    return {
        "id": comment_id,
        "html_url": f"https://github.com/example/repo/issues/20#issuecomment-{comment_id}",
        "body": body,
        "created_at": timestamp,
        "updated_at": timestamp,
        "author_association": association,
        "user": {
            "login": login,
            "type": user_type,
        },
    }


class AndaluciaWaterReceiptReviewAuditTest(unittest.TestCase):
    def test_flattens_paginated_github_api_response(self):
        first = review_comment(1, "ana", "declaraciones")
        second = review_comment(2, "bea", "uso-ciudadano")

        flattened = MODULE._flatten_comments([[first], [second], []])

        self.assertEqual(
            [item["id"] for item in flattened],
            [1, 2],
        )

    def test_empty_review_lane_is_explicitly_pending(self):
        audit = MODULE.build_audit([], excluded_logins={"owner"})

        self.assertEqual(audit["status"], "pending_reviewers")
        self.assertFalse(audit["review_gate_complete"])
        self.assertEqual(audit["valid_reviewers_total"], 0)
        self.assertEqual(audit["tracks_covered_total"], 0)

    def test_rejects_bot_owner_internal_and_unstructured_comments(self):
        comments = [
            review_comment(1, "owner", "declaraciones"),
            review_comment(
                2,
                "checks[bot]",
                "declaraciones",
                user_type="Bot",
            ),
            review_comment(
                3,
                "maintainer",
                "declaraciones",
                association="MEMBER",
            ),
            {
                "id": 4,
                "body": "Parece correcto.",
                "user": {"login": "reader", "type": "User"},
                "author_association": "NONE",
            },
        ]

        audit = MODULE.build_audit(
            comments,
            excluded_logins={"owner"},
        )

        self.assertEqual(audit["valid_reviewers_total"], 0)
        self.assertEqual(audit["rejected_comments_total"], 4)
        self.assertEqual(
            {item["reason"] for item in audit["rejected_comments"]},
            {
                "excluded_author",
                "bot_author",
                "internal_author:member",
                "missing_review_marker",
            },
        )

    def test_data_tracks_require_specific_official_evidence_url(self):
        comment = review_comment(
            1,
            "reader",
            "declaraciones",
            evidence="He revisado la fuente que aparece en la página.",
        )

        audit = MODULE.build_audit([comment])

        self.assertEqual(audit["valid_reviewers_total"], 0)
        self.assertEqual(
            audit["rejected_comments"][0]["reason"],
            "official_evidence_url_required",
        )

    def test_counts_unique_reviewers_and_all_tracks(self):
        comments = [
            review_comment(1, "ana", "declaraciones"),
            review_comment(2, "bea", "ventana-evidencia"),
            review_comment(3, "carla", "clasificacion"),
            review_comment(4, "dani", "responsabilidad"),
            review_comment(5, "elena", "uso-ciudadano"),
        ]

        audit = MODULE.build_audit(
            comments,
            excluded_logins={"owner"},
        )

        self.assertEqual(audit["status"], "verified")
        self.assertTrue(audit["review_gate_complete"])
        self.assertEqual(audit["valid_reviewers_total"], 5)
        self.assertEqual(audit["tracks_covered_total"], 5)
        self.assertEqual(audit["open_findings_total"], 0)

    def test_one_reviewer_covering_many_tracks_counts_once(self):
        comments = [
            review_comment(1, "ana", "declaraciones"),
            review_comment(2, "ana", "ventana-evidencia"),
            review_comment(3, "ana", "clasificacion"),
            review_comment(4, "ana", "responsabilidad"),
            review_comment(5, "ana", "uso-ciudadano"),
        ]

        audit = MODULE.build_audit(comments)

        self.assertEqual(audit["valid_reviewers_total"], 1)
        self.assertEqual(audit["tracks_covered_total"], 5)
        self.assertEqual(audit["status"], "pending_reviewers")

    def test_latest_review_by_same_reviewer_and_track_supersedes_old_one(self):
        comments = [
            review_comment(
                1,
                "ana",
                "declaraciones",
                verdict="correccion-necesaria",
                updated_at="2026-07-25T10:00:00Z",
            ),
            review_comment(
                2,
                "ana",
                "declaraciones",
                verdict="correcto",
                updated_at="2026-07-26T10:00:00Z",
            ),
        ]

        audit = MODULE.build_audit(comments)

        self.assertEqual(audit["valid_review_comments_total"], 1)
        self.assertEqual(audit["open_findings_total"], 0)
        self.assertEqual(
            audit["active_reviews"][0]["comment_id"],
            2,
        )

    def test_open_finding_blocks_milestone(self):
        tracks = list(MODULE.TRACKS)
        comments = [
            review_comment(
                index,
                f"reviewer-{index}",
                track,
                verdict=(
                    "evidencia-adicional"
                    if track == "clasificacion"
                    else "correcto"
                ),
            )
            for index, track in enumerate(tracks, start=1)
        ]

        audit = MODULE.build_audit(comments)

        self.assertEqual(audit["valid_reviewers_total"], 5)
        self.assertEqual(audit["tracks_covered_total"], 5)
        self.assertEqual(audit["status"], "changes_requested")
        self.assertFalse(audit["review_gate_complete"])
        self.assertEqual(audit["open_findings_total"], 1)

    def test_markdown_exposes_machine_status_and_coverage(self):
        audit = MODULE.build_audit(
            [review_comment(1, "ana", "declaraciones")]
        )

        markdown = MODULE.render_markdown(audit)

        self.assertIn(MODULE.STATUS_MARKER, markdown)
        self.assertIn("1/5 revisores independientes", markdown)
        self.assertIn("1/5 pistas cubiertas", markdown)
        self.assertIn("`pending_reviewers`", markdown)
        self.assertIn("@ana", markdown)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.declared_stance import (
    _infer_declared_stance_detail,
    backfill_declared_stance_from_topic_evidence,
    infer_declared_stance,
)
from etl.politicos_es.util import canonical_key, now_utc_iso, sha256_bytes


class TestParlDeclaredStance(unittest.TestCase):
    def test_infer_declared_stance_support_oppose_abstain(self) -> None:
        sup = infer_declared_stance("Votaremos a favor.")
        opp = infer_declared_stance("Votaremos en contra.")
        abst = infer_declared_stance("Nos abstendremos.")
        declared = infer_declared_stance("Apoyamos esta iniciativa.")
        catalan_sup = infer_declared_stance("Nosaltres votarem a favor de l'informe.")
        catalan_opp = infer_declared_stance("Votarem en contra de les esmenes.")
        neg_support = infer_declared_stance("No apoyamos esta iniciativa.")
        votar_fav = infer_declared_stance("Nosotros vamos a votar favorablemente esta enmienda.")
        votar_neg = infer_declared_stance("Vamos a votar negativamente la propuesta.")
        voted_past = infer_declared_stance("Votamos en contra porque era insuficiente.")
        no_vote_fav = infer_declared_stance("No vamos a votar a favor de esta proposición.")
        vote_comma_against = infer_declared_stance("Votaremos, obviamente, en contra de su enmienda.")
        no_vote_abs_favor = infer_declared_stance("No vamos a votar en absoluto a favor de la enmienda.")
        voto_sea_favor = infer_declared_stance("Hará que nuestro voto sea favorable a que continúe la ley.")
        self.assertIsNotNone(sup)
        self.assertIsNotNone(opp)
        self.assertIsNotNone(abst)
        self.assertIsNotNone(declared)
        self.assertIsNotNone(catalan_sup)
        self.assertIsNotNone(catalan_opp)
        self.assertIsNotNone(neg_support)
        self.assertIsNotNone(votar_fav)
        self.assertIsNotNone(votar_neg)
        self.assertIsNotNone(voted_past)
        self.assertIsNotNone(no_vote_fav)
        self.assertIsNotNone(vote_comma_against)
        self.assertIsNotNone(no_vote_abs_favor)
        self.assertIsNotNone(voto_sea_favor)
        self.assertEqual(sup[0], "support")
        self.assertEqual(opp[0], "oppose")
        self.assertEqual(abst[0], "mixed")
        self.assertEqual(declared[0], "support")
        self.assertEqual(catalan_sup[0], "support")
        self.assertEqual(catalan_opp[0], "oppose")
        self.assertEqual(neg_support[0], "oppose")
        self.assertEqual(votar_fav[0], "support")
        self.assertEqual(votar_neg[0], "oppose")
        self.assertEqual(voted_past[0], "oppose")
        self.assertEqual(no_vote_fav[0], "oppose")
        self.assertEqual(vote_comma_against[0], "oppose")
        self.assertEqual(no_vote_abs_favor[0], "oppose")
        self.assertEqual(voto_sea_favor[0], "support")
        self.assertGreaterEqual(float(sup[2]), 0.7)
        self.assertGreaterEqual(float(declared[2]), 0.62)
        self.assertGreaterEqual(float(neg_support[2]), 0.62)
        self.assertIsNone(infer_declared_stance("Voten a favor."))
        self.assertIsNone(infer_declared_stance("Sin señal explícita."))
        self.assertIsNone(infer_declared_stance("Esperamos que sus señorías voten favorablemente esta enmienda."))
        self.assertIsNone(infer_declared_stance("Nadie ha votado a favor de una enmienda de este bloque."))

    def test_infer_declared_stance_regex_v3_curated_signal_pct(self) -> None:
        snippets = [
            "Vamos a votar a favor de su toma en consideración.",
            "Votaremos favorablemente el informe de esta comisión.",
            "Nosotros vamos a votar en contra de su propuesta.",
            "No apoyaremos esta enmienda de totalidad.",
            "Hoy defendemos esta iniciativa.",
            "Se reanuda la sesión a las nueve de la mañana.",
            "La votación no se producirá antes de las trece horas.",
            "Tiene la palabra la señora portavoz.",
            "Muchas gracias, señor presidente.",
            "Sin señal explícita.",
        ]
        signal_count = 0
        for text in snippets:
            inferred = infer_declared_stance(text)
            if inferred is not None and inferred[0] in ("support", "oppose", "mixed"):
                signal_count += 1
        self.assertGreaterEqual(signal_count / len(snippets), 0.30)

    def test_infer_declared_stance_regex_v3_false_positive_negative_regressions(self) -> None:
        false_negative_cases = [
            ("Nosotros vamos a votar favorablemente esta ley.", "support"),
            ("Votamos a favor de la enmienda transaccional.", "support"),
            ("Hemos votado en contra de ese artículo.", "oppose"),
            ("No votaremos a favor de esta proposición.", "oppose"),
            ("Votaremos, obviamente, en contra de su enmienda.", "oppose"),
            ("No vamos a votar en absoluto a favor de la enmienda de Vox.", "oppose"),
            ("Hará que nuestro voto sea favorable a que esta ley continúe.", "support"),
        ]
        false_positive_cases = [
            "Esperamos que ustedes voten favorablemente esta enmienda.",
            "Nadie ha votado a favor de esa propuesta.",
            "Se inicia la votación de conjunto del dictamen.",
            "Luego votaremos las enmiendas por separado.",
            "Nos genera dudas a la hora de si votar favorablemente esta proposición.",
        ]

        for text, expected in false_negative_cases:
            inferred = infer_declared_stance(text)
            self.assertIsNotNone(inferred, msg=text)
            self.assertEqual(inferred[0], expected, msg=text)

        for text in false_positive_cases:
            inferred = infer_declared_stance(text)
            self.assertIsNone(inferred, msg=text)

    def test_infer_declared_stance_regex_v3_reason_confidence_policy(self) -> None:
        explicit_support = _infer_declared_stance_detail("Votaremos a favor de esta iniciativa.")
        abstention = _infer_declared_stance_detail("Nos abstendremos en esta votación.")
        declared_support_strong = _infer_declared_stance_detail("Apoyamos esta iniciativa.")
        declared_oppose_strong = _infer_declared_stance_detail("Rechazamos esta propuesta.")
        declared_support_weak = _infer_declared_stance_detail("Defendemos este modelo social.")
        declared_oppose_weak = _infer_declared_stance_detail("Nos oponemos totalmente.")
        conflicting = _infer_declared_stance_detail("Votaremos a favor, pero no apoyamos esta ley.")

        self.assertEqual(explicit_support, ("support", 1, 0.74, "explicit_vote_intent"))
        self.assertEqual(abstention, ("mixed", 0, 0.68, "abstention_intent"))
        self.assertEqual(declared_support_strong, ("support", 1, 0.66, "declared_support"))
        self.assertEqual(declared_oppose_strong, ("oppose", -1, 0.66, "declared_oppose"))
        self.assertEqual(declared_support_weak, ("support", 1, 0.58, "weak_declared_support"))
        self.assertEqual(declared_oppose_weak, ("oppose", -1, 0.58, "weak_declared_oppose"))
        self.assertEqual(conflicting, ("mixed", 0, 0.58, "conflicting_signal"))

    def test_backfill_declared_stance_regex_v3_queues_low_confidence_and_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "declared-stance-v3-reviews.db"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                ckey = canonical_key(full_name="Persona Demo", birth_date=None, territory_code="")
                conn.execute(
                    """
                    INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("Persona Demo", ckey, now, now),
                )
                person_id = int(
                    conn.execute(
                        "SELECT person_id FROM persons WHERE canonical_key = ?",
                        (ckey,),
                    ).fetchone()["person_id"]
                )

                sr_payload = '{"kind":"intervention","id":"test"}'
                sr_sha = sha256_bytes(sr_payload.encode("utf-8"))
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("congreso_intervenciones", "v3:weak", "2026-02-12", sr_payload, sr_sha, now, now),
                )
                sr_pk_weak = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id = ? AND source_record_id = ?",
                        ("congreso_intervenciones", "v3:weak"),
                    ).fetchone()["source_record_pk"]
                )
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("congreso_intervenciones", "v3:conflict", "2026-02-12", sr_payload, sr_sha, now, now),
                )
                sr_pk_conflict = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id = ? AND source_record_id = ?",
                        ("congreso_intervenciones", "v3:conflict"),
                    ).fetchone()["source_record_pk"]
                )

                conn.execute(
                    """
                    INSERT INTO topic_evidence (
                      topic_id, topic_set_id,
                      person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      evidence_type, evidence_date, title, excerpt,
                      stance, polarity, weight, confidence,
                      topic_method, stance_method,
                      vote_event_id, initiative_id,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (
                      NULL, NULL,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:intervention', '2026-02-12', NULL, ?,
                      'unclear', 0, 0.5, 0.2,
                      NULL, 'intervention_metadata',
                      NULL, NULL,
                      'congreso_intervenciones', 'https://example.invalid', ?, '2026-02-12',
                      '{}', ?, ?
                    )
                    """,
                    (person_id, "Defendemos este modelo social.", sr_pk_weak, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO topic_evidence (
                      topic_id, topic_set_id,
                      person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      evidence_type, evidence_date, title, excerpt,
                      stance, polarity, weight, confidence,
                      topic_method, stance_method,
                      vote_event_id, initiative_id,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (
                      NULL, NULL,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:intervention', '2026-02-12', NULL, ?,
                      'unclear', 0, 0.5, 0.2,
                      NULL, 'intervention_metadata',
                      NULL, NULL,
                      'congreso_intervenciones', 'https://example.invalid', ?, '2026-02-12',
                      '{}', ?, ?
                    )
                    """,
                    (
                        person_id,
                        "Votaremos a favor, pero no apoyamos esta ley.",
                        sr_pk_conflict,
                        now,
                        now,
                    ),
                )
                conn.commit()

                result = backfill_declared_stance_from_topic_evidence(
                    conn,
                    source_id="congreso_intervenciones",
                    limit=0,
                    min_auto_confidence=0.62,
                    dry_run=False,
                )

                self.assertEqual(int(result.get("updated", 0)), 0)
                self.assertEqual(int(result.get("review_pending", 0)), 2)
                by_reason = result.get("review_pending_by_reason", {})
                self.assertEqual(int(by_reason.get("low_confidence", 0)), 1)
                self.assertEqual(int(by_reason.get("conflicting_signal", 0)), 1)

                evidence_rows = conn.execute(
                    """
                    SELECT source_record_pk, stance, polarity, confidence, stance_method
                    FROM topic_evidence
                    WHERE source_record_pk IN (?, ?)
                    ORDER BY source_record_pk ASC
                    """,
                    (sr_pk_weak, sr_pk_conflict),
                ).fetchall()
                self.assertEqual(len(evidence_rows), 2)
                for row in evidence_rows:
                    self.assertEqual(str(row["stance"]), "unclear")
                    self.assertEqual(int(row["polarity"]), 0)
                    self.assertEqual(str(row["stance_method"]), "intervention_metadata")

                review_rows = conn.execute(
                    """
                    SELECT source_record_pk, review_reason, suggested_stance, suggested_confidence, status
                    FROM topic_evidence_reviews
                    WHERE source_record_pk IN (?, ?)
                    ORDER BY source_record_pk ASC
                    """,
                    (sr_pk_weak, sr_pk_conflict),
                ).fetchall()
                self.assertEqual(len(review_rows), 2)
                self.assertEqual(str(review_rows[0]["review_reason"]), "low_confidence")
                self.assertEqual(str(review_rows[0]["suggested_stance"]), "support")
                self.assertAlmostEqual(float(review_rows[0]["suggested_confidence"]), 0.58, places=6)
                self.assertEqual(str(review_rows[0]["status"]), "pending")
                self.assertEqual(str(review_rows[1]["review_reason"]), "conflicting_signal")
                self.assertEqual(str(review_rows[1]["suggested_stance"]), "mixed")
                self.assertAlmostEqual(float(review_rows[1]["suggested_confidence"]), 0.58, places=6)
                self.assertEqual(str(review_rows[1]["status"]), "pending")
            finally:
                conn.close()

    def test_backfill_declared_stance_from_topic_evidence_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "declared-stance.db"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                ckey = canonical_key(full_name="Persona Demo", birth_date=None, territory_code="")
                conn.execute(
                    """
                    INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("Persona Demo", ckey, now, now),
                )
                person_id = int(
                    conn.execute(
                        "SELECT person_id FROM persons WHERE canonical_key = ?",
                        (ckey,),
                    ).fetchone()["person_id"]
                )

                sr_payload = '{"kind":"intervention","id":"test"}'
                sr_sha = sha256_bytes(sr_payload.encode("utf-8"))
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("congreso_intervenciones", "test:1", "2026-02-12", sr_payload, sr_sha, now, now),
                )
                sr_pk = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id = ? AND source_record_id = ?",
                        ("congreso_intervenciones", "test:1"),
                    ).fetchone()["source_record_pk"]
                )
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("congreso_intervenciones", "test:2", "2026-02-12", sr_payload, sr_sha, now, now),
                )
                sr_pk_2 = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id = ? AND source_record_id = ?",
                        ("congreso_intervenciones", "test:2"),
                    ).fetchone()["source_record_pk"]
                )
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("congreso_intervenciones", "test:3", "2026-02-12", sr_payload, sr_sha, now, now),
                )
                sr_pk_3 = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id = ? AND source_record_id = ?",
                        ("congreso_intervenciones", "test:3"),
                    ).fetchone()["source_record_pk"]
                )

                conn.execute(
                    """
                    INSERT INTO topic_evidence (
                      topic_id, topic_set_id,
                      person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      evidence_type, evidence_date, title, excerpt,
                      stance, polarity, weight, confidence,
                      topic_method, stance_method,
                      vote_event_id, initiative_id,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (
                      NULL, NULL,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:intervention', '2026-02-12', NULL, ?,
                      'unclear', 0, 0.5, 0.2,
                      NULL, 'intervention_metadata',
                      NULL, NULL,
                      'congreso_intervenciones', 'https://example.invalid', ?, '2026-02-12',
                      '{}', ?, ?
                    )
                    """,
                    (person_id, "Votaremos a favor de esta iniciativa.", sr_pk, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO topic_evidence (
                      topic_id, topic_set_id,
                      person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      evidence_type, evidence_date, title, excerpt,
                      stance, polarity, weight, confidence,
                      topic_method, stance_method,
                      vote_event_id, initiative_id,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (
                      NULL, NULL,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:intervention', '2026-02-12', NULL, ?,
                      'unclear', 0, 0.5, 0.2,
                      NULL, 'intervention_metadata',
                      NULL, NULL,
                      'congreso_intervenciones', 'https://example.invalid', ?, '2026-02-12',
                      '{}', ?, ?
                    )
                    """,
                    (person_id, "Apoyamos esta iniciativa.", sr_pk_2, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO topic_evidence (
                      topic_id, topic_set_id,
                      person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      evidence_type, evidence_date, title, excerpt,
                      stance, polarity, weight, confidence,
                      topic_method, stance_method,
                      vote_event_id, initiative_id,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (
                      NULL, NULL,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:intervention', '2026-02-12', NULL, NULL,
                      'unclear', 0, 0.5, 0.2,
                      NULL, 'intervention_metadata',
                      NULL, NULL,
                      'congreso_intervenciones', 'https://example.invalid', ?, '2026-02-12',
                      '{}', ?, ?
                    )
                    """,
                    (person_id, sr_pk_3, now, now),
                )
                conn.commit()

                result1 = backfill_declared_stance_from_topic_evidence(
                    conn,
                    source_id="congreso_intervenciones",
                    limit=0,
                    min_auto_confidence=0.62,
                    dry_run=False,
                )
                self.assertEqual(int(result1.get("updated", 0)), 2)
                self.assertEqual(int(result1.get("review_pending", 0)), 1)

                row = conn.execute(
                    "SELECT stance, polarity, confidence, stance_method FROM topic_evidence WHERE source_record_pk = ?",
                    (sr_pk,),
                ).fetchone()
                self.assertEqual(row["stance"], "support")
                self.assertEqual(int(row["polarity"]), 1)
                self.assertGreater(float(row["confidence"]), 0.2)
                self.assertEqual(row["stance_method"], "declared:regex_v3")

                low_row = conn.execute(
                    "SELECT stance, polarity, confidence, stance_method FROM topic_evidence WHERE source_record_pk = ?",
                    (sr_pk_2,),
                ).fetchone()
                self.assertEqual(low_row["stance"], "support")
                self.assertEqual(int(low_row["polarity"]), 1)
                self.assertGreaterEqual(float(low_row["confidence"]), 0.62)
                self.assertEqual(low_row["stance_method"], "declared:regex_v3")

                review_rows = conn.execute(
                    """
                    SELECT source_record_pk, review_reason, status
                    FROM topic_evidence_reviews
                    ORDER BY source_record_pk ASC
                    """
                ).fetchall()
                self.assertEqual(len(review_rows), 1)
                self.assertEqual(str(review_rows[0]["review_reason"]), "missing_text")
                self.assertEqual(str(review_rows[0]["status"]), "pending")

                result2 = backfill_declared_stance_from_topic_evidence(
                    conn,
                    source_id="congreso_intervenciones",
                    limit=0,
                    min_auto_confidence=0.62,
                    dry_run=False,
                )
                self.assertEqual(int(result2.get("updated", 0)), 0)
                self.assertEqual(int(result2.get("review_pending", 0)), 1)
                self.assertEqual(
                    int(conn.execute("SELECT COUNT(*) AS c FROM topic_evidence_reviews").fetchone()["c"]),
                    1,
                )

                fk = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk, [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

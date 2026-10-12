#!/usr/bin/env python3
"""Ingest page-addressable claims from one verified, real manifesto PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "promises_public_sample_v1"
PIPELINE_VERSION = "manifesto_promises_v1"
SEGMENTATION_VERSION = "pdf_bullets_page_aware_v1"
TOPIC_CODEBOOK_VERSION = "promise_topics_es_gl_v1"
SOURCE_ID = "programas_partidos"
SOURCE_NAME = "Programas electorales de partidos"
BNG_SOURCE_URL = (
    "https://www.bng.gal/media/bnggaliza/files/2023/07/05/23_bng_xerais_programa.pdf"
)
BNG_SHA256 = "b8994deec0bbc45cdcbef5d7c5395cabf30b0509706303c3d8e76058c48eebfd"
BNG_BYTES = 396_842
BNG_PAGES = 68
BNG_PARTY_NAME = "Bloque Nacionalista Galego"
BNG_PARTY_ACRONYM = "BNG"
BNG_ACTOR_LABEL = "BNG"
BNG_TITLE = "Programa Electoral Eleccións Xerais 2023"
BNG_ELECTION_KEY = "es_generales_2023"

ACTION_PREFIXES = (
    "aplicar",
    "aprobar",
    "aumentar",
    "asunción",
    "blindar",
    "crear",
    "derrogación",
    "derrogar",
    "desenvolver",
    "elaborar",
    "elevar",
    "eliminar",
    "estabelecer",
    "establecer",
    "evitar",
    "fixar",
    "garantir",
    "implantar",
    "incorporar",
    "incrementar",
    "modificar",
    "mudar",
    "nacionalizar",
    "posta en marcha",
    "prohibir",
    "recuperar",
    "reclamar",
    "reducir",
    "reforzar",
    "reformular",
    "regular",
    "suprimir",
    "transferencia",
    "transferir",
    "traspaso",
    "traspasar",
)
SOFT_PREFIXES = (
    "avanzar",
    "defender",
    "fomentar",
    "favorecer",
    "impulsar",
    "promover",
    "procurar",
)
BINARY_ACTION_PREFIXES = (
    "aprobar",
    "crear",
    "derrog",
    "eliminar",
    "establecer",
    "estabelecer",
    "fixar",
    "implantar",
    "incorporar",
    "nacionalizar",
    "prohibir",
    "recuperar",
    "regular",
    "suprimir",
    "transfer",
    "traspas",
)

TOPIC_CODEBOOK: dict[str, tuple[str, tuple[str, ...]]] = {
    "institutional_autonomy": (
        "Autogobierno y organización territorial",
        (
            "competencia*",
            "autogoberno*",
            "soberanía*",
            "facenda galega",
            "concerto económico",
        ),
    ),
    "social_protection": (
        "Protección e inclusión social",
        (
            "protección social",
            "pobreza*",
            "exclusión social",
            "dependencia*",
            "servizos sociais",
            "renda galega",
        ),
    ),
    "housing": (
        "Vivienda",
        ("vivenda*", "aluguer*", "sareb", "solo*", "ibi"),
    ),
    "labour": (
        "Trabajo y relaciones laborales",
        (
            "labora*",
            "salario*",
            "emprego*",
            "despedimento*",
            "xornada*",
            "convenio*",
            "subcontratación*",
        ),
    ),
    "pensions": (
        "Pensiones y Seguridad Social",
        ("pensión*", "xubilación*", "seguridade social"),
    ),
    "public_finance": (
        "Fiscalidad y finanzas públicas",
        (
            "fiscalidade*",
            "política fiscal",
            "imposto*",
            "tribut*",
            "financiamento*",
            "orzamento*",
        ),
    ),
    "health": (
        "Sanidad",
        ("sanidade*", "sanitario*", "saúde*", "hospital*"),
    ),
    "education": (
        "Educación",
        ("educación*", "educativo*", "universidade*", "escola*"),
    ),
    "equality": (
        "Igualdad y no discriminación",
        ("igualdade*", "muller*", "lgbt*", "discapacidade*"),
    ),
    "democracy_rights": (
        "Democracia y derechos civiles",
        ("dereito*", "liberdade*", "democracia*", "mordaza", "memoria democrática"),
    ),
    "energy": (
        "Energía y transición energética",
        ("enerx*", "eléctric*", "eólic*", "tarifa*"),
    ),
    "transport": (
        "Transportes e infraestructuras",
        ("transporte*", "ferrocarr*", "estrada*", "ap-9", "porto*", "aeroporto*"),
    ),
    "environment": (
        "Medio ambiente y biodiversidad",
        ("ambient*", "biodivers*", "contamin*", "litoral*", "ría*"),
    ),
    "industry": (
        "Industria y tejido productivo",
        ("industr*", "empresa*", "sectores estratéxicos", "produción*"),
    ),
    "agriculture_fisheries": (
        "Agricultura, ganadería y pesca",
        ("agro*", "agraria*", "gand*", "pesca*", "marisque*", "forestal*"),
    ),
    "science_innovation": (
        "Ciencia, tecnología e innovación",
        ("ciencia*", "innovación*", "investigación*", "dixital*", "tecnolox*"),
    ),
    "language_culture": (
        "Lengua y cultura",
        (
            "lingua*",
            "lingüístic*",
            "normalización lingüística",
            "cultura*",
            "audiovisual*",
            "arquivo*",
        ),
    ),
    "youth": (
        "Juventud",
        ("mocidade*", "xuventude*", "xove*"),
    ),
    "sports": (
        "Deporte",
        ("deport*", "federacións deportivas", "competicións deportivas"),
    ),
    "foreign_policy_peace": (
        "Política exterior, paz y defensa",
        ("paz", "militar*", "otan", "sáhara", "internacional*", "arma*"),
    ),
}

SECTION_RANGES = (
    (3, 8, "0. Introdución"),
    (9, 13, "1. Soberanía política para garantir maior benestar social"),
    (14, 20, "2. Máis dereitos para unha maior xustiza social"),
    (21, 24, "3. Políticas feministas para avanzar nos dereitos das mulleres"),
    (25, 26, "4. A defensa dos dereitos das persoas LGBT"),
    (27, 30, "5. Na defensa da democracia e das liberdades públicas"),
    (31, 38, "6. Por uns servizos públicos de calidade"),
    (39, 47, "7. Economía ao servizo das maiorías sociais"),
    (48, 51, "8. Por unha transición enerxética xusta"),
    (52, 55, "9. Infraestruturas públicas e ordenación territorial"),
    (56, 59, "10. Pola protección do medio e a biodiversidade"),
    (60, 61, "11. Lingua e cultura"),
    (62, 64, "12. Políticas para a mocidade"),
    (65, 65, "13. Galiza na vangarda deportiva"),
    (66, 68, "14. Pola paz e a convivencia dos pobos"),
)


@dataclass(frozen=True)
class Segment:
    page: int
    ordinal: int
    exact_quote: str
    normalized_text: str
    char_start: int
    char_end: int
    section_path: str | None


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def section_for_page(page: int) -> str | None:
    for start, end, label in SECTION_RANGES:
        if start <= page <= end:
            return label
    return None


def extract_pages(pdf_path: Path) -> list[str]:
    completed = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        capture_output=True,
    )
    text = completed.stdout.decode("utf-8", errors="strict")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def build_segment(
    *,
    page_number: int,
    ordinal: int,
    current_lines: list[str],
    current_start: int,
) -> tuple[int, Segment | None]:
    if not current_lines:
        return ordinal, None
    exact_quote = "\n".join(current_lines).strip()
    normalized = re.sub(r"\s+", " ", exact_quote.lstrip("• ")).strip()
    if not normalized:
        return ordinal, None
    ordinal += 1
    return ordinal, Segment(
        page=page_number,
        ordinal=ordinal,
        exact_quote=exact_quote,
        normalized_text=normalized,
        char_start=current_start,
        char_end=current_start + len(exact_quote),
        section_path=section_for_page(page_number),
    )


def extract_bullet_segments(pages: list[str]) -> list[Segment]:
    segments: list[Segment] = []
    ordinal = 0
    bullet_re = re.compile(r"^\s*•\s+(.+?)\s*$")

    for page_number, page_text in enumerate(pages, start=1):
        lines = [line.strip() for line in page_text.splitlines()]
        canonical_page = "\n".join(lines)
        offsets: list[int] = []
        cursor = 0
        for line in lines:
            offsets.append(cursor)
            cursor += len(line) + 1

        current_lines: list[str] = []
        current_start = 0

        for line_number, line in enumerate(lines):
            match = bullet_re.match(line)
            if match:
                ordinal, segment = build_segment(
                    page_number=page_number,
                    ordinal=ordinal,
                    current_lines=current_lines,
                    current_start=current_start,
                )
                if segment:
                    segments.append(segment)
                current_start = offsets[line_number] + line.index("•")
                current_lines = [line[line.index("•") :]]
                continue
            if current_lines and not line:
                ordinal, segment = build_segment(
                    page_number=page_number,
                    ordinal=ordinal,
                    current_lines=current_lines,
                    current_start=current_start,
                )
                if segment:
                    segments.append(segment)
                current_lines = []
                continue
            if current_lines:
                current_lines.append(line)
        ordinal, segment = build_segment(
            page_number=page_number,
            ordinal=ordinal,
            current_lines=current_lines,
            current_start=current_start,
        )
        if segment:
            segments.append(segment)

        for segment in segments:
            if segment.page == page_number:
                assert (
                    canonical_page[segment.char_start : segment.char_end]
                    == segment.exact_quote
                )

    return segments


def classify_claim(text: str) -> tuple[str, str, float]:
    lowered = text.casefold()
    first_words = lowered[:80]
    action = next(
        (prefix for prefix in ACTION_PREFIXES if first_words.startswith(prefix)), None
    )
    if action and len(text) >= 35:
        return "explicit_promise", action, 0.98
    soft = next(
        (prefix for prefix in SOFT_PREFIXES if first_words.startswith(prefix)), None
    )
    if soft and len(text) >= 35:
        return "soft_commitment", soft, 0.86
    return "context", "", 0.55


def is_complete_segment(text: str) -> bool:
    lowered = text.casefold().rstrip()
    incomplete_endings = (
        " a",
        " ao",
        " as",
        " con",
        " da",
        " das",
        " de",
        " do",
        " dos",
        " e",
        " en",
        " na",
        " nas",
        " no",
        " nos",
        " o",
        " os",
        " para",
        " que",
        " un",
        " unha",
    )
    return not lowered.endswith(incomplete_endings) and not lowered.endswith(
        (",", ";", ":")
    )


def keyword_matches(text: str, term: str) -> bool:
    if term.endswith("*"):
        prefix = re.escape(term[:-1])
        pattern = rf"(?<!\w){prefix}\w*"
    else:
        pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    return re.search(pattern, text) is not None


def topic_matches(text: str) -> list[tuple[str, str, float]]:
    lowered = text.casefold()
    matches: list[tuple[str, str, float]] = []
    for key, (label, terms) in TOPIC_CODEBOOK.items():
        hit_count = sum(keyword_matches(lowered, term) for term in terms)
        if hit_count:
            confidence = min(0.99, 0.84 + (hit_count - 1) * 0.05)
            matches.append((key, label, confidence))
    return matches


def measurability(text: str, action: str) -> tuple[str, list[dict[str, str]]]:
    lowered = text.casefold()
    has_number = bool(
        re.search(r"\b\d+(?:[.,]\d+)?\s*(?:%|euros?|anos?|horas?)?\b", lowered)
    )
    has_binary_action = any(
        action.startswith(prefix) for prefix in BINARY_ACTION_PREFIXES
    )
    if has_number:
        state = "measurable"
        criterion_type = "numeric_or_deadline_in_source"
    elif has_binary_action:
        state = "measurable"
        criterion_type = "binary_action_in_source"
    else:
        state = "partially_measurable"
        criterion_type = "action_requires_operational_definition"
    return state, [{"criterion_type": criterion_type, "source_text": text}]


def verify_real_pdf(pdf_path: Path) -> tuple[bytes, str]:
    data = pdf_path.read_bytes()
    digest = sha256_bytes(data)
    errors: list[str] = []
    if not data.startswith(b"%PDF-"):
        errors.append("source is not a PDF payload")
    if digest != BNG_SHA256:
        errors.append(f"SHA-256 mismatch: expected {BNG_SHA256}, got {digest}")
    if len(data) != BNG_BYTES:
        errors.append(f"byte mismatch: expected {BNG_BYTES}, got {len(data)}")
    if errors:
        raise ValueError("; ".join(errors))
    return data, digest


def upsert_foundations(
    conn: sqlite3.Connection,
    *,
    pdf_path: Path,
    digest: str,
    text_sha256: str,
    text_chars: int,
    page_count: int,
    snapshot_date: str,
    observed_at: str,
) -> tuple[int, int, int, str]:
    conn.execute(
        """
        INSERT INTO sources (
          source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
        ) VALUES (?, ?, 'nacional', ?, 'pdf', 1, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
          name=excluded.name, default_url=excluded.default_url,
          data_format=excluded.data_format, is_active=1, updated_at=excluded.updated_at
        """,
        (SOURCE_ID, SOURCE_NAME, BNG_SOURCE_URL, observed_at, observed_at),
    )
    conn.execute(
        """
        INSERT INTO parties (name, acronym, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET acronym=excluded.acronym, updated_at=excluded.updated_at
        """,
        (BNG_PARTY_NAME, BNG_PARTY_ACRONYM, observed_at, observed_at),
    )
    party_id = int(
        conn.execute(
            "SELECT party_id FROM parties WHERE name = ?", (BNG_PARTY_NAME,)
        ).fetchone()[0]
    )

    source_record_id = f"manifesto:{digest}"
    raw_payload = canonical_json(
        {
            "actor": BNG_ACTOR_LABEL,
            "content_sha256": digest,
            "election_key": BNG_ELECTION_KEY,
            "official_public_domain_information_retained": True,
            "source_url": BNG_SOURCE_URL,
            "synthetic_or_mock": False,
            "title": BNG_TITLE,
        }
    )
    conn.execute(
        """
        INSERT INTO source_records (
          source_id, source_record_id, source_snapshot_date, raw_payload,
          content_sha256, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, source_record_id) DO UPDATE SET
          source_snapshot_date=excluded.source_snapshot_date,
          raw_payload=excluded.raw_payload,
          content_sha256=excluded.content_sha256,
          updated_at=excluded.updated_at
        """,
        (
            SOURCE_ID,
            source_record_id,
            snapshot_date,
            raw_payload,
            digest,
            observed_at,
            observed_at,
        ),
    )
    source_record_pk = int(
        conn.execute(
            "SELECT source_record_pk FROM source_records WHERE source_id=? AND source_record_id=?",
            (SOURCE_ID, source_record_id),
        ).fetchone()[0]
    )
    raw_path = pdf_path.as_posix()
    conn.execute(
        """
        INSERT INTO text_documents (
          source_id, source_url, source_record_pk, fetched_at, content_type,
          content_sha256, bytes, raw_path, text_excerpt, text_chars, text_path,
          text_sha256, text_extraction_method, text_extracted_at, text_truncated,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'application/pdf', ?, ?, ?, NULL, ?, NULL, ?,
                  'pdftotext-layout-page-aware', ?, 0, ?, ?)
        ON CONFLICT(source_record_pk) DO UPDATE SET
          source_url=excluded.source_url,
          content_sha256=excluded.content_sha256,
          bytes=excluded.bytes,
          raw_path=excluded.raw_path,
          text_chars=excluded.text_chars,
          text_sha256=excluded.text_sha256,
          text_extraction_method=excluded.text_extraction_method,
          text_extracted_at=excluded.text_extracted_at,
          text_truncated=0,
          updated_at=excluded.updated_at
        """,
        (
            SOURCE_ID,
            BNG_SOURCE_URL,
            source_record_pk,
            observed_at,
            digest,
            BNG_BYTES,
            raw_path,
            text_chars,
            text_sha256,
            observed_at,
            observed_at,
            observed_at,
        ),
    )
    text_document_id = int(
        conn.execute(
            "SELECT text_document_id FROM text_documents WHERE source_record_pk=?",
            (source_record_pk,),
        ).fetchone()[0]
    )
    document_payload = {
        "actor": BNG_PARTY_NAME,
        "content_sha256": digest,
        "election_key": BNG_ELECTION_KEY,
        "source_url": BNG_SOURCE_URL,
    }
    manifesto_document_id = stable_id("manifesto", document_payload)
    conn.execute(
        """
        INSERT INTO manifesto_documents (
          manifesto_document_id, text_document_id, source_record_pk, source_id,
          party_id, document_kind, title, election_key, jurisdiction, language,
          published_date, snapshot_date, source_url, content_sha256, bytes,
          page_count, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'manifesto', ?, ?, 'España / Galicia', 'gl',
          '2023-07-05', ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(manifesto_document_id) DO UPDATE SET
          text_document_id=excluded.text_document_id,
          source_record_pk=excluded.source_record_pk,
          party_id=excluded.party_id,
          snapshot_date=excluded.snapshot_date,
          page_count=excluded.page_count,
          updated_at=excluded.updated_at
        """,
        (
            manifesto_document_id,
            text_document_id,
            source_record_pk,
            SOURCE_ID,
            party_id,
            BNG_TITLE,
            BNG_ELECTION_KEY,
            snapshot_date,
            BNG_SOURCE_URL,
            digest,
            BNG_BYTES,
            page_count,
            observed_at,
            observed_at,
        ),
    )
    return party_id, source_record_pk, text_document_id, manifesto_document_id


def upsert_topics(conn: sqlite3.Connection, observed_at: str) -> dict[str, int]:
    topic_ids: dict[str, int] = {}
    conn.execute(
        """
        INSERT INTO topic_sets (name, description, created_at, updated_at)
        VALUES ('Promesas España/Galicia v1', ?, ?, ?)
        ON CONFLICT DO UPDATE SET description=excluded.description, updated_at=excluded.updated_at
        """,
        (
            "Taxonomía determinista v1 para claims de manifiestos; no contiene datos políticos.",
            observed_at,
            observed_at,
        ),
    )
    topic_set_id = int(
        conn.execute(
            "SELECT topic_set_id FROM topic_sets WHERE name='Promesas España/Galicia v1'"
        ).fetchone()[0]
    )
    for rank, (key, (label, _terms)) in enumerate(TOPIC_CODEBOOK.items(), start=1):
        canonical_key = f"promise.v1.{key}"
        conn.execute(
            """
            INSERT INTO topics (canonical_key, label, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(canonical_key) DO UPDATE SET
              label=excluded.label, description=excluded.description, updated_at=excluded.updated_at
            """,
            (
                canonical_key,
                label,
                f"Topic del codebook {TOPIC_CODEBOOK_VERSION}.",
                observed_at,
                observed_at,
            ),
        )
        topic_id = int(
            conn.execute(
                "SELECT topic_id FROM topics WHERE canonical_key=?", (canonical_key,)
            ).fetchone()[0]
        )
        topic_ids[key] = topic_id
        conn.execute(
            """
            INSERT INTO topic_set_topics (
              topic_set_id, topic_id, stakes_rank, is_high_stakes, notes,
              created_at, updated_at
            ) VALUES (?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(topic_set_id, topic_id) DO UPDATE SET
              stakes_rank=excluded.stakes_rank,
              is_high_stakes=excluded.is_high_stakes,
              notes=excluded.notes,
              updated_at=excluded.updated_at
            """,
            (
                topic_set_id,
                topic_id,
                rank,
                f"Asignación por {TOPIC_CODEBOOK_VERSION}.",
                observed_at,
                observed_at,
            ),
        )
    return topic_ids


def ingest_claims(
    conn: sqlite3.Connection,
    *,
    segments: list[Segment],
    party_id: int,
    text_document_id: int,
    manifesto_document_id: str,
    document_sha256: str,
    topic_ids: dict[str, int],
    observed_at: str,
    publish_limit: int,
) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
    config = {
        "action_prefixes": ACTION_PREFIXES,
        "publish_limit": publish_limit,
        "soft_prefixes": SOFT_PREFIXES,
        "source_sha256": document_sha256,
        "topic_codebook": TOPIC_CODEBOOK,
    }
    config_sha256 = sha256_bytes(canonical_json(config).encode("utf-8"))
    run_payload = {
        "config_sha256": config_sha256,
        "manifesto_document_id": manifesto_document_id,
        "pipeline_version": PIPELINE_VERSION,
        "segmentation_version": SEGMENTATION_VERSION,
        "topic_codebook_version": TOPIC_CODEBOOK_VERSION,
    }
    run_id = stable_id("claimrun", run_payload)
    conn.execute(
        """
        INSERT INTO claim_extraction_runs (
          claim_extraction_run_id, manifesto_document_id, pipeline_version,
          segmentation_version, topic_codebook_version, config_sha256,
          status, started_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?)
        ON CONFLICT(claim_extraction_run_id) DO UPDATE SET
          status='running', started_at=excluded.started_at, finished_at=NULL, message=NULL
        """,
        (
            run_id,
            manifesto_document_id,
            PIPELINE_VERSION,
            SEGMENTATION_VERSION,
            TOPIC_CODEBOOK_VERSION,
            config_sha256,
            observed_at,
        ),
    )

    public_candidates: list[dict[str, Any]] = []
    counts = {
        "segments_seen": len(segments),
        "claims_loaded": 0,
        "explicit_promises": 0,
        "promises_loaded": 0,
        "soft_commitments": 0,
        "pending_claims": 0,
        "needs_context_claims": 0,
        "topic_links": 0,
    }
    for segment in segments:
        kind, action, confidence = classify_claim(segment.normalized_text)
        complete = is_complete_segment(segment.normalized_text)
        review_status = (
            "rule_confirmed"
            if kind == "explicit_promise" and complete
            else "needs_context"
            if kind == "explicit_promise"
            else "pending"
        )
        review_method = (
            f"{PIPELINE_VERSION}:structured_bullet_action_prefix"
            if review_status == "rule_confirmed"
            else None
        )
        claim_payload = {
            "document": manifesto_document_id,
            "exact_quote": segment.exact_quote,
            "ordinal": segment.ordinal,
            "page_end": segment.page,
            "page_start": segment.page,
        }
        claim_id = stable_id("claim", claim_payload)
        conn.execute(
            """
            INSERT INTO claims (
              claim_id, manifesto_document_id, claim_extraction_run_id, party_id,
              attributed_actor_label, claim_kind, exact_text, normalized_text,
              language, page_start, page_end, section_path, document_ordinal,
              extraction_method, extraction_version, extraction_confidence,
              review_status, review_method, reviewed_at, claim_status,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'gl', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      'active', ?, ?)
            ON CONFLICT(claim_id) DO UPDATE SET
              claim_extraction_run_id=excluded.claim_extraction_run_id,
              claim_kind=excluded.claim_kind,
              normalized_text=excluded.normalized_text,
              extraction_confidence=excluded.extraction_confidence,
              review_status=excluded.review_status,
              review_method=excluded.review_method,
              reviewed_at=excluded.reviewed_at,
              updated_at=excluded.updated_at
            """,
            (
                claim_id,
                manifesto_document_id,
                run_id,
                party_id,
                BNG_ACTOR_LABEL,
                kind,
                segment.exact_quote,
                segment.normalized_text,
                segment.page,
                segment.page,
                segment.section_path,
                segment.ordinal,
                "pdftotext-layout-bullet",
                SEGMENTATION_VERSION,
                confidence,
                review_status,
                review_method,
                observed_at if review_status == "rule_confirmed" else None,
                observed_at,
                observed_at,
            ),
        )
        counts["claims_loaded"] += 1
        if kind == "explicit_promise":
            counts["explicit_promises"] += 1
        elif kind == "soft_commitment":
            counts["soft_commitments"] += 1
        if review_status == "pending":
            counts["pending_claims"] += 1
        elif review_status == "needs_context":
            counts["needs_context_claims"] += 1

        evidence_payload = {
            "claim_id": claim_id,
            "document_sha256": document_sha256,
            "page": segment.page,
            "quote_sha256": sha256_bytes(segment.exact_quote.encode("utf-8")),
            "role": "primary",
        }
        evidence_id = stable_id("claimevidence", evidence_payload)
        quote_sha256 = evidence_payload["quote_sha256"]
        conn.execute(
            """
            INSERT INTO claim_evidence (
              claim_evidence_id, claim_id, text_document_id, evidence_role,
              source_url, document_sha256, page_start, page_end, char_start,
              char_end, exact_quote, quote_sha256, extraction_method,
              created_at, updated_at
            ) VALUES (?, ?, ?, 'primary', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(claim_evidence_id) DO UPDATE SET
              char_start=excluded.char_start,
              char_end=excluded.char_end,
              exact_quote=excluded.exact_quote,
              quote_sha256=excluded.quote_sha256,
              updated_at=excluded.updated_at
            """,
            (
                evidence_id,
                claim_id,
                text_document_id,
                BNG_SOURCE_URL,
                document_sha256,
                segment.page,
                segment.page,
                segment.char_start,
                segment.char_end,
                segment.exact_quote,
                quote_sha256,
                "pdftotext-layout-page-canonical-lines",
                observed_at,
                observed_at,
            ),
        )

        topics: list[dict[str, Any]] = []
        conn.execute(
            """
            DELETE FROM claim_topics
            WHERE claim_id=? AND assignment_method='keyword_multilabel'
              AND assignment_version=?
            """,
            (claim_id, TOPIC_CODEBOOK_VERSION),
        )
        for topic_key, topic_label, topic_confidence in topic_matches(
            segment.normalized_text
        ):
            topic_id = topic_ids[topic_key]
            conn.execute(
                """
                INSERT INTO claim_topics (
                  claim_id, topic_id, assignment_method, assignment_version,
                  confidence, review_status, created_at, updated_at
                ) VALUES (?, ?, 'keyword_multilabel', ?, ?, 'rule_assigned', ?, ?)
                ON CONFLICT(claim_id, topic_id, assignment_method, assignment_version)
                DO UPDATE SET confidence=excluded.confidence, updated_at=excluded.updated_at
                """,
                (
                    claim_id,
                    topic_id,
                    TOPIC_CODEBOOK_VERSION,
                    topic_confidence,
                    observed_at,
                    observed_at,
                ),
            )
            counts["topic_links"] += 1
            topics.append(
                {
                    "assignment_method": "keyword_multilabel",
                    "assignment_version": TOPIC_CODEBOOK_VERSION,
                    "canonical_key": f"promise.v1.{topic_key}",
                    "confidence": topic_confidence,
                    "label": topic_label,
                }
            )

        if kind != "explicit_promise" or review_status != "rule_confirmed":
            conn.execute("DELETE FROM promises WHERE claim_id=?", (claim_id,))
            continue
        measure_state, criteria = measurability(segment.normalized_text, action)
        promise_id = stable_id("promise", {"claim_id": claim_id})
        conn.execute(
            """
            INSERT INTO promises (
              promise_id, claim_id, commitment_strength, action_text, object_text,
              target_territory, measurability_state, measurable_criteria_json,
              observation_status, created_at, updated_at
            ) VALUES (?, ?, 'explicit', ?, ?, 'Galicia', ?, ?, 'not_assessed', ?, ?)
            ON CONFLICT(promise_id) DO UPDATE SET
              action_text=excluded.action_text,
              object_text=excluded.object_text,
              measurability_state=excluded.measurability_state,
              measurable_criteria_json=excluded.measurable_criteria_json,
              updated_at=excluded.updated_at
            """,
            (
                promise_id,
                claim_id,
                action,
                segment.normalized_text,
                measure_state,
                canonical_json(criteria),
                observed_at,
                observed_at,
            ),
        )
        counts["promises_loaded"] += 1
        if topics and len(public_candidates) < publish_limit:
            public_candidates.append(
                {
                    "actor": {
                        "actor_kind": "party",
                        "acronym": BNG_PARTY_ACRONYM,
                        "name": BNG_PARTY_NAME,
                        "source_label": BNG_ACTOR_LABEL,
                    },
                    "claim_id": claim_id,
                    "claim_kind": kind,
                    "commitment_strength": "explicit",
                    "evidence": {
                        "claim_evidence_id": evidence_id,
                        "char_end": segment.char_end,
                        "char_start": segment.char_start,
                        "document_sha256": document_sha256,
                        "exact_quote": segment.exact_quote,
                        "page_end": segment.page,
                        "page_start": segment.page,
                        "quote_sha256": quote_sha256,
                        "source_url": BNG_SOURCE_URL,
                    },
                    "extraction": {
                        "confidence": confidence,
                        "method": "pdftotext-layout-bullet",
                        "version": SEGMENTATION_VERSION,
                    },
                    "measurability": {
                        "criteria": criteria,
                        "state": measure_state,
                    },
                    "normalized_text": segment.normalized_text,
                    "observation_status": "not_assessed",
                    "promise_id": promise_id,
                    "review": {
                        "method": review_method,
                        "status": review_status,
                    },
                    "section_path": segment.section_path,
                    "topics": topics,
                }
            )

    conn.execute(
        """
        UPDATE claim_extraction_runs
        SET status='ok', finished_at=?, pages_seen=?, segments_seen=?, claims_loaded=?,
            promises_loaded=?, publishable_claims=?, message=?
        WHERE claim_extraction_run_id=?
        """,
        (
            observed_at,
            BNG_PAGES,
            counts["segments_seen"],
            counts["claims_loaded"],
            counts["promises_loaded"],
            len(public_candidates),
            "Real official BNG manifesto; rule-confirmed sample only.",
            run_id,
        ),
    )
    return run_id, public_candidates, counts


def build_public_payload(
    *,
    manifesto_document_id: str,
    run_id: str,
    items: list[dict[str, Any]],
    counts: dict[str, int],
    observed_at: str,
) -> dict[str, Any]:
    content_payload = {
        "manifesto_document_id": manifesto_document_id,
        "run_id": run_id,
        "items": items,
    }
    release_id = sha256_bytes(canonical_json(content_payload).encode("utf-8"))
    return {
        "schema_version": SCHEMA_VERSION,
        "release_id": release_id,
        "generated_at": observed_at,
        "real_data_only": True,
        "synthetic_or_mock": False,
        "public_domain_information_policy": "retained_exactly",
        "source": {
            "bytes": BNG_BYTES,
            "content_sha256": BNG_SHA256,
            "document_kind": "manifesto",
            "election_key": BNG_ELECTION_KEY,
            "language": "gl",
            "manifesto_document_id": manifesto_document_id,
            "page_count": BNG_PAGES,
            "source_id": SOURCE_ID,
            "source_url": BNG_SOURCE_URL,
            "title": BNG_TITLE,
        },
        "methodology": {
            "ambiguity_policy": "unconfirmed rows remain internal and are not published",
            "pipeline_version": PIPELINE_VERSION,
            "review_policy": "rule-confirmed structured bullets with explicit action prefixes",
            "segmentation_version": SEGMENTATION_VERSION,
            "spec_path": "docs/data-model/promises-spec-v1.md",
            "topic_codebook_version": TOPIC_CODEBOOK_VERSION,
        },
        "counts": {**counts, "published_promises": len(items)},
        "items": items,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path(
            f"etl/data/raw/text_documents/programas_partidos/{BNG_SHA256}.pdf"
        ),
    )
    parser.add_argument(
        "--db", type=Path, default=Path("etl/data/staging/promises-bng-2023.db")
    )
    parser.add_argument(
        "--schema", type=Path, default=Path("etl/load/sqlite_schema.sql")
    )
    parser.add_argument("--snapshot-date", default="2026-08-19")
    parser.add_argument("--observed-at", default="2026-08-19T20:00:00Z")
    parser.add_argument("--publish-limit", type=int, default=20)
    parser.add_argument(
        "--published-out",
        type=Path,
        default=Path("etl/data/published/promises-bng-2023.json"),
    )
    parser.add_argument(
        "--public-out",
        type=Path,
        default=Path("ui/site/public/promises/data/bng-2023.json"),
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=Path(
            "docs/etl/sprints/PROMISES-20260819/evidence/promises-bng-2023-ingest.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.publish_limit < 1 or args.publish_limit > 100:
        raise SystemExit("--publish-limit must be between 1 and 100")
    _raw_bytes, digest = verify_real_pdf(args.pdf)
    pages = extract_pages(args.pdf)
    if len(pages) != BNG_PAGES:
        raise SystemExit(f"page count mismatch: expected {BNG_PAGES}, got {len(pages)}")
    full_text = "\f".join(pages)
    text_sha256 = sha256_bytes(full_text.encode("utf-8"))
    segments = extract_bullet_segments(pages)
    if not segments:
        raise SystemExit("no real manifesto bullet segments extracted")

    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(args.schema.read_text(encoding="utf-8"))
        party_id, source_record_pk, text_document_id, document_id = upsert_foundations(
            conn,
            pdf_path=args.pdf,
            digest=digest,
            text_sha256=text_sha256,
            text_chars=len(full_text),
            page_count=len(pages),
            snapshot_date=args.snapshot_date,
            observed_at=args.observed_at,
        )
        topic_ids = upsert_topics(conn, args.observed_at)
        run_id, items, counts = ingest_claims(
            conn,
            segments=segments,
            party_id=party_id,
            text_document_id=text_document_id,
            manifesto_document_id=document_id,
            document_sha256=digest,
            topic_ids=topic_ids,
            observed_at=args.observed_at,
            publish_limit=args.publish_limit,
        )
        foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise RuntimeError(f"foreign key errors: {foreign_key_errors[:5]}")
        conn.commit()
    finally:
        conn.close()

    payload = build_public_payload(
        manifesto_document_id=document_id,
        run_id=run_id,
        items=items,
        counts=counts,
        observed_at=args.observed_at,
    )
    write_json(args.published_out, payload)
    write_json(args.public_out, payload)
    report = {
        "schema_version": "manifesto_promises_ingest_report_v1",
        "status": "ok",
        "db_path": args.db.as_posix(),
        "published_out": args.published_out.as_posix(),
        "public_out": args.public_out.as_posix(),
        "source": payload["source"],
        "run_id": run_id,
        "release_id": payload["release_id"],
        "party_id": party_id,
        "source_record_pk": source_record_pk,
        "text_document_id": text_document_id,
        "text_sha256": text_sha256,
        "text_chars": len(full_text),
        "counts": payload["counts"],
        "foreign_key_errors": 0,
        "real_data_only": True,
        "synthetic_or_mock": False,
        "official_public_domain_information_retained": True,
    }
    write_json(args.report_out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

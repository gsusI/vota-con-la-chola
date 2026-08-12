"""Bounded parser for Infoelectoral fixed-width candidate archives."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterator
from zipfile import BadZipFile, ZipFile, ZipInfo

from publicdata_core.util import normalize_ws


SOURCE_ID = "infoelectoral_candidates"
DEFAULT_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_MAX_MEMBERS = 256
DEFAULT_MAX_CANDIDATE_ROWS = 1_000_000
DEFAULT_MAX_PARTY_ROWS = 100_000
DEFAULT_MAX_COMPRESSION_RATIO = 250.0
_CANDIDATE_MEMBER = re.compile(r"(?:^|/)04([0-9]{6})\.DAT$", re.IGNORECASE)
_PARTY_MEMBER = re.compile(r"(?:^|/)03([0-9]{6})\.DAT$", re.IGNORECASE)


@dataclass(frozen=True)
class CandidateArchiveSpec:
    archive_id: str
    source_url: str
    election_date: str
    election_type_code: str
    election_id: str


@dataclass(frozen=True)
class CandidateRecord:
    candidate_occurrence_id: str
    source_record_id: str
    archive_id: str
    election_date: str
    election_type_code: str
    election_year: int
    election_month: int
    election_round: str
    province_code: str
    district_code: str
    candidate_scope_code: str
    party_source_code: str
    candidate_order: int
    candidate_type_code: str
    given_name: str
    surname_1: str
    surname_2: str | None
    full_name: str
    gender_code: str | None
    birth_date: str | None
    birth_date_source: str | None
    dni: str | None
    is_elected: int
    candidacy_name: str
    candidacy_acronym: str | None
    party_province_code: str | None
    party_autonomy_code: str | None
    party_national_code: str | None
    source_url: str
    source_content_sha256: str
    source_member_name: str
    source_line_number: int

    def public_source_payload(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=True, sort_keys=True)


@dataclass
class CandidateArchiveMetrics:
    party_rows: int = 0
    candidate_rows: int = 0


@dataclass(frozen=True)
class _PartyRecord:
    source_code: str
    acronym: str | None
    name: str
    province_code: str | None
    autonomy_code: str | None
    national_code: str | None


def _clean(value: str) -> str:
    return normalize_ws(value.replace('"', ""))


def _optional(value: str) -> str | None:
    token = _clean(value)
    return token or None


def _birth_date(value: str) -> tuple[str | None, str | None]:
    source = _optional(value)
    if source is None:
        return None, None
    if len(source) == 8 and source.isdigit():
        try:
            return datetime.strptime(source, "%d%m%Y").date().isoformat(), source
        except ValueError:
            pass
    return source, source


def _required_integer(value: str, *, field: str, line_number: int) -> int:
    token = value.strip()
    if not token.isdigit():
        raise RuntimeError(
            f"candidate DAT invalid {field} at line {line_number}: {value!r}"
        )
    return int(token)


def _safe_members(
    archive: ZipFile,
    *,
    max_members: int,
    max_uncompressed_bytes: int,
    max_compression_ratio: float,
) -> tuple[ZipInfo, ZipInfo]:
    infos = archive.infolist()
    if not infos or len(infos) > int(max_members):
        raise RuntimeError("candidate ZIP member count outside bounded contract")
    seen: set[str] = set()
    total_uncompressed = 0
    candidate_members: list[ZipInfo] = []
    party_members: list[ZipInfo] = []
    for info in infos:
        member_path = PurePosixPath(info.filename)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise RuntimeError("candidate ZIP contains unsafe member path")
        if info.filename in seen:
            raise RuntimeError("candidate ZIP contains duplicate member path")
        seen.add(info.filename)
        total_uncompressed += int(info.file_size)
        if total_uncompressed > int(max_uncompressed_bytes):
            raise RuntimeError("candidate ZIP exceeds uncompressed-byte contract")
        if info.file_size > 0:
            if info.compress_size <= 0:
                raise RuntimeError("candidate ZIP member has invalid compressed size")
            ratio = float(info.file_size) / float(info.compress_size)
            if ratio > float(max_compression_ratio):
                raise RuntimeError("candidate ZIP member exceeds compression-ratio contract")
        if _CANDIDATE_MEMBER.search(info.filename):
            candidate_members.append(info)
        if _PARTY_MEMBER.search(info.filename):
            party_members.append(info)
    if len(candidate_members) != 1 or len(party_members) != 1:
        raise RuntimeError(
            "candidate ZIP requires exactly one 04*.DAT and one 03*.DAT member"
        )
    candidate_suffix = _CANDIDATE_MEMBER.search(candidate_members[0].filename)
    party_suffix = _PARTY_MEMBER.search(party_members[0].filename)
    if candidate_suffix is None or party_suffix is None:
        raise RuntimeError("candidate ZIP member contract resolution failed")
    if candidate_suffix.group(1) != party_suffix.group(1):
        raise RuntimeError("candidate and party DAT election codes do not match")
    return candidate_members[0], party_members[0]


def _fixed_width_lines(
    handle: BinaryIO,
    *,
    width: int,
    max_rows: int,
    member_name: str,
) -> Iterator[tuple[int, str]]:
    rows = 0
    for line_number, raw_line in enumerate(handle, start=1):
        if len(raw_line) > width + 2:
            raise RuntimeError(
                f"{member_name} line {line_number} exceeds fixed-width contract"
            )
        raw = raw_line.rstrip(b"\r\n")
        if not raw:
            continue
        if len(raw) != width:
            raise RuntimeError(
                f"{member_name} line {line_number} has width {len(raw)}, expected {width}"
            )
        rows += 1
        if rows > int(max_rows):
            raise RuntimeError(f"{member_name} exceeds row contract")
        yield line_number, raw.decode("iso-8859-1")


def _party_records(
    archive: ZipFile,
    member: ZipInfo,
    *,
    max_rows: int,
) -> tuple[dict[str, _PartyRecord], int]:
    parties: dict[str, _PartyRecord] = {}
    rows = 0
    with archive.open(member) as handle:
        for line_number, line in _fixed_width_lines(
            handle,
            width=232,
            max_rows=max_rows,
            member_name=member.filename,
        ):
            rows += 1
            source_code = line[8:14].strip()
            name = _clean(line[64:214])
            if not source_code or not name:
                raise RuntimeError(
                    f"party DAT missing identity at line {line_number}"
                )
            record = _PartyRecord(
                source_code=source_code,
                acronym=_optional(line[14:64]),
                name=name,
                province_code=_optional(line[214:220]),
                autonomy_code=_optional(line[220:226]),
                national_code=_optional(line[226:232]),
            )
            existing = parties.get(source_code)
            if existing is not None and existing != record:
                raise RuntimeError(f"conflicting party code in DAT: {source_code}")
            parties[source_code] = record
    if not parties:
        raise RuntimeError("party DAT contains no records")
    return parties, rows


def _identity(parts: tuple[object, ...]) -> str:
    encoded = json.dumps(parts, ensure_ascii=True, separators=(",", ":"))
    return "infoelectoral-candidate:" + hashlib.sha256(
        encoded.encode("utf-8")
    ).hexdigest()


def _candidate_record(
    line: str,
    *,
    line_number: int,
    member_name: str,
    spec: CandidateArchiveSpec,
    source_content_sha256: str,
    parties: dict[str, _PartyRecord],
) -> CandidateRecord:
    election_type = line[0:2]
    year = _required_integer(line[2:6], field="year", line_number=line_number)
    month = _required_integer(line[6:8], field="month", line_number=line_number)
    order = _required_integer(
        line[21:24], field="candidate_order", line_number=line_number
    )
    if not 1 <= month <= 12 or election_type != spec.election_type_code:
        raise RuntimeError(f"candidate DAT election contract mismatch at line {line_number}")
    party_code = line[15:21].strip()
    party = parties.get(party_code)
    if party is None:
        raise RuntimeError(
            f"candidate DAT references unknown party {party_code!r} at line {line_number}"
        )
    given_name = _clean(line[25:50])
    surname_1 = _clean(line[50:75])
    surname_2 = _optional(line[75:100])
    if not given_name or not surname_1:
        raise RuntimeError(f"candidate DAT missing name at line {line_number}")
    full_name = " ".join(
        value for value in (given_name, surname_1, surname_2) if value
    )
    province_code = line[9:11].strip()
    district_code = line[11:12].strip()
    candidate_scope_code = line[12:15].strip()
    candidate_type = line[24:25].strip()
    occurrence_id = _identity(
        (
            election_type,
            year,
            month,
            line[8:9].strip(),
            province_code,
            district_code,
            candidate_scope_code,
            party_code,
            order,
            candidate_type,
        )
    )
    elected_code = line[119:120].strip().upper()
    birth_date, birth_date_source = _birth_date(line[101:109])
    return CandidateRecord(
        candidate_occurrence_id=occurrence_id,
        source_record_id=occurrence_id,
        archive_id=spec.archive_id,
        election_date=spec.election_date,
        election_type_code=election_type,
        election_year=year,
        election_month=month,
        election_round=line[8:9].strip(),
        province_code=province_code,
        district_code=district_code,
        candidate_scope_code=candidate_scope_code,
        party_source_code=party_code,
        candidate_order=order,
        candidate_type_code=candidate_type,
        given_name=given_name,
        surname_1=surname_1,
        surname_2=surname_2,
        full_name=full_name,
        gender_code=_optional(line[100:101]),
        birth_date=birth_date,
        birth_date_source=birth_date_source,
        dni=_optional(line[109:119]),
        is_elected=1 if elected_code in {"S", "1", "Y"} else 0,
        candidacy_name=party.name,
        candidacy_acronym=party.acronym,
        party_province_code=party.province_code,
        party_autonomy_code=party.autonomy_code,
        party_national_code=party.national_code,
        source_url=spec.source_url,
        source_content_sha256=source_content_sha256,
        source_member_name=member_name,
        source_line_number=line_number,
    )


def iter_candidate_archive(
    path: Path,
    *,
    spec: CandidateArchiveSpec,
    source_content_sha256: str,
    max_archive_bytes: int = DEFAULT_MAX_ARCHIVE_BYTES,
    max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
    max_members: int = DEFAULT_MAX_MEMBERS,
    max_candidate_rows: int = DEFAULT_MAX_CANDIDATE_ROWS,
    max_party_rows: int = DEFAULT_MAX_PARTY_ROWS,
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
    metrics: CandidateArchiveMetrics | None = None,
) -> Iterator[CandidateRecord]:
    archive_path = Path(path)
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    if archive_path.stat().st_size > int(max_archive_bytes):
        raise RuntimeError("candidate archive exceeds byte contract")
    try:
        with ZipFile(archive_path) as archive:
            candidate_member, party_member = _safe_members(
                archive,
                max_members=max_members,
                max_uncompressed_bytes=max_uncompressed_bytes,
                max_compression_ratio=max_compression_ratio,
            )
            parties, party_rows = _party_records(
                archive,
                party_member,
                max_rows=max_party_rows,
            )
            if metrics is not None:
                metrics.party_rows = party_rows
                metrics.candidate_rows = 0
            seen: set[str] = set()
            with archive.open(candidate_member) as handle:
                for line_number, line in _fixed_width_lines(
                    handle,
                    width=120,
                    max_rows=max_candidate_rows,
                    member_name=candidate_member.filename,
                ):
                    record = _candidate_record(
                        line,
                        line_number=line_number,
                        member_name=candidate_member.filename,
                        spec=spec,
                        source_content_sha256=source_content_sha256,
                        parties=parties,
                    )
                    if record.candidate_occurrence_id in seen:
                        raise RuntimeError(
                            "duplicate candidate occurrence identity in archive"
                        )
                    seen.add(record.candidate_occurrence_id)
                    if metrics is not None:
                        metrics.candidate_rows += 1
                    yield record
            if not seen:
                raise RuntimeError("candidate DAT contains no records")
    except BadZipFile as exc:
        raise RuntimeError("invalid candidate ZIP archive") from exc


__all__ = [
    "CandidateArchiveSpec",
    "CandidateArchiveMetrics",
    "CandidateRecord",
    "DEFAULT_MAX_ARCHIVE_BYTES",
    "DEFAULT_MAX_CANDIDATE_ROWS",
    "DEFAULT_MAX_COMPRESSION_RATIO",
    "DEFAULT_MAX_MEMBERS",
    "DEFAULT_MAX_PARTY_ROWS",
    "DEFAULT_MAX_UNCOMPRESSED_BYTES",
    "SOURCE_ID",
    "iter_candidate_archive",
]

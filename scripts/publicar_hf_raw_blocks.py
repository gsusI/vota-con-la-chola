#!/usr/bin/env python3
"""Publica archivos raw en Hugging Face, empaquetados en bloques."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RAW_DIR = Path("etl/data/raw")
DEFAULT_ENV_FILE = Path(".env")
DEFAULT_DATASET_NAME = "vota-con-la-chola-raw"
DEFAULT_SOURCE_REPO_URL = "https://github.com/gsusI/vota-con-la-chola"
PLACEHOLDER_VALUES = {"", "your_hf_token_here", "your_hf_username_here"}
DEFAULT_EXCLUDE_GLOBS = (
    "**/.DS_Store",
    "**/.gitkeep",
    "**/.headful-profile/**",
    "**/*_profile/**",
    "**/profile/**",
    "**/Cookies",
    "**/Cookies-journal",
    "**/Login Data",
    "**/Login Data*",
    "**/Web Data",
    "**/History",
    "**/History*",
    "**/Local Storage/**",
    "**/Session Storage/**",
    "**/Code Cache/**",
    "**/*cookie*.json",
    "**/*storage*.json",
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_iso_date(value: str) -> str:
    cleaned = value.strip()
    try:
        datetime.strptime(cleaned, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"snapshot-date invalido: {cleaned!r}") from exc
    return cleaned


def ensure_positive(value: int, flag_name: str) -> int:
    if value <= 0:
        raise ValueError(f"{flag_name} debe ser > 0")
    return value


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


def resolve_setting(key: str, cli_value: str, dotenv_values: dict[str, str]) -> str:
    if cli_value.strip():
        return cli_value.strip()
    env_value = os.environ.get(key, "").strip()
    if env_value:
        return env_value
    return dotenv_values.get(key, "").strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_csv_list(raw_value: str) -> list[str]:
    values: list[str] = []
    for piece in raw_value.replace("\n", ",").split(","):
        value = piece.strip()
        if value:
            values.append(value)
    return values


def should_exclude(rel_path: Path, *, include_manual: bool, exclude_globs: list[str]) -> bool:
    rel = rel_path.as_posix()
    if not include_manual and rel_path.parts and rel_path.parts[0] == "manual":
        return True
    for pattern in exclude_globs:
        if fnmatch.fnmatch(rel, pattern):
            return True
    return False


def collect_raw_files(
    raw_dir: Path,
    *,
    include_manual: bool,
    exclude_globs: list[str],
    max_files: int,
) -> list[Path]:
    files: list[Path] = []
    for path in raw_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(raw_dir)
        if should_exclude(rel, include_manual=include_manual, exclude_globs=exclude_globs):
            continue
        files.append(path)
    files.sort(key=lambda p: p.relative_to(raw_dir).as_posix())
    if max_files > 0:
        return files[:max_files]
    return files


def chunk_paths(paths: list[Path], block_size: int) -> list[list[Path]]:
    out: list[list[Path]] = []
    for idx in range(0, len(paths), block_size):
        out.append(paths[idx : idx + block_size])
    return out


def write_checksums(snapshot_dir: Path, relative_paths: list[Path]) -> None:
    out_path = snapshot_dir / "checksums.sha256"
    lines = []
    for rel in sorted(relative_paths):
        digest = sha256_file(snapshot_dir / rel)
        lines.append(f"{digest}  {rel.as_posix()}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_block_archive(
    *,
    raw_dir: Path,
    block_files: list[Path],
    block_tar_path: Path,
    block_manifest_path: Path,
    gzip_level: int,
) -> dict[str, Any]:
    block_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    block_tar_path.parent.mkdir(parents=True, exist_ok=True)

    files_total_bytes = 0
    first_path = ""
    last_path = ""
    with block_manifest_path.open("w", encoding="utf-8", newline="\n") as mfh:
        with tarfile.open(block_tar_path, mode="w:gz", compresslevel=gzip_level, format=tarfile.PAX_FORMAT) as tf:
            for idx, abs_path in enumerate(block_files):
                rel = abs_path.relative_to(raw_dir).as_posix()
                st = abs_path.stat()
                entry = {
                    "path": rel,
                    "bytes": int(st.st_size),
                    "sha256": sha256_file(abs_path),
                    "mtime_unix": int(st.st_mtime),
                }
                mfh.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")
                tf.add(str(abs_path), arcname=rel, recursive=False)
                files_total_bytes += int(st.st_size)
                if idx == 0:
                    first_path = rel
                last_path = rel

    return {
        "files_count": len(block_files),
        "files_bytes_total": files_total_bytes,
        "first_path": first_path,
        "last_path": last_path,
        "archive_bytes": int(block_tar_path.stat().st_size),
        "archive_sha256": sha256_file(block_tar_path),
        "manifest_bytes": int(block_manifest_path.stat().st_size),
        "manifest_sha256": sha256_file(block_manifest_path),
    }


def build_dataset_readme(
    *,
    dataset_repo: str,
    source_repo_url: str,
    snapshot_date: str,
    snapshot_rel_dir: Path,
    blocks: list[dict[str, Any]],
    include_manual: bool,
    exclude_globs: list[str],
    max_files_per_block: int,
) -> str:
    lines = [
        "---",
        "language:",
        "- es",
        "license: other",
        "task_categories:",
        "- other",
        "pretty_name: Vota Con La Chola raw blocks",
        "---",
        "",
        "# Vota Con La Chola - Raw Blocks",
        "",
        f"Dataset raw del proyecto `{dataset_repo}`.",
        "",
        f"Repositorio fuente: [{source_repo_url}]({source_repo_url})",
        "",
        "Contrato de empaquetado:",
        f"- Bloques `tar.gz` con hasta `{max_files_per_block}` ficheros por bloque.",
        "- Cada bloque incluye un `.manifest.jsonl` con `path`, `bytes`, `sha256` y `mtime_unix` por archivo.",
        "- Se publica `raw_blocks_index.json` con resumen y checksums de bloques.",
        "",
        "Ruta del snapshot publicado:",
        f"- `{snapshot_rel_dir.as_posix()}` (snapshot_date={snapshot_date})",
        "",
        "Archivos por snapshot:",
        f"- `{snapshot_rel_dir.as_posix()}/raw_blocks/block-*.tar.gz`",
        f"- `{snapshot_rel_dir.as_posix()}/raw_blocks/block-*.manifest.jsonl`",
        f"- `{snapshot_rel_dir.as_posix()}/raw_blocks_index.json`",
        f"- `{snapshot_rel_dir.as_posix()}/manifest.json`",
        f"- `{snapshot_rel_dir.as_posix()}/checksums.sha256`",
        "",
        "Privacidad y exclusiones:",
        f"- `include_manual={str(include_manual).lower()}`",
        "- Excluidos por defecto patrones sensibles de perfiles/cookies/storage de navegador.",
        "- Este dataset no implica respaldo institucional de las fuentes.",
        "",
        "Patrones de exclusión activos:",
    ]
    for pattern in exclude_globs:
        lines.append(f"- `{pattern}`")
    lines.extend(
        [
            "",
            f"Bloques en este snapshot: {len(blocks)}",
            "",
            "Actualización:",
            "- `just etl-publish-hf-raw-dry-run` para validar empaquetado.",
            "- `just etl-publish-hf-raw` para publicar actualización.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Publicar archivos raw en bloques a Hugging Face Datasets")
    p.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR), help="Directorio raw de entrada")
    p.add_argument("--snapshot-date", required=True, help="Fecha ISO YYYY-MM-DD del snapshot")
    p.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Archivo .env con credenciales")
    p.add_argument("--dataset-repo", default="", help="Repo HF dataset (owner/name)")
    p.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME, help="Nombre default de repo si no se define dataset-repo")
    p.add_argument("--hf-token", default="", help="Token HF (override)")
    p.add_argument("--hf-username", default="", help="Usuario HF (override)")
    p.add_argument("--source-repo-url", default="", help="URL del repo fuente")
    p.add_argument("--snapshot-prefix", default="snapshots", help="Prefijo de snapshot remoto")
    p.add_argument("--blocks-prefix", default="raw_blocks", help="Directorio de bloques dentro del snapshot")
    p.add_argument("--max-files-per-block", type=int, default=10_000, help="Max de ficheros por bloque")
    p.add_argument("--gzip-level", type=int, default=6, help="Nivel gzip (0-9)")
    p.add_argument("--include-manual", action="store_true", help="Incluye etl/data/raw/manual (no recomendado en público)")
    p.add_argument(
        "--exclude-globs",
        default=",".join(DEFAULT_EXCLUDE_GLOBS),
        help="Patrones glob separados por coma a excluir (relativos a raw-dir)",
    )
    p.add_argument("--max-files", type=int, default=0, help="Limitar total de archivos (0 = sin límite)")
    p.add_argument("--max-blocks", type=int, default=0, help="Limitar bloques construidos (0 = sin límite)")
    p.add_argument("--private", action="store_true", help="Crear repo privado si no existe")
    p.add_argument("--dry-run", action="store_true", help="Arma y valida sin subir")
    p.add_argument("--keep-temp", action="store_true", help="Conservar carpeta temporal")
    p.add_argument("--allow-empty", action="store_true", help="Permitir snapshot vacío")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        snapshot_date = ensure_iso_date(args.snapshot_date)
        ensure_positive(int(args.max_files_per_block), "--max-files-per-block")
        if int(args.gzip_level) < 0 or int(args.gzip_level) > 9:
            raise ValueError("--gzip-level debe estar en rango 0..9")
        if int(args.max_files) < 0:
            raise ValueError("--max-files debe ser >= 0")
        if int(args.max_blocks) < 0:
            raise ValueError("--max-blocks debe ser >= 0")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    raw_dir = Path(args.raw_dir)
    if not raw_dir.exists() or not raw_dir.is_dir():
        print(f"ERROR: raw-dir no existe o no es directorio: {raw_dir}", file=sys.stderr)
        return 2

    dotenv_values = load_dotenv(Path(args.env_file))
    hf_token = resolve_setting("HF_TOKEN", args.hf_token, dotenv_values)
    hf_username = resolve_setting("HF_USERNAME", args.hf_username, dotenv_values)
    dataset_repo = resolve_setting("HF_RAW_DATASET_REPO_ID", args.dataset_repo, dotenv_values)
    if not dataset_repo:
        dataset_repo = resolve_setting("HF_DATASET_REPO_ID", "", dotenv_values)
    source_repo_url = resolve_setting("SOURCE_REPO_URL", args.source_repo_url, dotenv_values) or DEFAULT_SOURCE_REPO_URL

    if not dataset_repo:
        if hf_username in PLACEHOLDER_VALUES:
            if args.dry_run:
                dataset_repo = f"local/{args.dataset_name}"
            else:
                print("ERROR: define HF_RAW_DATASET_REPO_ID o HF_USERNAME válido", file=sys.stderr)
                return 2
        else:
            dataset_repo = f"{hf_username}/{args.dataset_name}"
    elif "/" not in dataset_repo:
        if hf_username in PLACEHOLDER_VALUES:
            print("ERROR: dataset-repo sin owner y HF_USERNAME inválido", file=sys.stderr)
            return 2
        dataset_repo = f"{hf_username}/{dataset_repo}"

    if hf_token in PLACEHOLDER_VALUES:
        if args.dry_run:
            print("WARN: HF_TOKEN vacío/placeholder. Dry run continúa sin publicar.", file=sys.stderr)
        else:
            print("ERROR: HF_TOKEN vacío o placeholder", file=sys.stderr)
            return 2

    exclude_globs = parse_csv_list(args.exclude_globs)
    files = collect_raw_files(
        raw_dir,
        include_manual=bool(args.include_manual),
        exclude_globs=exclude_globs,
        max_files=int(args.max_files),
    )
    if not files and not args.allow_empty:
        print("ERROR: no hay ficheros raw elegibles para publicar", file=sys.stderr)
        return 2

    blocks = chunk_paths(files, int(args.max_files_per_block))
    if int(args.max_blocks) > 0:
        blocks = blocks[: int(args.max_blocks)]

    temp_ctx: tempfile.TemporaryDirectory[str] | None = None
    if args.keep_temp:
        build_root = Path(tempfile.mkdtemp(prefix="hf_raw_blocks_"))
    else:
        temp_ctx = tempfile.TemporaryDirectory(prefix="hf_raw_blocks_")
        build_root = Path(temp_ctx.name)

    try:
        snapshot_rel_dir = Path(args.snapshot_prefix) / snapshot_date
        snapshot_dir = build_root / snapshot_rel_dir
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        blocks_rel_prefix = Path(args.blocks_prefix)
        blocks_abs_dir = snapshot_dir / blocks_rel_prefix
        blocks_abs_dir.mkdir(parents=True, exist_ok=True)

        tracked_files: list[Path] = []
        block_index: list[dict[str, Any]] = []
        published_file_count = 0
        published_file_bytes = 0

        for block_idx, block_files in enumerate(blocks):
            block_id = f"block-{block_idx:05d}"
            tar_rel = blocks_rel_prefix / f"{block_id}.tar.gz"
            man_rel = blocks_rel_prefix / f"{block_id}.manifest.jsonl"
            stats = build_block_archive(
                raw_dir=raw_dir,
                block_files=block_files,
                block_tar_path=snapshot_dir / tar_rel,
                block_manifest_path=snapshot_dir / man_rel,
                gzip_level=int(args.gzip_level),
            )
            tracked_files.extend([tar_rel, man_rel])
            published_file_count += int(stats["files_count"])
            published_file_bytes += int(stats["files_bytes_total"])
            block_index.append(
                {
                    "block_id": block_id,
                    "archive_path": tar_rel.as_posix(),
                    "manifest_path": man_rel.as_posix(),
                    **stats,
                }
            )

        index_rel = Path("raw_blocks_index.json")
        index_payload = {
            "snapshot_date": snapshot_date,
            "generated_at": now_utc_iso(),
            "raw_dir": str(raw_dir),
            "include_manual": bool(args.include_manual),
            "exclude_globs": exclude_globs,
            "max_files_per_block": int(args.max_files_per_block),
            "blocks_count": len(block_index),
            "files_count": published_file_count,
            "files_bytes_total": published_file_bytes,
            "blocks": block_index,
        }
        (snapshot_dir / index_rel).write_text(
            json.dumps(index_payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        tracked_files.append(index_rel)

        manifest_rel = Path("manifest.json")
        manifest_payload = {
            "project": "vota-con-la-chola-raw",
            "snapshot_date": snapshot_date,
            "generated_at": now_utc_iso(),
            "dataset_repo": dataset_repo,
            "snapshot_dir": snapshot_rel_dir.as_posix(),
            "raw_dir": str(raw_dir),
            "stats": {
                "blocks_count": len(block_index),
                "files_count": published_file_count,
                "files_bytes_total": published_file_bytes,
                "include_manual": bool(args.include_manual),
            },
            "files": [],
        }
        for rel in tracked_files:
            abs_path = snapshot_dir / rel
            manifest_payload["files"].append(
                {
                    "path": rel.as_posix(),
                    "bytes": int(abs_path.stat().st_size),
                    "sha256": sha256_file(abs_path),
                }
            )
        (snapshot_dir / manifest_rel).write_text(
            json.dumps(manifest_payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        tracked_files.append(manifest_rel)

        write_checksums(snapshot_dir, tracked_files)

        latest_payload = {
            "project": "vota-con-la-chola-raw",
            "dataset_repo": dataset_repo,
            "snapshot_date": snapshot_date,
            "snapshot_dir": snapshot_rel_dir.as_posix(),
            "blocks_count": len(block_index),
            "files_count": published_file_count,
            "updated_at": now_utc_iso(),
        }
        (build_root / "latest.json").write_text(
            json.dumps(latest_payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

        (build_root / "README.md").write_text(
            build_dataset_readme(
                dataset_repo=dataset_repo,
                source_repo_url=source_repo_url,
                snapshot_date=snapshot_date,
                snapshot_rel_dir=snapshot_rel_dir,
                blocks=block_index,
                include_manual=bool(args.include_manual),
                exclude_globs=exclude_globs,
                max_files_per_block=int(args.max_files_per_block),
            ),
            encoding="utf-8",
        )

        print(f"HF dataset repo: {dataset_repo}")
        print(f"Snapshot bundle: {snapshot_rel_dir.as_posix()}")
        print(f"Raw files selected: {len(files)}")
        print(f"Blocks built: {len(block_index)}")
        print(f"Files packed: {published_file_count}")
        print(f"Bytes packed (raw): {published_file_bytes}")
        print(f"include_manual: {str(bool(args.include_manual)).lower()}")

        if args.dry_run:
            print("Dry run: no se subió nada a Hugging Face")
            print(f"Bundle local: {build_root}")
            return 0

        from huggingface_hub import HfApi  # type: ignore

        api = HfApi(token=hf_token)
        api.create_repo(
            repo_id=dataset_repo,
            repo_type="dataset",
            private=bool(args.private),
            exist_ok=True,
        )
        api.upload_folder(
            repo_id=dataset_repo,
            repo_type="dataset",
            folder_path=str(build_root),
            path_in_repo=".",
            commit_message=f"Publish raw blocks snapshot {snapshot_date}",
            delete_patterns=[
                f"{snapshot_rel_dir.as_posix()}/**",
                "latest.json",
                "README.md",
            ],
        )
        print(f"OK published to https://huggingface.co/datasets/{dataset_repo}")
        return 0
    except (RuntimeError, ValueError, sqlite3.OperationalError, OSError, tarfile.TarError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

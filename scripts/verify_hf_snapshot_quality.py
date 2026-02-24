#!/usr/bin/env python3
"""Verifica en remoto que el snapshot HF publica quality_report consistente."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from scripts.publicar_hf_snapshot import DEFAULT_DATASET_NAME, PLACEHOLDER_VALUES, load_dotenv, resolve_setting
except ModuleNotFoundError:
    # Supports execution as `python3 scripts/verify_hf_snapshot_quality.py` inside containers.
    from publicar_hf_snapshot import DEFAULT_DATASET_NAME, PLACEHOLDER_VALUES, load_dotenv, resolve_setting


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verificar quality_report remoto en Hugging Face Datasets")
    p.add_argument(
        "--dataset-repo",
        default="",
        help="Repo HF dataset (owner/name). Si no se define, usa HF_DATASET_REPO_ID o HF_USERNAME/default.",
    )
    p.add_argument("--hf-username", default="", help="Usuario HF (override; si vacio usa env/.env)")
    p.add_argument("--env-file", default=".env", help="Archivo .env con credenciales/config")
    p.add_argument(
        "--snapshot-date",
        default="",
        help="Fecha esperada YYYY-MM-DD (opcional). Si no se indica, se usa latest.json remoto.",
    )
    p.add_argument("--timeout", type=float, default=20.0, help="Timeout de red por request (segundos)")
    p.add_argument("--skip-readme-check", action="store_true", help="No validar sección de calidad en README remoto")
    p.add_argument("--json-out", default="", help="Ruta opcional para guardar reporte JSON")
    return p.parse_args()


def resolve_dataset_repo(dataset_repo: str, hf_username: str) -> str:
    repo = dataset_repo.strip()
    user = hf_username.strip()
    if not repo:
        if user in PLACEHOLDER_VALUES:
            raise ValueError("No se pudo resolver dataset repo: define HF_DATASET_REPO_ID o HF_USERNAME válido.")
        return f"{user}/{DEFAULT_DATASET_NAME}"
    if "/" in repo:
        return repo
    if user in PLACEHOLDER_VALUES:
        raise ValueError("HF_DATASET_REPO_ID sin owner y HF_USERNAME inválido.")
    return f"{user}/{repo}"


def fetch_text(url: str, timeout: float) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "vota-con-la-chola/verify-hf-snapshot-quality",
            "Accept": "application/json,text/plain,text/markdown,*/*",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(req, timeout=float(timeout)) as resp:
        body = resp.read()
    return body.decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    raw = fetch_text(url, timeout)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON no-objeto en {url}")
    return payload


def evaluate_contract(
    latest_payload: dict[str, Any],
    manifest_payload: dict[str, Any],
    readme_text: str,
    expected_snapshot_date: str,
    require_readme: bool,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    checks: dict[str, Any] = {}

    latest_snapshot_date = str(latest_payload.get("snapshot_date") or "")
    manifest_snapshot_date = str(manifest_payload.get("snapshot_date") or "")
    checks["snapshot_date_latest"] = latest_snapshot_date
    checks["snapshot_date_manifest"] = manifest_snapshot_date
    checks["snapshot_date_expected"] = expected_snapshot_date

    if not latest_snapshot_date:
        errors.append("latest.json no incluye snapshot_date")
    if latest_snapshot_date != expected_snapshot_date:
        errors.append(
            f"snapshot_date mismatch en latest.json: esperado={expected_snapshot_date!r} real={latest_snapshot_date!r}"
        )
    if manifest_snapshot_date != expected_snapshot_date:
        errors.append(
            f"snapshot_date mismatch en manifest.json: esperado={expected_snapshot_date!r} real={manifest_snapshot_date!r}"
        )

    latest_quality = latest_payload.get("quality_report")
    manifest_quality = manifest_payload.get("quality_report")
    checks["latest_has_quality_report"] = isinstance(latest_quality, dict)
    checks["manifest_has_quality_report"] = isinstance(manifest_quality, dict)

    if not isinstance(latest_quality, dict):
        errors.append("latest.json no incluye quality_report")
        latest_quality = {}
    if not isinstance(manifest_quality, dict):
        errors.append("manifest.json no incluye quality_report")
        manifest_quality = {}

    file_name = str(latest_quality.get("file_name") or "")
    checks["quality_file_name"] = file_name
    checks["vote_gate_passed"] = bool(latest_quality.get("vote_gate_passed"))
    checks["initiative_gate_passed_present"] = "initiative_gate_passed" in latest_quality
    checks["initiative_gate_passed"] = (
        bool(latest_quality.get("initiative_gate_passed")) if "initiative_gate_passed" in latest_quality else None
    )

    if not file_name:
        errors.append("quality_report.file_name ausente en latest.json")
    elif not file_name.startswith("votaciones-kpis-es-"):
        errors.append(f"quality_report.file_name inesperado: {file_name!r}")

    shared_quality_keys = sorted(set(latest_quality) & set(manifest_quality))
    mismatches: list[str] = []
    for key in shared_quality_keys:
        if latest_quality.get(key) != manifest_quality.get(key):
            mismatches.append(key)
    checks["quality_shared_keys"] = shared_quality_keys
    checks["quality_mismatch_keys"] = mismatches
    if mismatches:
        errors.append("quality_report mismatch latest vs manifest en keys: " + ", ".join(mismatches))

    if require_readme:
        checks["readme_has_quality_section"] = "Resumen de calidad del snapshot" in readme_text
        checks["readme_has_vote_gate_line"] = "Vote gate:" in readme_text
        checks["readme_mentions_quality_file"] = bool(file_name) and (f"published/{file_name}" in readme_text)
        if not checks["readme_has_quality_section"]:
            errors.append("README remoto no contiene 'Resumen de calidad del snapshot'")
        if not checks["readme_has_vote_gate_line"]:
            errors.append("README remoto no contiene línea 'Vote gate:'")
        if file_name and not checks["readme_mentions_quality_file"]:
            errors.append(f"README remoto no referencia published/{file_name}")

    return checks, errors


def main() -> int:
    args = parse_args()
    try:
        if float(args.timeout) <= 0:
            raise ValueError("--timeout debe ser > 0")
        dotenv_values = load_dotenv(Path(args.env_file))
        hf_username = resolve_setting("HF_USERNAME", args.hf_username, dotenv_values)
        dataset_repo_raw = resolve_setting("HF_DATASET_REPO_ID", args.dataset_repo, dotenv_values)
        dataset_repo = resolve_dataset_repo(dataset_repo_raw, hf_username)

        base_url = f"https://huggingface.co/datasets/{dataset_repo}/resolve/main"
        latest_url = f"{base_url}/latest.json"
        latest_payload = fetch_json(latest_url, timeout=float(args.timeout))
        snapshot_date = args.snapshot_date.strip() or str(latest_payload.get("snapshot_date") or "").strip()
        if not snapshot_date:
            raise ValueError("No se pudo resolver snapshot_date (ni --snapshot-date ni latest.json)")
        manifest_url = f"{base_url}/snapshots/{snapshot_date}/manifest.json"
        manifest_payload = fetch_json(manifest_url, timeout=float(args.timeout))
        readme_url = f"{base_url}/README.md"
        readme_text = "" if args.skip_readme_check else fetch_text(readme_url, timeout=float(args.timeout))
    except (ValueError, HTTPError, URLError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    checks, errors = evaluate_contract(
        latest_payload=latest_payload,
        manifest_payload=manifest_payload,
        readme_text=readme_text,
        expected_snapshot_date=snapshot_date,
        require_readme=(not args.skip_readme_check),
    )

    report = {
        "dataset_repo": dataset_repo,
        "snapshot_date": snapshot_date,
        "urls": {
            "latest": latest_url,
            "manifest": manifest_url,
            "readme": readme_url,
        },
        "checks": checks,
        "errors": errors,
        "passed": not errors,
    }

    if args.json_out.strip():
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(f"HF dataset repo: {dataset_repo}")
    print(f"Snapshot date: {snapshot_date}")
    print(f"Latest quality_report: {'yes' if checks.get('latest_has_quality_report') else 'no'}")
    print(f"Manifest quality_report: {'yes' if checks.get('manifest_has_quality_report') else 'no'}")
    if checks.get("quality_file_name"):
        print(f"Quality file: {checks['quality_file_name']}")
    print(f"Readme check: {'skipped' if args.skip_readme_check else 'enabled'}")
    if errors:
        print("FAIL: contrato de quality_report no cumple")
        for err in errors:
            print(f"- {err}")
        return 1
    print("OK: contrato de quality_report verificado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

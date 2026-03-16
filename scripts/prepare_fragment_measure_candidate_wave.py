#!/usr/bin/env python3
"""Prepare a Codex CLI wave for fragment-level measure extraction."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from textwrap import dedent
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = "docs/etl/review_schemas/fragment_measure_candidate_output.schema.json"
DEFAULT_MODEL = "gpt-5.3-codex-spark"
DEFAULT_EFFORT = "high"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prepare a fragment measure Codex CLI wave")
    p.add_argument("--queue-csv", required=True, help="Input queue CSV from export_fragment_measure_candidate_queue.py")
    p.add_argument("--out-dir", required=True, help="Output directory for prompts, manifest, and launcher")
    p.add_argument("--limit", type=int, default=24, help="Maximum number of tasks to select")
    p.add_argument("--max-per-initiative", type=int, default=2, help="Maximum tasks per initiative")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Codex model for each worker")
    p.add_argument("--effort", default=DEFAULT_EFFORT, help="Codex reasoning effort to use")
    p.add_argument("--max-parallel", type=int, default=6, help="Default MAX_PARALLEL in launcher")
    p.add_argument("--schema-path", default=DEFAULT_SCHEMA_PATH, help="Output schema path relative to repo root")
    return p.parse_args()


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _safe_task_name(task_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", _norm(task_id))


def _repo_path_or_abs(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _read_queue(queue_csv: Path) -> tuple[list[str], list[dict[str, str]]]:
    with queue_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [{_norm(k): _norm(v) for k, v in row.items()} for row in reader]
    return fieldnames, rows


def _select_rows(rows: list[dict[str, str]], *, limit: int, max_per_initiative: int) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    per_initiative: dict[str, int] = defaultdict(int)
    for row in rows:
        initiative_id = _norm(row.get("initiative_id"))
        if not initiative_id:
            continue
        if max_per_initiative > 0 and per_initiative[initiative_id] >= max_per_initiative:
            continue
        per_initiative[initiative_id] += 1
        selected.append(row)
        if limit > 0 and len(selected) >= limit:
            break
    return selected


def _prompt_text(*, task_id: str, evidence_bundle_dir: str) -> str:
    return dedent(
        f"""\
        You are a fragment-level measure extraction worker for one parliamentary text fragment.

        Task id: `{task_id}`
        Evidence bundle: `{evidence_bundle_dir}`

        Instructions:
        - Read `bundle.json` in the evidence bundle first.
        - Use only the evidence in this bundle. Do not browse the web.
        - Do not edit repo files.
        - Decide whether this fragment contains 1 to 3 concrete citizen-facing legal effects a person might actually search for.
        - If the fragment is not materially useful for citizen-facing measures, return `review_status` = `ignored` and `candidates` = `[]`.
        - If useful, return `review_status` = `resolved` and 1 to 3 candidates.
        - Prefer concrete taxes, prices, benefits, obligations, restrictions, sanctions, and practical rights over generic institutional or process summaries.
        - Keep `measure_title` and `citizen_summary` factual, short, and in plain Spanish.
        - Choose `primary_vote_event_ids` from `recommended_primary_vote_event_ids` when possible.
        - For ordinary approval or amendment votes, `support_side` will usually be `yes` for the text being voted.
        - Every evidence row must quote concrete wording and include the correct `fragment_id`.
        - Be conservative. If uncertain, omit the candidate instead of over-claiming.

        Return JSON that matches the provided output schema exactly.
        """
    )


def _launcher_text(*, root: Path, base: Path, schema_path: str, max_parallel: int) -> str:
    base_rel = _repo_path_or_abs(base)
    return dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail

        ROOT="{root}"
        BASE="{base_rel}"
        MANIFEST="$BASE/manifest.csv"
        LOGS="$BASE/logs"
        mkdir -p "$LOGS"
        MAX_PARALLEL="${{MAX_PARALLEL:-{int(max_parallel)}}}"

        wait_for_slot() {{
          while [ "$(jobs -pr | wc -l | tr -d ' ')" -ge "$MAX_PARALLEL" ]; do
            sleep 1
          done
        }}

        while IFS=, read -r name model effort sandbox output_file prompt_file; do
          wait_for_slot
          codex exec \\
            -C "$ROOT" \\
            --model "$model" \\
            -c "model_reasoning_effort=\\"$effort\\"" \\
            -c 'model_reasoning_summary="auto"' \\
            --full-auto \\
            --output-schema {schema_path} \\
            -o "$output_file" \\
            < "$prompt_file" \\
            > "$LOGS/$name.log" 2>&1 &
        done < <(tail -n +2 "$MANIFEST")

        wait
        """
    )


def prepare_wave(
    *,
    queue_csv: Path,
    out_dir: Path,
    limit: int,
    max_per_initiative: int,
    model: str,
    effort: str,
    max_parallel: int,
    schema_path: str,
) -> dict[str, Any]:
    fieldnames, rows = _read_queue(queue_csv)
    selected = _select_rows(rows, limit=limit, max_per_initiative=max_per_initiative)

    out_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir = out_dir / "prompts"
    results_dir = out_dir / "results"
    logs_dir = out_dir / "logs"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    selected_queue_csv = out_dir / "selected_queue.csv"
    manifest_csv = out_dir / "manifest.csv"
    launch_script = out_dir / "launch_batch.sh"

    with selected_queue_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)

    with manifest_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["name", "model", "effort", "sandbox", "output_file", "prompt_file"])
        for row in selected:
            task_id = _norm(row.get("task_id"))
            safe_name = _safe_task_name(task_id)
            prompt_path = prompts_dir / f"{safe_name}.txt"
            output_path = results_dir / f"{safe_name}.json"
            prompt_path.write_text(
                _prompt_text(task_id=task_id, evidence_bundle_dir=_norm(row.get("evidence_bundle_dir"))),
                encoding="utf-8",
            )
            writer.writerow(
                [
                    safe_name,
                    _norm(model) or DEFAULT_MODEL,
                    _norm(effort) or DEFAULT_EFFORT,
                    "workspace-write",
                    _repo_path_or_abs(output_path),
                    _repo_path_or_abs(prompt_path),
                ]
            )

    launch_script.write_text(
        _launcher_text(
            root=REPO_ROOT,
            base=out_dir,
            schema_path=_norm(schema_path) or DEFAULT_SCHEMA_PATH,
            max_parallel=max_parallel,
        ),
        encoding="utf-8",
    )
    launch_script.chmod(0o755)

    return {
        "queue_csv": _repo_path_or_abs(queue_csv),
        "out_dir": _repo_path_or_abs(out_dir),
        "selected_rows": len(selected),
        "selected_queue_csv": _repo_path_or_abs(selected_queue_csv),
        "manifest_csv": _repo_path_or_abs(manifest_csv),
        "launch_script": _repo_path_or_abs(launch_script),
        "model": _norm(model) or DEFAULT_MODEL,
        "effort": _norm(effort) or DEFAULT_EFFORT,
    }


def main() -> int:
    args = parse_args()
    summary = prepare_wave(
        queue_csv=Path(args.queue_csv),
        out_dir=Path(args.out_dir),
        limit=max(0, int(args.limit)),
        max_per_initiative=max(0, int(args.max_per_initiative)),
        model=args.model,
        effort=args.effort,
        max_parallel=max(1, int(args.max_parallel)),
        schema_path=args.schema_path,
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

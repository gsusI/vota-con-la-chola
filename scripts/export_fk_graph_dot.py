#!/usr/bin/env python3
"""Export SQLite FK graph as compact Graphviz DOT / Mermaid.

The goal is readable schema diagrams for large schemas:
- clusters by table family to reduce crossing
- orthogonal/sane layout defaults
- optional SVG render via Graphviz `dot`
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_DOT = Path("docs/er-schema.compact.dot")
DEFAULT_SVG = Path("docs/er-schema.compact.svg")
DEFAULT_MERMAID = Path("docs/er-schema.compact.mmd")


@dataclass(frozen=True)
class ForeignKey:
    child: str
    child_col: str
    parent: str
    parent_col: str
    on_delete: str
    on_update: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export FK graph from SQLite as compact DOT")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--out-dot", default=str(DEFAULT_DOT), help="DOT output path")
    p.add_argument("--out-svg", default=str(DEFAULT_SVG), help="SVG output path")
    p.add_argument("--out-mermaid", default=str(DEFAULT_MERMAID), help="Mermaid output path")
    p.add_argument("--format", choices=("dot", "mermaid", "both"), default="both")
    p.add_argument("--rankdir", default="LR", choices=("LR", "TB"), help="Graph direction")
    p.add_argument("--no-cluster", action="store_true", help="Disable clustering by table family")
    p.add_argument("--no-labels", action="store_true", help="Emit only table names (faster, denser)")
    p.add_argument("--render-svg", action="store_true", help="Render SVG with `dot` after DOT export")
    p.add_argument("--dot", default="dot", help="`dot` binary path")
    p.add_argument("--include-isolated", choices=("all", "fk"), default="all", help="Include tables without FKs")
    return p.parse_args(argv)


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(r[0]) for r in rows]


def load_foreign_keys(conn: sqlite3.Connection) -> list[ForeignKey]:
    fks: list[ForeignKey] = []
    for table in list_tables(conn):
        for fk in conn.execute(f"PRAGMA foreign_key_list({table})").fetchall():
            if not fk["table"]:
                continue
            fks.append(
                ForeignKey(
                    child=table,
                    child_col=fk["from"],
                    parent=str(fk["table"]),
                    parent_col=str(fk["to"]),
                    on_delete=str(fk["on_delete"] or ""),
                    on_update=str(fk["on_update"] or ""),
                )
            )
    return fks


def load_pk_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [str(r["name"]) for r in rows if r["pk"]]


def load_table_row_counts(conn: sqlite3.Connection, tables: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in sorted(tables):
        try:
            counts[table] = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()[0]
        except sqlite3.DatabaseError:
            counts[table] = -1
    return counts


def classify_cluster(table: str) -> str:
    if table in {
        "sources",
        "source_records",
        "raw_fetches",
        "document_fetches",
        "run_fetches",
        "ingestion_runs",
        "text_documents",
    }:
        return "Source & ETL"

    if table.startswith("parl_"):
        return "Parliament procedures"

    if table.startswith("sanction_") or table.startswith("liberty_"):
        return "Sanctions & liberty"

    if table.startswith("policy_") or table.startswith("indicator_"):
        return "Policy analytics"

    if table.startswith("topic_"):
        return "Citizen topics"

    if table.startswith("infoelectoral_"):
        return "Electoral"

    if table.startswith("money_"):
        return "Budgets & subsidies"

    if table in {
        "admin_levels",
        "institutions",
        "territories",
        "roles",
        "genders",
        "persons",
        "person_identifiers",
        "person_name_aliases",
        "parties",
        "party_aliases",
        "domains",
    }:
        return "People & org dimensions"

    if table in {"legal_norms", "legal_norm_fragments", "legal_norm_lineage_edges", "legal_fragment_responsibilities"}:
        return "Legal corpus"

    if table in {"parl_initiatives", "parl_vote_events", "parl_vote_member_votes", "parl_vote_event_initiatives"}:
        return "Parliament procedures"

    return "Core tables"


def escape_label(text: str) -> str:
    return text.replace('\\', '\\\\').replace('"', '\\"').replace("\n", "\\n")


def node_label(
    conn: sqlite3.Connection,
    table: str,
    row_count: int,
    include_fields: bool,
) -> str:
    table_name = table if row_count < 0 else f"{table} (n={row_count})"
    if not include_fields:
        return table_name

    pks = load_pk_columns(conn, table)
    if not pks:
        return f"{table_name}\\nPK <rowid>"
    if len(pks) > 1:
        return f"{table_name}\\nPK: {', '.join(pks)}"
    return f"{table_name}\\nPK: {pks[0]}"


def edge_label(fk: ForeignKey) -> str:
    if fk.on_delete and fk.on_delete != "NO ACTION":
        return f"{fk.child_col} -> {fk.parent_col} ({fk.on_delete})"
    return f"{fk.child_col} -> {fk.parent_col}"


def emit_dot(
    *,
    conn: sqlite3.Connection,
    out: Path,
    fks: list[ForeignKey],
    rankdir: str,
    use_clusters: bool,
    include_fields: bool,
    include_isolated: bool,
) -> dict[str, Any]:
    tables = set(list_tables(conn))
    fk_children = {fk.child for fk in fks}
    fk_parents = {fk.parent for fk in fks}

    nodes = set()
    if include_isolated == "all":
        nodes = set(tables)
    else:
        nodes = {t for t in tables if t in fk_children or t in fk_parents}

    filtered_fks = [fk for fk in fks if fk.child in nodes and fk.parent in nodes]

    clusters: dict[str, list[str]] = {}
    row_counts = load_table_row_counts(conn=conn, tables=set(tables))
    if use_clusters:
        for table in sorted(nodes):
            clusters.setdefault(classify_cluster(table), []).append(table)

    with out.open("w", encoding="utf-8") as f:
        f.write("digraph ER {\n")
        f.write("  rankdir=%s\n" % rankdir)
        f.write("  splines=ortho\n")
        f.write("  overlap=false\n")
        f.write("  concentrate=true\n")
        f.write("  nodesep=0.45\n")
        f.write("  ranksep=0.55\n")
        f.write("  node [shape=box, style=rounded, fontsize=10, fontname=Helvetica]\n")
        f.write("  edge [fontsize=8, fontname=Helvetica]\n\n")

        # Ensure deterministic node order
        for table in sorted(nodes):
            if table in clusters:
                continue
            row_count = row_counts.get(table, -1)
            label = escape_label(
                node_label(
                    conn=conn,
                    table=table,
                    row_count=row_count,
                    include_fields=include_fields,
                )
            )
            width_hint = max(1.0, min(3.0, 1.1 + 0.06 * len(label)))
            f.write(
                f'  "{table}" [label="{label}", width={width_hint:.2f}, tooltip="{table} ({row_count})"]\n'
            )

        if use_clusters:
            for cluster_id, tables_in_cluster in clusters.items():
                cluster_name = re.sub(r"[^a-zA-Z0-9_]", "_", cluster_id)
                f.write(f"\n  subgraph cluster_{cluster_name} {{\n")
                f.write('    style=rounded;\n')
                f.write(f'    color="#d0d0d0";\n')
                f.write(f'    label="{escape_label(cluster_id)}";\n')
                for table in sorted(tables_in_cluster):
                    row_count = row_counts.get(table, -1)
                    label = escape_label(
                        node_label(
                            conn=conn,
                            table=table,
                            row_count=row_count,
                            include_fields=include_fields,
                        )
                    )
                    width_hint = max(1.0, min(3.2, 1.1 + 0.06 * len(label)))
                    f.write(
                        f'    "{table}" [label="{label}", width={width_hint:.2f}, tooltip="{table} ({row_count})"]\n'
                    )
                f.write("  }\n")

        for fk in filtered_fks:
            if fk.parent not in nodes:
                continue
            penwidth = 1.4
            color = "#555555"
            if fk.parent in {"sources", "source_records", "raw_fetches", "run_fetches", "ingestion_runs"}:
                color = "#2b6cb0"
            elif fk.parent.startswith("parl_"):
                color = "#2f855a"
            elif fk.parent.startswith("topic_"):
                color = "#b7791f"
            elif fk.parent.startswith("sanction_"):
                color = "#b33"  # warm

            attrs = [
                f'label="{escape_label(edge_label(fk))}"',
                "fontsize=8",
                f'color="{color}"',
                f'fontcolor="{color}"',
                f'penwidth={penwidth}',
                "arrowhead=vee",
            ]
            if fk.on_delete and fk.on_delete != "NO ACTION":
                attrs.append(f'constraint=true')
            f.write(f'  "{fk.child}" -> "{fk.parent}" [{", ".join(attrs)}]\n')

        f.write("}\n")

    return {
        "node_count": len(nodes),
        "edge_count": len(filtered_fks),
        "clusters": clusters,
    }


def emit_mermaid(
    *,
    conn: sqlite3.Connection,
    out: Path,
    fks: list[ForeignKey],
    include_isolated: str,
) -> dict[str, int]:
    tables = set(list_tables(conn))
    fk_children = {fk.child for fk in fks}
    fk_parents = {fk.parent for fk in fks}

    nodes = set(tables) if include_isolated == "all" else {t for t in tables if t in fk_children or t in fk_parents}
    filtered_fks = [fk for fk in fks if fk.child in nodes and fk.parent in nodes]

    with out.open("w", encoding="utf-8") as f:
        f.write("erDiagram\n")
        for table in sorted(nodes):
            pks = load_pk_columns(conn, table)
            if pks:
                f.write(f'  {table} {{\n')
                for pk in pks[:5]:
                    f.write(f"    int {pk} PK\n")
                if len(pks) > 5:
                    f.write("    ...\n")
                f.write("  }\n")
            else:
                f.write(f"  {table} {{\n    int <rowid> PK\n  }}\n")

        for fk in sorted(filtered_fks, key=lambda item: (item.parent, item.child)):
            f.write(f"  {fk.parent} ||--o{{ {fk.child} : {fk.child_col}\n")

    return {"nodes": len(nodes), "edges": len(filtered_fks)}


def render_svg(dot_path: Path, svg_path: Path, dot_bin: str) -> int:
    if shutil.which(dot_bin) is None:
        print(f"ERROR: dot binary not found: {dot_bin}", flush=True)
        return 1

    cmd = [dot_bin, "-Tsvg", "-Goverlap=false", "-Gsplines=ortho", "-o", str(svg_path), str(dot_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return 0

    if "Orthogonal edges do not currently handle edge labels" in (proc.stderr or ""):
        print("WARN: dot orthogonal mode failed with edge labels; retrying without labels", flush=True)
        no_label_dot = dot_path.with_suffix(".label_free.dot")
        raw_lines = dot_path.read_text(encoding="utf-8").splitlines()
        cleaned: list[str] = []
        for line in raw_lines:
            if " -> " not in line or "[" not in line or "]" not in line:
                cleaned.append(line)
                continue

            pre, rest = line.split("[", 1)
            attrs = rest.rsplit("]", 1)[0]
            attr_parts = [part.strip() for part in attrs.split(",") if part.strip()]
            attr_parts = [part for part in attr_parts if not part.strip().startswith("label=")]
            if not attr_parts:
                cleaned.append(f"{pre}[ ]")
                continue
            cleaned.append(f"{pre}[{', '.join(attr_parts)}]")
        no_label_dot.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
        no_label_cmd = [
            dot_bin,
            "-Tsvg",
            "-Goverlap=false",
            "-Gsplines=ortho",
            "-o",
            str(svg_path),
            str(no_label_dot),
        ]
        proc = subprocess.run(no_label_cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return 0

        # final fallback: safe router for stubborn graphs
        fallback_cmd = [dot_bin, "-Tsvg", "-Goverlap=false", "-o", str(svg_path), str(no_label_dot)]
        proc = subprocess.run(fallback_cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            print("WARN: fell back to non-orthogonal spline renderer for SVG", flush=True)
            return 0

        # keep the most recent stderr/stdout for visibility
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        return proc.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    out_dot = Path(args.out_dot)
    out_svg = Path(args.out_svg)
    out_mermaid = Path(args.out_mermaid)

    conn = open_db(db_path)
    try:
        fks = load_foreign_keys(conn)
        conn_info = conn.execute("PRAGMA foreign_key_check").fetchall()
        if conn_info:
            print(f"WARN: {len(conn_info)} foreign_key_check violations present.")

        dot_stats = emit_dot(
            conn=conn,
            out=out_dot,
            fks=fks,
            rankdir=args.rankdir,
            use_clusters=not args.no_cluster,
            include_fields=not args.no_labels,
            include_isolated=args.include_isolated,
        )

        mermaid_stats = None
        if args.format in ("mermaid", "both"):
            mermaid_stats = emit_mermaid(
                conn=conn,
                out=out_mermaid,
                fks=fks,
                include_isolated=args.include_isolated,
            )

        print(f"Wrote DOT: {out_dot} (nodes={dot_stats['node_count']}, edges={dot_stats['edge_count']})")
        if mermaid_stats is not None:
            print(f"Wrote Mermaid: {out_mermaid} (nodes={mermaid_stats['nodes']}, edges={mermaid_stats['edges']})")

        if args.render_svg:
            code = render_svg(out_dot, out_svg, args.dot)
            if code != 0:
                return code
            print(f"Wrote SVG: {out_svg}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

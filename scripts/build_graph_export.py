#!/usr/bin/env python3
"""Stage A — single coherent, provenance-stamped graph export.

Earlier iterations left several divergent ``neo4j_relationships*.csv`` vintages
and a hand-edited Cypher script, with no single reproducible "current graph".
This script collapses that into one bundle:

    artifacts/graph_export/
        nodes.csv          unique (type, name) over surviving relationships
        relationships.csv  the post-audit edge set
        import.cypher      idempotent MERGE script (no APOC required)
        manifest.json      source vintages, git SHA, pre/post counts,
                           and EVERY dropped row with its cited reason

Reconciliation rule (deliberately conservative and data-driven):

  superset      = artifacts/neo4j_relationships_microbe_expanded.csv
                  (the most complete assembled export)
  minus UMLS    = rows whose (source_node, target_node, rel_type) match a
                  record in artifacts/dropped_entities_audit.jsonl
                  (Task-1 live audit; 2 records, 25% of 8 microbe->feature)
  minus vision  = CORRELATES_WITH rows matching the recorded vision-audit
                  retraction policy in scripts/drop_failed_vision_edges.py
                  (PMC6178902 firmicutes -> Total fat %; LFC scale, wrong sign)

Nothing is dropped that is not traceable to a recorded audit artifact, and
every drop is written into the manifest with its source-of-truth path.

Run:
    conda run -n base python scripts/build_graph_export.py
    conda run -n base python scripts/build_graph_export.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- Vision-audit retraction policy (provenance: scripts/drop_failed_vision_edges.py)
#     The repo already encodes this as a constant (DROP_FIGURE_IDS); we mirror
#     it here keyed on the columns the expanded CSV actually carries (pmcid +
#     source_node), since that CSV predates the figure_id column.
VISION_DROP_POLICY: list[dict[str, str]] = [
    {
        "pmcid": "PMC6178902",
        "source_node": "firmicutes",
        "rel_type": "CORRELATES_WITH",
        "reason": "vision_audit_retraction:PMC6178902_g0006_wrong_sign_LFC_scale",
        "source_of_truth": "scripts/drop_failed_vision_edges.py",
    }
]

REL_KEY = ("source_node", "target_node", "rel_type")


@dataclass
class DropRecord:
    source_node: str
    target_node: str
    rel_type: str
    reason: str
    source_of_truth: str
    pmid: str = ""
    pmcid: str = ""


@dataclass
class ExportResult:
    nodes: list[dict[str, str]]
    relationships: list[dict[str, Any]]
    dropped: list[DropRecord]
    pre_counts: dict[str, int] = field(default_factory=dict)
    post_counts: dict[str, int] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Pure, unit-testable core
# --------------------------------------------------------------------------- #
def read_relationships_csv(path: str | Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_umls_drops(audit_path: str | Path) -> list[DropRecord]:
    """Drops recorded by the Task-1 UMLS live audit (data-driven)."""
    drops: list[DropRecord] = []
    p = Path(audit_path)
    if not p.exists():
        return drops
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        drops.append(
            DropRecord(
                source_node=rec.get("source_node", ""),
                target_node=rec.get("target_node", ""),
                rel_type=rec.get("rel_type", ""),
                reason=f"umls_gate:{rec.get('drop_reason', 'unknown')}",
                source_of_truth=str(p),
                pmid=str(rec.get("pmid", "")),
            )
        )
    return drops


def _row_matches_vision_policy(row: dict[str, str], policy: dict[str, str]) -> bool:
    return (
        row.get("pmcid", "") == policy["pmcid"]
        and row.get("source_node", "") == policy["source_node"]
        and row.get("rel_type", "") == policy["rel_type"]
    )


def apply_drops(
    rows: list[dict[str, str]],
    umls_drops: list[DropRecord],
    vision_policy: list[dict[str, str]] | None = None,
) -> tuple[list[dict[str, str]], list[DropRecord]]:
    """Return (kept_rows, drop_records). Pure; deterministic."""
    vision_policy = vision_policy if vision_policy is not None else VISION_DROP_POLICY
    umls_keys = {(d.source_node, d.target_node, d.rel_type) for d in umls_drops}
    umls_by_key = {(d.source_node, d.target_node, d.rel_type): d for d in umls_drops}

    kept: list[dict[str, str]] = []
    fired: list[DropRecord] = []
    for row in rows:
        key = (row.get("source_node", ""), row.get("target_node", ""), row.get("rel_type", ""))
        if key in umls_keys:
            d = umls_by_key[key]
            fired.append(
                DropRecord(
                    source_node=key[0], target_node=key[1], rel_type=key[2],
                    reason=d.reason, source_of_truth=d.source_of_truth,
                    pmid=row.get("pmid", ""), pmcid=row.get("pmcid", ""),
                )
            )
            continue
        vmatch = next((p for p in vision_policy if _row_matches_vision_policy(row, p)), None)
        if vmatch is not None:
            fired.append(
                DropRecord(
                    source_node=row.get("source_node", ""),
                    target_node=row.get("target_node", ""),
                    rel_type=row.get("rel_type", ""),
                    reason=vmatch["reason"], source_of_truth=vmatch["source_of_truth"],
                    pmid=row.get("pmid", ""), pmcid=row.get("pmcid", ""),
                )
            )
            continue
        kept.append(row)
    return kept, fired


def derive_nodes(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Unique (label, name) pairs over both endpoints, sorted for reproducibility."""
    seen: set[tuple[str, str]] = set()
    for r in rows:
        if r.get("source_node_type") and r.get("source_node"):
            seen.add((r["source_node_type"], r["source_node"]))
        if r.get("target_node_type") and r.get("target_node"):
            seen.add((r["target_node_type"], r["target_node"]))
    return [{"label": lbl, "name": name} for lbl, name in sorted(seen)]


def count_by_rel(rows: list[dict[str, str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[r.get("rel_type", "?")] = out.get(r.get("rel_type", "?"), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def render_import_cypher(nodes: list[dict[str, str]], rels: list[dict[str, str]]) -> str:
    lines: list[str] = [
        "// SanoMap Radiomics Layer — coherent post-audit graph import",
        "// Generated by scripts/build_graph_export.py — DO NOT hand-edit.",
        "// Idempotent (MERGE). No APOC required.",
        "",
    ]
    labels = sorted({n["label"] for n in nodes})
    for lbl in labels:
        lines.append(
            f"CREATE CONSTRAINT {lbl.lower()}_name IF NOT EXISTS "
            f"FOR (n:{lbl}) REQUIRE n.name IS UNIQUE;"
        )
    lines.append("")
    lines.append("// --- Nodes ---")
    for n in nodes:
        lines.append(f"MERGE (:{n['label']} {{name: '{_esc(n['name'])}'}});")
    lines.append("")
    lines.append("// --- Relationships ---")
    for r in rels:
        props = []
        if r.get("pmid"):
            props.append(f"pmid: '{_esc(r['pmid'])}'")
        if r.get("confidence"):
            props.append(f"confidence: {r['confidence']}")
        prop_str = (" {" + ", ".join(props) + "}") if props else ""
        lines.append(
            f"MATCH (s:{r['source_node_type']} {{name: '{_esc(r['source_node'])}'}}), "
            f"(t:{r['target_node_type']} {{name: '{_esc(r['target_node'])}'}}) "
            f"MERGE (s)-[:{r['rel_type']}{prop_str}]->(t);"
        )
    lines.append("")
    lines.append("// --- Verify ---")
    lines.append("MATCH (n) RETURN labels(n)[0] AS label, count(n) ORDER BY count(n) DESC;")
    lines.append("MATCH ()-[r]->() RETURN type(r) AS rel, count(r) ORDER BY count(r) DESC;")
    return "\n".join(lines) + "\n"


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def _file_vintage(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"path": str(p), "exists": False}
    st = p.stat()
    return {
        "path": str(p),
        "exists": True,
        "bytes": st.st_size,
        "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
    }


def build_export(source_csv: str | Path, umls_audit: str | Path) -> ExportResult:
    rows = read_relationships_csv(source_csv)
    pre = count_by_rel(rows)
    umls_drops = load_umls_drops(umls_audit)
    kept, dropped = apply_drops(rows, umls_drops)
    return ExportResult(
        nodes=derive_nodes(kept),
        relationships=kept,
        dropped=dropped,
        pre_counts=pre,
        post_counts=count_by_rel(kept),
    )


# --------------------------------------------------------------------------- #
# Side-effecting CLI
# --------------------------------------------------------------------------- #
def write_bundle(result: ExportResult, out_dir: Path, source_csv: str, umls_audit: str) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)

    nodes_path = out_dir / "nodes.csv"
    with open(nodes_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["label", "name"])
        w.writeheader()
        w.writerows(result.nodes)

    rels_path = out_dir / "relationships.csv"
    if result.relationships:
        fields = list(result.relationships[0].keys())
        with open(rels_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(result.relationships)

    cypher_path = out_dir / "import.cypher"
    cypher_path.write_text(render_import_cypher(result.nodes, result.relationships), encoding="utf-8")

    manifest = {
        "stage": "graph_export_reconciliation",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "sources": {
            "superset_csv": _file_vintage(source_csv),
            "umls_audit": _file_vintage(umls_audit),
            "vision_drop_policy": VISION_DROP_POLICY,
        },
        "counts": {
            "pre_audit_by_rel": result.pre_counts,
            "post_audit_by_rel": result.post_counts,
            "pre_total": sum(result.pre_counts.values()),
            "post_total": sum(result.post_counts.values()),
            "nodes": len(result.nodes),
            "dropped": len(result.dropped),
        },
        "drops": [vars(d) for d in result.dropped],
        "schema_note": (
            "CORRELATES_WITH = quantitatively verified microbe->feature; "
            "ASSOCIATED_WITH = text co-mention feature->disease; "
            "bridge hypotheses are audit-only and never appear here."
        ),
        "outputs": {
            "nodes_csv": str(nodes_path),
            "relationships_csv": str(rels_path),
            "import_cypher": str(cypher_path),
        },
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {
        "nodes": str(nodes_path),
        "relationships": str(rels_path),
        "import_cypher": str(cypher_path),
        "manifest": str(manifest_path),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Stage A: coherent post-audit graph export.")
    ap.add_argument("--source-csv", default="artifacts/neo4j_relationships_microbe_expanded.csv")
    ap.add_argument("--umls-audit", default="artifacts/dropped_entities_audit.jsonl")
    ap.add_argument("--out-dir", default="artifacts/graph_export")
    ap.add_argument("--dry-run", action="store_true", help="Print summary; write nothing.")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_export(args.source_csv, args.umls_audit)
    print(f"superset rows : {sum(result.pre_counts.values())}  {result.pre_counts}")
    print(f"dropped       : {len(result.dropped)}")
    for d in result.dropped:
        print(f"  - [{d.rel_type}] {d.source_node} -> {d.target_node}  ({d.reason})")
    print(f"kept rows     : {sum(result.post_counts.values())}  {result.post_counts}")
    print(f"unique nodes  : {len(result.nodes)}")
    if args.dry_run:
        print("[dry-run] no files written.")
        return 0
    outs = write_bundle(result, Path(args.out_dir), args.source_csv, args.umls_audit)
    for k, v in outs.items():
        print(f"wrote {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

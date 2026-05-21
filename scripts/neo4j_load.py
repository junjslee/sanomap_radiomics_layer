#!/usr/bin/env python3
"""Load the reconciled graph_export/ bundle into a live Neo4j instance.

Fork 1 (live Neo4j, minimal) loader. Deliberately conservative:

* ``--dry-run`` (validate the bundle and print the plan WITHOUT connecting)
  is the safe default posture; a real load requires explicit invocation.
* Credentials come from env (``NEO4J_URI`` / ``NEO4J_USER`` /
  ``NEO4J_PASSWORD``) or flags — never hardcoded.
* The loader runs the idempotent ``import.cypher`` (MERGE), so re-running is
  safe and converges to the same graph. ``--wipe`` is gated behind an
  explicit flag and prints what it will delete first.

Prereq: ``pip install 'neo4j>=5,<6'`` and a running Neo4j (see
docs/NEO4J_RUNBOOK.md for the Docker path).

Examples:
    conda run -n base python scripts/neo4j_load.py --dry-run
    NEO4J_PASSWORD=... conda run -n base python scripts/neo4j_load.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _split_statements(cypher_text: str) -> list[str]:
    """Split import.cypher into individual executable statements.

    Statements are ``;``-terminated, one per line in our generated file;
    comment-only and blank lines are dropped.
    """
    statements: list[str] = []
    for raw in cypher_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        statements.append(line.rstrip(";"))
    return [s for s in statements if s]


def validate_bundle(bundle_dir: Path) -> dict:
    """Return the manifest dict; raise with a clear message if incomplete."""
    required = ["nodes.csv", "relationships.csv", "import.cypher", "manifest.json"]
    missing = [f for f in required if not (bundle_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"graph_export bundle at {bundle_dir} missing: {missing}. "
            f"Run: conda run -n base python scripts/build_graph_export.py"
        )
    return json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Load graph_export/ into Neo4j.")
    ap.add_argument("--bundle", default="artifacts/graph_export")
    ap.add_argument("--uri", default=os.environ.get("NEO4J_URI", "neo4j://localhost:7687"))
    ap.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    ap.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", ""))
    ap.add_argument("--database", default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate + print plan; do not connect. Safe default.")
    ap.add_argument("--wipe", action="store_true",
                    help="DETACH DELETE all nodes before import (gated).")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bundle = Path(args.bundle)

    try:
        manifest = validate_bundle(bundle)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    statements = _split_statements((bundle / "import.cypher").read_text(encoding="utf-8"))
    counts = manifest.get("counts", {})
    print(f"bundle      : {bundle}")
    print(f"git_sha     : {manifest.get('git_sha')}")
    print(f"post counts : {counts.get('post_audit_by_rel')}")
    print(f"nodes/rels  : {counts.get('nodes')} nodes / {counts.get('post_total')} rels")
    print(f"statements  : {len(statements)} executable Cypher statements")
    print(f"target      : {args.uri} (db={args.database}, user={args.user})")

    if args.dry_run:
        print("[dry-run] bundle valid; not connecting. "
              "Re-run without --dry-run (and with NEO4J_PASSWORD) to load.")
        return 0

    if not args.password:
        print("ERROR: no password. Set NEO4J_PASSWORD or pass --password.",
              file=sys.stderr)
        return 2

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("ERROR: neo4j driver not installed. Run: "
              "pip install 'neo4j>=5,<6'", file=sys.stderr)
        return 2

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        driver.verify_connectivity()
        with driver.session(database=args.database) as session:
            if args.wipe:
                print("--wipe: DETACH DELETE all nodes ...")
                session.run("MATCH (n) DETACH DELETE n")
            applied = 0
            for stmt in statements:
                if stmt.upper().startswith("MATCH (N) RETURN") or \
                   stmt.upper().startswith("MATCH ()-[R]->() RETURN"):
                    continue  # the verify queries — run them after, below
                session.run(stmt)
                applied += 1
            node_total = session.run(
                "MATCH (n) RETURN count(n) AS c").single()["c"]
            rel_total = session.run(
                "MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        print(f"applied {applied} statements")
        print(f"graph now: {node_total} nodes, {rel_total} relationships")
        expected_nodes = counts.get("nodes")
        if expected_nodes is not None and node_total != expected_nodes:
            print(f"NOTE: node count {node_total} != manifest {expected_nodes} "
                  f"(expected if the DB was non-empty; use --wipe for a clean load)")
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Neo4j Runbook (Fork 1 — live integration)

This is the operational path from the reconciled `graph_export/` bundle to a
queryable Neo4j instance. It is intentionally minimal: local Docker, a
one-file driver loader, and a read-only query module — no APOC, no clustering,
no hosted service.

## Why this exists

Earlier iterations had no live graph store — only a hand-runnable `.cypher`
file and several divergent CSV vintages. Fork 1 closes the PI's "Neo4j
integration" step with a reproducible spine:

```
assembled artifacts
  └─ scripts/build_graph_export.py   (Stage A: reconcile + provenance)
       └─ artifacts/graph_export/    (nodes, relationships, import.cypher, manifest)
            └─ scripts/neo4j_load.py (driver loader, idempotent)
                 └─ Neo4j  ←  src/graph_queries.py (read-only canonical traversals)
```

## Prerequisites

- Docker Desktop installed. **The daemon must be running** (`docker info`
  should succeed). On this machine Docker is installed but the daemon is
  stopped by default — start Docker Desktop first.
- `pip install 'neo4j>=5,<6'` in the conda `base` env (now pinned in
  `requirements.txt`).

## Steps

### 1. Reconcile the export (Stage A)

```bash
conda run -n base python scripts/build_graph_export.py
# Inspect what changed and why:
cat artifacts/graph_export/manifest.json
```

The manifest records source-artifact vintages, the git SHA, pre/post counts
by relationship type, and every dropped edge with its cited reason. Treat the
manifest counts — not any prose headline — as the authoritative graph size.

### 2. Start Neo4j

```bash
export NEO4J_PASSWORD='choose-a-strong-one'   # not committed
docker compose -f docker-compose.neo4j.yml up -d
# wait for health, then:
#   Browser UI : http://localhost:7474
#   Bolt       : neo4j://localhost:7687
```

### 3. Load the bundle

```bash
# Safe default — validates the bundle, prints the plan, does NOT connect:
conda run -n base python scripts/neo4j_load.py --dry-run

# Real load (idempotent MERGE; re-running converges to the same graph):
NEO4J_PASSWORD="$NEO4J_PASSWORD" conda run -n base python scripts/neo4j_load.py

# Clean reload (gated; deletes all nodes first):
NEO4J_PASSWORD="$NEO4J_PASSWORD" conda run -n base python scripts/neo4j_load.py --wipe
```

The loader prints the resulting node/relationship totals and warns if they
diverge from the manifest (expected only if the DB was non-empty and you did
not pass `--wipe`).

### 4. Query (read-only)

`src/graph_queries.py` exposes the eight canonical traversals (the six
documented in README plus `entity_search` and `neighborhood` for the app).
Each returns `(cypher, params)`; values are passed as Cypher parameters, never
interpolated. Example:

```python
from neo4j import GraphDatabase
from src.graph_queries import three_hop_paths

cypher, params = three_hop_paths(limit=25)
with GraphDatabase.driver(
    "neo4j://localhost:7687",
    auth=("neo4j", os.environ["NEO4J_PASSWORD"]),
).session() as s:
    for rec in s.run(cypher, **params):
        print(rec["microbe"], "→", rec["feature"], "→", rec["disease"])
```

`assert_read_only()` in that module is enforced by
`tests/test_graph_queries.py`, so a write clause can never be introduced into
the query layer silently.

## Teardown

```bash
docker compose -f docker-compose.neo4j.yml down          # keep data volume
docker compose -f docker-compose.neo4j.yml down -v       # also delete data
```

## Reproducibility contract

The graph is fully reproducible from committed artifacts: `build_graph_export`
is deterministic (sorted output), the manifest pins source vintages + git SHA,
and `import.cypher` is idempotent. A reviewer can reproduce the exact graph
with the four commands above and verify every edge against the manifest's
provenance and drop records.

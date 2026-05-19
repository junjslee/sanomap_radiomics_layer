"""Read-only canonical graph traversals for the SanoMap Radiomics Layer.

Every function returns ``(cypher, params)`` — a parameterized Cypher string
and its parameter dict. Two deliberate properties:

* **Read-only.** No query contains a write clause. ``assert_read_only`` is
  enforced in tests so a write clause can never be introduced silently.
* **Injection-safe.** User-supplied values are passed as Cypher ``$params``,
  never string-interpolated.

These mirror the six traversals documented in README.md ("Neo4j Graph
Queries") so the application layer exposes exactly the queries the project
already advertises.
"""

from __future__ import annotations

from typing import Any

_WRITE_CLAUSES = (
    "CREATE", "MERGE", "DELETE", "SET ", "REMOVE", "DROP", "DETACH",
    "CALL {", "LOAD CSV", "FOREACH",
)


def assert_read_only(cypher: str) -> None:
    """Raise if *cypher* contains any write/DDL clause. Used by tests."""
    upper = cypher.upper()
    for clause in _WRITE_CLAUSES:
        if clause in upper:
            raise AssertionError(f"non-read-only clause {clause!r} in query: {cypher!r}")


# --------------------------------------------------------------------------- #
# The six canonical traversals
# --------------------------------------------------------------------------- #
def three_hop_paths(limit: int = 200) -> tuple[str, dict[str, Any]]:
    """Microbe -> Feature -> Disease (the intermediary-layer thesis query)."""
    cypher = (
        "MATCH (m:Microbe)-[:CORRELATES_WITH]->(f)-[:ASSOCIATED_WITH]->(d:Disease) "
        "RETURN m.name AS microbe, labels(f)[0] AS feature_type, "
        "f.name AS feature, d.name AS disease "
        "ORDER BY microbe, disease LIMIT $limit"
    )
    return cypher, {"limit": limit}


def features_for_disease(disease_substring: str, limit: int = 200) -> tuple[str, dict[str, Any]]:
    """Which imaging features associate with a given disease (substring match)."""
    cypher = (
        "MATCH (f)-[:ASSOCIATED_WITH]->(d:Disease) "
        "WHERE toLower(d.name) CONTAINS toLower($disease) "
        "RETURN labels(f)[0] AS node_type, f.name AS feature, d.name AS disease "
        "ORDER BY feature LIMIT $limit"
    )
    return cypher, {"disease": disease_substring, "limit": limit}


def signed_microbe_disease(limit: int = 200) -> tuple[str, dict[str, Any]]:
    """Signed microbe->disease edges, strongest net confidence first."""
    cypher = (
        "MATCH (m:Microbe)-[r:POSITIVELY_CORRELATED_WITH|NEGATIVELY_CORRELATED_WITH]->(d:Disease) "
        "RETURN m.name AS microbe, type(r) AS direction, d.name AS disease, "
        "r.confidence AS confidence "
        "ORDER BY confidence DESC LIMIT $limit"
    )
    return cypher, {"limit": limit}


def features_at_location(location: str, limit: int = 200) -> tuple[str, dict[str, Any]]:
    """Radiomic/body-composition features measured at a body location."""
    cypher = (
        "MATCH (f)-[:MEASURED_AT]->(bl:BodyLocation) "
        "WHERE toLower(bl.name) = toLower($location) "
        "RETURN labels(f)[0] AS node_type, f.name AS feature, bl.name AS location "
        "ORDER BY feature LIMIT $limit"
    )
    return cypher, {"location": location, "limit": limit}


def full_modality_chain(limit: int = 200) -> tuple[str, dict[str, Any]]:
    """Microbe -> Feature -> ImagingModality, with the feature's disease."""
    cypher = (
        "MATCH (m:Microbe)-[:CORRELATES_WITH]->(f)-[:ACQUIRED_VIA]->(mod:ImagingModality) "
        "MATCH (f)-[:ASSOCIATED_WITH]->(d:Disease) "
        "RETURN m.name AS microbe, f.name AS feature, "
        "mod.name AS modality, d.name AS disease "
        "ORDER BY microbe LIMIT $limit"
    )
    return cypher, {"limit": limit}


def vision_verified_edges(limit: int = 200) -> tuple[str, dict[str, Any]]:
    """The quantitatively verified vision-track CORRELATES_WITH edges."""
    cypher = (
        "MATCH (m:Microbe)-[r:CORRELATES_WITH]->(f) "
        "WHERE r.evidence CONTAINS 'Vision proposal' "
        "RETURN m.name AS microbe, f.name AS feature, "
        "r.confidence AS confidence, r.pmid AS pmid "
        "ORDER BY confidence DESC LIMIT $limit"
    )
    return cypher, {"limit": limit}


def entity_search(name_substring: str, limit: int = 50) -> tuple[str, dict[str, Any]]:
    """App entry point: find nodes by name substring across all labels."""
    cypher = (
        "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($q) "
        "RETURN labels(n)[0] AS label, n.name AS name "
        "ORDER BY label, name LIMIT $limit"
    )
    return cypher, {"q": name_substring, "limit": limit}


def neighborhood(node_name: str, limit: int = 100) -> tuple[str, dict[str, Any]]:
    """One-hop neighborhood expansion for the explorer UI (read-only)."""
    cypher = (
        "MATCH (n {name: $name})-[r]-(nb) "
        "RETURN labels(n)[0] AS src_label, n.name AS src, type(r) AS rel, "
        "labels(nb)[0] AS nb_label, nb.name AS neighbor "
        "ORDER BY rel, neighbor LIMIT $limit"
    )
    return cypher, {"name": node_name, "limit": limit}


CANONICAL_QUERIES = {
    "three_hop_paths": three_hop_paths,
    "features_for_disease": features_for_disease,
    "signed_microbe_disease": signed_microbe_disease,
    "features_at_location": features_at_location,
    "full_modality_chain": full_modality_chain,
    "vision_verified_edges": vision_verified_edges,
    "entity_search": entity_search,
    "neighborhood": neighborhood,
}

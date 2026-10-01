"""
Spatial Graph — converts DesignRequirements into a NetworkX graph that
encodes rooms as nodes and spatial relationships as weighted edges.

This graph is the machine-readable spatial representation consumed by the
generator, critic, and optimizer.
"""

from __future__ import annotations

import networkx as nx
from typing import Dict, List, Tuple

from models import (
    DesignRequirements,
    SpatialRelationship,
    RelationshipType,
    RoomRequirement,
)


# Edge-weight semantics:
#   NEAR / CONNECTED_TO  →  positive weight (attraction)
#   AWAY_FROM             →  negative weight (repulsion)
WEIGHT_MAP = {
    RelationshipType.NEAR: 1.0,
    RelationshipType.CONNECTED_TO: 2.0,   # stronger than "near"
    RelationshipType.AWAY_FROM: -1.0,
}


def build_spatial_graph(requirements: DesignRequirements) -> nx.Graph:
    """
    Build an undirected weighted graph from design requirements.

    Nodes carry room metadata (type, preferred dimensions).
    Edges carry relationship type and numeric weight.
    """
    G = nx.Graph()

    # Add nodes
    for room in requirements.rooms:
        G.add_node(
            room.name,
            room_type=room.room_type.value,
            min_width=room.min_width,
            min_height=room.min_height,
            preferred_area=room.preferred_area,
        )

    # Add edges
    for rel in requirements.relationships:
        w = WEIGHT_MAP.get(rel.relationship, 0.0)
        G.add_edge(
            rel.room_a,
            rel.room_b,
            relationship=rel.relationship.value,
            weight=w,
        )

    return G


def graph_summary(G: nx.Graph) -> str:
    """Human-readable summary of the spatial graph."""
    lines = [f"Spatial Graph — {G.number_of_nodes()} rooms, {G.number_of_edges()} relationships"]
    lines.append("")
    lines.append("Rooms:")
    for node, data in G.nodes(data=True):
        lines.append(f"  {node}  (type={data.get('room_type')}, area≈{data.get('preferred_area')} sqft)")
    lines.append("")
    lines.append("Relationships:")
    for u, v, data in G.edges(data=True):
        lines.append(f"  {u} → {data.get('relationship', '?')} → {v}")
    return "\n".join(lines)


def get_adjacency_matrix(
    G: nx.Graph,
) -> Tuple[List[str], List[List[float]]]:
    """Return room names and a numeric adjacency matrix (attraction/repulsion)."""
    nodes = list(G.nodes())
    n = len(nodes)
    mat = [[0.0] * n for _ in range(n)]
    idx = {name: i for i, name in enumerate(nodes)}
    for u, v, data in G.edges(data=True):
        w = data.get("weight", 0.0)
        i, j = idx[u], idx[v]
        mat[i][j] = w
        mat[j][i] = w
    return nodes, mat

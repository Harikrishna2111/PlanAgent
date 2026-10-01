"""
Constraint-Based Procedural Floor-Plan Generator.

Generates multiple candidate 2D floor plans by placing rooms on a grid inside
the plot boundary.  Uses a strip-packing heuristic with spatial-relationship
awareness to produce diverse candidates.

This is a scientifically defensible procedural generator suitable for the 50%
milestone.  The generation interface is modular — a learned generative model
(e.g. HouseGAN++) can replace this module later by implementing the same
`generate()` function signature.
"""

from __future__ import annotations

import copy
import math
import random
from typing import List, Optional, Tuple

import networkx as nx

from models import (
    DesignRequirements,
    FloorPlan,
    Room,
    RoomRequirement,
    RoomType,
)
from spatial.graph import build_spatial_graph


# ---------------------------------------------------------------------------
# Default room sizing (width, height in ft) — used when preferred_area > 0
# ---------------------------------------------------------------------------

def _size_room(req: RoomRequirement) -> Tuple[float, float]:
    """Determine (width, height) for a room from its requirement."""
    if req.min_width > 0 and req.min_height > 0:
        return req.min_width, req.min_height
    if req.preferred_area > 0:
        side = math.sqrt(req.preferred_area)
        # Slightly rectangular
        return round(side * 0.9, 1), round(side * 1.1, 1)
    return 10.0, 10.0


# ---------------------------------------------------------------------------
# Grid-based strip packing generator
# ---------------------------------------------------------------------------

class ProceduralGenerator:
    """
    Places rooms row-by-row using a strip-packing heuristic.
    Produces `num_candidates` diverse layouts by varying room order and
    placement jitter.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def generate(
        self,
        requirements: DesignRequirements,
        num_candidates: int = 5,
    ) -> List[FloorPlan]:
        """Generate multiple candidate floor plans."""
        graph = build_spatial_graph(requirements)
        candidates: List[FloorPlan] = []

        for i in range(num_candidates):
            plan = self._generate_one(requirements, graph, variation=i)
            if plan is not None:
                candidates.append(plan)

        return candidates

    # ---- internal ---------------------------------------------------------

    def _generate_one(
        self,
        req: DesignRequirements,
        graph: nx.Graph,
        variation: int = 0,
    ) -> Optional[FloorPlan]:
        """Generate a single candidate floor plan."""
        pw, ph = req.plot_width, req.plot_height

        # Size every room
        sized: List[Tuple[RoomRequirement, float, float]] = []
        for room_req in req.rooms:
            w, h = _size_room(room_req)
            # Clamp to plot
            w = min(w, pw)
            h = min(h, ph)
            sized.append((room_req, w, h))

        # Order rooms — use different strategies for diversity
        if variation == 0:
            # Largest first (area descending)
            sized.sort(key=lambda t: t[1] * t[2], reverse=True)
        elif variation == 1:
            # Prioritise entrance / living at front
            def _priority(t):
                if t[0].room_type == RoomType.ENTRANCE:
                    return 0
                if t[0].room_type == RoomType.LIVING_ROOM:
                    return 1
                return 10
            sized.sort(key=_priority)
        elif variation == 2:
            # Graph-based: rooms with more constraints first
            def _degree(t):
                return -graph.degree(t[0].name) if t[0].name in graph else 0
            sized.sort(key=_degree)
        else:
            # Random shuffle for diversity
            self.rng.shuffle(sized)

        # Place rooms using strip-packing with spatial awareness
        placed_rooms: List[Room] = []
        for room_req, w, h in sized:
            pos = self._find_position(
                room_req, w, h, pw, ph, placed_rooms, graph, req.relationships
            )
            if pos is None:
                # Try rotated
                pos = self._find_position(
                    room_req, h, w, pw, ph, placed_rooms, graph, req.relationships
                )
                if pos is not None:
                    w, h = h, w
            if pos is None:
                # Force-place in any free spot (shrink if needed)
                pos, w, h = self._force_place(w, h, pw, ph, placed_rooms)
            if pos is not None:
                placed_rooms.append(Room(
                    name=room_req.name,
                    room_type=room_req.room_type,
                    x=pos[0], y=pos[1],
                    width=w, height=h,
                ))

        if not placed_rooms:
            return None

        return FloorPlan(
            plot_width=pw,
            plot_height=ph,
            rooms=placed_rooms,
        )

    def _find_position(
        self,
        room_req: RoomRequirement,
        w: float, h: float,
        pw: float, ph: float,
        placed: List[Room],
        graph: nx.Graph,
        relationships,
    ) -> Optional[Tuple[float, float]]:
        """Find a valid (x, y) for the room, preferring positions that
        satisfy spatial relationships."""
        step = 1.0  # ft grid resolution
        best_pos = None
        best_score = -float("inf")

        # Generate candidate positions on a grid
        xs = [i * step for i in range(int((pw - w) / step) + 1)]
        ys = [j * step for j in range(int((ph - h) / step) + 1)]

        # Subsample for speed when many positions
        if len(xs) * len(ys) > 500:
            xs = [xs[i] for i in range(0, len(xs), max(1, len(xs) // 20))]
            ys = [ys[j] for j in range(0, len(ys), max(1, len(ys) // 20))]
            # Add some random jitter positions
            for _ in range(10):
                xs.append(self.rng.uniform(0, max(0.1, pw - w)))
                ys.append(self.rng.uniform(0, max(0.1, ph - h)))

        for x in xs:
            for y in ys:
                candidate = Room(
                    name=room_req.name,
                    room_type=room_req.room_type,
                    x=x, y=y, width=w, height=h,
                )
                # Check bounds
                if candidate.right > pw + 0.01 or candidate.top > ph + 0.01:
                    continue
                # Check overlap
                if any(candidate.overlaps(p) for p in placed):
                    continue
                # Score based on spatial relationships
                score = self._position_score(candidate, placed, graph)
                if score > best_score:
                    best_score = score
                    best_pos = (x, y)

        return best_pos

    def _position_score(
        self, candidate: Room, placed: List[Room], graph: nx.Graph
    ) -> float:
        """Score a candidate position based on spatial graph."""
        score = 0.0
        for p in placed:
            if graph.has_edge(candidate.name, p.name):
                edge_data = graph.edges[candidate.name, p.name]
                weight = edge_data.get("weight", 0.0)
                dist = candidate.distance_to(p)
                if weight > 0:
                    # Attraction — closer is better
                    score -= dist * weight * 0.1
                    if candidate.shares_edge(p):
                        score += weight * 5.0
                else:
                    # Repulsion — farther is better
                    score += dist * abs(weight) * 0.1
        return score

    def _force_place(
        self,
        w: float, h: float,
        pw: float, ph: float,
        placed: List[Room],
    ) -> Tuple[Optional[Tuple[float, float]], float, float]:
        """Shrink room if needed and place it wherever it fits."""
        for shrink in [1.0, 0.8, 0.6, 0.5]:
            sw, sh = w * shrink, h * shrink
            step = 2.0
            for x in [i * step for i in range(int((pw - sw) / step) + 1)]:
                for y in [j * step for j in range(int((ph - sh) / step) + 1)]:
                    candidate = Room("tmp", RoomType.UTILITY, x, y, sw, sh)
                    if candidate.right <= pw + 0.01 and candidate.top <= ph + 0.01:
                        if not any(candidate.overlaps(p) for p in placed):
                            return (x, y), sw, sh
        return None, w, h


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_floor_plans(
    requirements: DesignRequirements,
    num_candidates: int = 5,
    seed: Optional[int] = 42,
) -> List[FloorPlan]:
    """Top-level convenience function."""
    gen = ProceduralGenerator(seed=seed)
    return gen.generate(requirements, num_candidates=num_candidates)

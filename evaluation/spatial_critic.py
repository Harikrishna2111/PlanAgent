"""
Spatial Critic — evaluates candidate floor plans against structured constraints.

Produces a deterministic, interpretable numerical score using geometric
calculations.  No LLM is used for evaluation.

Scoring dimensions:
  1. Room completeness   — are all required rooms present?
  2. Room dimensions     — do rooms meet minimum size requirements?
  3. Overlap penalty     — do rooms overlap each other?
  4. Boundary compliance — are all rooms inside the plot?
  5. Adjacency           — are "near" rooms actually adjacent?
  6. Connectivity        — do "connected_to" rooms share an edge?
  7. Separation          — are "away_from" rooms sufficiently separated?
  8. Space utilisation   — what fraction of the plot is used?

Each dimension yields a score in [0, 1].  The final score is a weighted sum,
also in [0, 1].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from models import (
    DesignRequirements,
    FloorPlan,
    Room,
    RelationshipType,
    SpatialRelationship,
)


# ---------------------------------------------------------------------------
# Default scoring weights (configurable)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: Dict[str, float] = {
    "room_completeness":   0.20,
    "room_dimensions":     0.10,
    "overlap_penalty":     0.20,
    "boundary_compliance": 0.10,
    "adjacency":           0.15,
    "connectivity":        0.10,
    "separation":          0.05,
    "space_utilization":   0.10,
}


# ---------------------------------------------------------------------------
# Violation record
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    category: str
    description: str
    severity: float = 1.0   # 0..1

    def __repr__(self):
        return f"Violation({self.category}: {self.description})"


# ---------------------------------------------------------------------------
# Critic
# ---------------------------------------------------------------------------

@dataclass
class EvaluationResult:
    """Detailed result of evaluating a floor plan."""
    total_score: float = 0.0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    violations: List[Violation] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [f"Total Score: {self.total_score:.4f}"]
        lines.append("Dimension Scores:")
        for k, v in self.dimension_scores.items():
            w = self.weights.get(k, 0)
            lines.append(f"  {k:25s}  score={v:.3f}  weight={w:.2f}  weighted={v*w:.4f}")
        if self.violations:
            lines.append(f"\nViolations ({len(self.violations)}):")
            for v in self.violations:
                lines.append(f"  [{v.category}] {v.description}")
        else:
            lines.append("\nNo violations.")
        return "\n".join(lines)


class SpatialCritic:
    """Deterministic constraint evaluator for floor plans."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    def evaluate(
        self,
        plan: FloorPlan,
        requirements: DesignRequirements,
    ) -> EvaluationResult:
        """Evaluate a floor plan against requirements. Returns an EvaluationResult."""
        result = EvaluationResult(weights=self.weights.copy())

        # 1. Room completeness
        s, vs = self._check_completeness(plan, requirements)
        result.dimension_scores["room_completeness"] = s
        result.violations.extend(vs)

        # 2. Room dimensions
        s, vs = self._check_dimensions(plan, requirements)
        result.dimension_scores["room_dimensions"] = s
        result.violations.extend(vs)

        # 3. Overlap penalty
        s, vs = self._check_overlaps(plan)
        result.dimension_scores["overlap_penalty"] = s
        result.violations.extend(vs)

        # 4. Boundary compliance
        s, vs = self._check_boundary(plan)
        result.dimension_scores["boundary_compliance"] = s
        result.violations.extend(vs)

        # 5. Adjacency (near)
        s, vs = self._check_adjacency(plan, requirements)
        result.dimension_scores["adjacency"] = s
        result.violations.extend(vs)

        # 6. Connectivity (connected_to)
        s, vs = self._check_connectivity(plan, requirements)
        result.dimension_scores["connectivity"] = s
        result.violations.extend(vs)

        # 7. Separation (away_from)
        s, vs = self._check_separation(plan, requirements)
        result.dimension_scores["separation"] = s
        result.violations.extend(vs)

        # 8. Space utilization
        s, vs = self._check_utilization(plan)
        result.dimension_scores["space_utilization"] = s
        result.violations.extend(vs)

        # Weighted total
        total = 0.0
        for dim, score in result.dimension_scores.items():
            total += score * self.weights.get(dim, 0.0)
        result.total_score = total

        # Attach to plan
        plan.score = result.total_score
        plan.score_details = result.dimension_scores.copy()

        return result

    # ---- dimension evaluators ---------------------------------------------

    def _check_completeness(
        self, plan: FloorPlan, req: DesignRequirements
    ) -> Tuple[float, List[Violation]]:
        violations = []
        required_names = {r.name for r in req.rooms}
        placed_names = {r.name for r in plan.rooms}
        missing = required_names - placed_names
        for m in missing:
            violations.append(Violation("room_completeness", f"Missing room: {m}"))
        if not required_names:
            return 1.0, violations
        score = len(placed_names & required_names) / len(required_names)
        return score, violations

    def _check_dimensions(
        self, plan: FloorPlan, req: DesignRequirements
    ) -> Tuple[float, List[Violation]]:
        violations = []
        req_map = {r.name: r for r in req.rooms}
        scores = []
        for room in plan.rooms:
            rr = req_map.get(room.name)
            if rr is None:
                continue
            dim_ok = True
            if rr.min_width > 0 and room.width < rr.min_width * 0.8:
                violations.append(Violation(
                    "room_dimensions",
                    f"{room.name}: width {room.width:.1f} < min {rr.min_width:.1f}",
                ))
                dim_ok = False
            if rr.min_height > 0 and room.height < rr.min_height * 0.8:
                violations.append(Violation(
                    "room_dimensions",
                    f"{room.name}: height {room.height:.1f} < min {rr.min_height:.1f}",
                ))
                dim_ok = False
            scores.append(1.0 if dim_ok else 0.5)
        return (sum(scores) / len(scores)) if scores else 1.0, violations

    def _check_overlaps(
        self, plan: FloorPlan
    ) -> Tuple[float, List[Violation]]:
        violations = []
        total_overlap = 0.0
        rooms = plan.rooms
        for i in range(len(rooms)):
            for j in range(i + 1, len(rooms)):
                ov = rooms[i].overlap_area(rooms[j])
                if ov > 0.01:
                    violations.append(Violation(
                        "overlap",
                        f"{rooms[i].name} overlaps {rooms[j].name} by {ov:.1f} sqft",
                    ))
                    total_overlap += ov
        plot_area = plan.plot_width * plan.plot_height
        penalty = min(total_overlap / max(plot_area * 0.1, 1), 1.0)
        return 1.0 - penalty, violations

    def _check_boundary(
        self, plan: FloorPlan
    ) -> Tuple[float, List[Violation]]:
        violations = []
        ok_count = 0
        for room in plan.rooms:
            inside = (
                room.x >= -0.01
                and room.y >= -0.01
                and room.right <= plan.plot_width + 0.01
                and room.top <= plan.plot_height + 0.01
            )
            if inside:
                ok_count += 1
            else:
                violations.append(Violation(
                    "boundary",
                    f"{room.name} extends outside plot boundary",
                ))
        return (ok_count / len(plan.rooms)) if plan.rooms else 1.0, violations

    def _check_adjacency(
        self, plan: FloorPlan, req: DesignRequirements
    ) -> Tuple[float, List[Violation]]:
        """Check 'near' relationships — rooms should be adjacent or close."""
        near_rels = [r for r in req.relationships if r.relationship == RelationshipType.NEAR]
        if not near_rels:
            return 1.0, []
        violations = []
        satisfied = 0
        for rel in near_rels:
            ra = plan.get_room(rel.room_a)
            rb = plan.get_room(rel.room_b)
            if ra is None or rb is None:
                continue
            # "Near" is satisfied if rooms share an edge or centres are within
            # 1.5x the sum of their half-widths
            if ra.shares_edge(rb, tolerance=1.0):
                satisfied += 1
            elif ra.distance_to(rb) < (ra.width + rb.width) / 2 + 5:
                satisfied += 0.5
            else:
                violations.append(Violation(
                    "adjacency",
                    f"{rel.room_a} should be near {rel.room_b} "
                    f"(dist={ra.distance_to(rb):.1f} ft)",
                ))
        return satisfied / len(near_rels) if near_rels else 1.0, violations

    def _check_connectivity(
        self, plan: FloorPlan, req: DesignRequirements
    ) -> Tuple[float, List[Violation]]:
        """Check 'connected_to' relationships — rooms must share an edge."""
        conn_rels = [r for r in req.relationships if r.relationship == RelationshipType.CONNECTED_TO]
        if not conn_rels:
            return 1.0, []
        violations = []
        satisfied = 0
        for rel in conn_rels:
            ra = plan.get_room(rel.room_a)
            rb = plan.get_room(rel.room_b)
            if ra is None or rb is None:
                continue
            if ra.shares_edge(rb, tolerance=1.0):
                satisfied += 1
            else:
                violations.append(Violation(
                    "connectivity",
                    f"{rel.room_a} should be connected to {rel.room_b}",
                ))
        return satisfied / len(conn_rels) if conn_rels else 1.0, violations

    def _check_separation(
        self, plan: FloorPlan, req: DesignRequirements
    ) -> Tuple[float, List[Violation]]:
        """Check 'away_from' relationships — rooms should be far apart."""
        away_rels = [r for r in req.relationships if r.relationship == RelationshipType.AWAY_FROM]
        if not away_rels:
            return 1.0, []
        violations = []
        satisfied = 0
        diag = (plan.plot_width ** 2 + plan.plot_height ** 2) ** 0.5
        threshold = diag * 0.3  # at least 30% of plot diagonal apart
        for rel in away_rels:
            ra = plan.get_room(rel.room_a)
            rb = plan.get_room(rel.room_b)
            if ra is None or rb is None:
                continue
            dist = ra.distance_to(rb)
            if dist >= threshold:
                satisfied += 1
            else:
                violations.append(Violation(
                    "separation",
                    f"{rel.room_a} should be away from {rel.room_b} "
                    f"(dist={dist:.1f} < threshold={threshold:.1f})",
                ))
                satisfied += dist / threshold
        return satisfied / len(away_rels) if away_rels else 1.0, violations

    def _check_utilization(
        self, plan: FloorPlan
    ) -> Tuple[float, List[Violation]]:
        violations = []
        util = plan.utilization
        # Penalise both under- and over-utilisation (target ~60-85%)
        if util < 0.4:
            violations.append(Violation(
                "utilization",
                f"Low space utilization: {util:.1%}",
                severity=0.5,
            ))
        elif util > 0.95:
            violations.append(Violation(
                "utilization",
                f"Extremely high utilization: {util:.1%} — may lack circulation space",
                severity=0.3,
            ))
        # Score: ramp up to 1.0 at 70%, stay 1.0 up to 90%, decrease after
        if util <= 0.7:
            score = util / 0.7
        elif util <= 0.9:
            score = 1.0
        else:
            score = max(0, 1.0 - (util - 0.9) / 0.2)
        return score, violations

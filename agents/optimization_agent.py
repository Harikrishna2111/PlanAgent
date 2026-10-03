"""
Optimization Agent — iteratively improves a floor plan using Simulated Annealing.

Loop:
  1. Evaluate current layout → score + violations
  2. Propose a modification — either a targeted repair of the weakest
     constraint dimension, or a random move / resize / swap / expand
  3. Evaluate modified layout
  4. Accept/reject based on SA criterion
  5. Repeat until quality stabilises (no improvement for `patience`
     iterations) or the iteration budget is used up
  6. Return best layout found

This demonstrates the Generate → Evaluate → Improve cycle required by the
project specification.
"""

from __future__ import annotations

import copy
import math
import random
from typing import Dict, List, Optional, Tuple

from models import (
    DesignRequirements,
    FloorPlan,
    RelationshipType,
    Room,
)
from evaluation.spatial_critic import SpatialCritic, EvaluationResult

# Dimensions a geometric move can repair (room_completeness cannot be fixed
# by moving rooms, so it is never targeted).
_REPAIRABLE_DIMENSIONS = (
    "overlap_penalty",
    "boundary_compliance",
    "room_dimensions",
    "adjacency",
    "connectivity",
    "separation",
    "space_utilization",
)


# ---------------------------------------------------------------------------
# Modification operators
# ---------------------------------------------------------------------------

def _move_room(
    plan: FloorPlan, rng: random.Random, max_shift: float = 3.0
) -> FloorPlan:
    """Move a random room by a small delta."""
    new = copy.deepcopy(plan)
    if not new.rooms:
        return new
    room = rng.choice(new.rooms)
    dx = rng.uniform(-max_shift, max_shift)
    dy = rng.uniform(-max_shift, max_shift)
    room.x = max(0, min(room.x + dx, new.plot_width - room.width))
    room.y = max(0, min(room.y + dy, new.plot_height - room.height))
    return new


def _resize_room(
    plan: FloorPlan, rng: random.Random, max_delta: float = 2.0
) -> FloorPlan:
    """Slightly resize a random room, biased toward expansion when utilization is low."""
    new = copy.deepcopy(plan)
    if not new.rooms:
        return new
    room = rng.choice(new.rooms)
    # Bias toward expansion when utilization is low
    if new.utilization < 0.6:
        dw = rng.uniform(0, max_delta * 2)
        dh = rng.uniform(0, max_delta * 2)
    else:
        dw = rng.uniform(-max_delta, max_delta)
        dh = rng.uniform(-max_delta, max_delta)
    room.width = max(3, min(room.width + dw, new.plot_width - room.x))
    room.height = max(3, min(room.height + dh, new.plot_height - room.y))
    return new


def _expand_room(plan: FloorPlan, rng: random.Random) -> FloorPlan:
    """Expand a random room to fill adjacent empty space without overlapping others."""
    new = copy.deepcopy(plan)
    if not new.rooms:
        return new
    room = rng.choice(new.rooms)
    others = [r for r in new.rooms if r.name != room.name]

    # Try expanding in each direction
    directions = ["right", "down", "left", "up"]
    rng.shuffle(directions)
    step = 1.0

    for d in directions[:2]:  # Try 2 random directions
        for _ in range(5):  # Up to 5 steps
            old_x, old_y, old_w, old_h = room.x, room.y, room.width, room.height
            if d == "right":
                room.width += step
            elif d == "down":
                room.height += step
            elif d == "left":
                room.x -= step
                room.width += step
            elif d == "up":
                room.y -= step
                room.height += step

            # Check bounds
            if room.x < 0 or room.y < 0 or room.right > new.plot_width or room.top > new.plot_height:
                room.x, room.y, room.width, room.height = old_x, old_y, old_w, old_h
                break
            # Check overlaps
            if any(room.overlaps(o) for o in others):
                room.x, room.y, room.width, room.height = old_x, old_y, old_w, old_h
                break
    return new


def _swap_rooms(plan: FloorPlan, rng: random.Random) -> FloorPlan:
    """Swap positions of two random rooms (keeping sizes)."""
    new = copy.deepcopy(plan)
    if len(new.rooms) < 2:
        return new
    a, b = rng.sample(range(len(new.rooms)), 2)
    ra, rb = new.rooms[a], new.rooms[b]
    # Swap positions
    ra.x, rb.x = rb.x, ra.x
    ra.y, rb.y = rb.y, ra.y
    # Clamp to plot
    for room in [ra, rb]:
        room.x = max(0, min(room.x, new.plot_width - room.width))
        room.y = max(0, min(room.y, new.plot_height - room.height))
    return new


def _nudge_toward_partner(
    plan: FloorPlan, rng: random.Random, requirements: DesignRequirements
) -> FloorPlan:
    """Move a room toward a room it should be near (informed by violations)."""
    from models import RelationshipType
    new = copy.deepcopy(plan)
    near_rels = [r for r in requirements.relationships
                 if r.relationship == RelationshipType.NEAR
                 or r.relationship == RelationshipType.CONNECTED_TO]
    if not near_rels:
        return _move_room(plan, rng)
    rel = rng.choice(near_rels)
    ra = new.get_room(rel.room_a)
    rb = new.get_room(rel.room_b)
    if ra is None or rb is None:
        return _move_room(plan, rng)
    # Move ra toward rb
    target = rng.choice([ra, rb])
    other = rb if target is ra else ra
    dx = (other.center[0] - target.center[0]) * rng.uniform(0.1, 0.4)
    dy = (other.center[1] - target.center[1]) * rng.uniform(0.1, 0.4)
    target.x = max(0, min(target.x + dx, new.plot_width - target.width))
    target.y = max(0, min(target.y + dy, new.plot_height - target.height))
    return new


# ---------------------------------------------------------------------------
# Targeted repair — "identify weak areas and modify them"
# ---------------------------------------------------------------------------

def pick_weakest_dimension(
    evaluation: EvaluationResult, rng: random.Random
) -> Optional[str]:
    """Choose a repairable dimension, weighted by how much score it is losing.

    Shortfall = weight × (1 − score).  Sampling in proportion to shortfall
    focuses on the lowest-scoring constraints without getting stuck on one
    that cannot be improved further.
    """
    shortfalls = {
        dim: evaluation.weights.get(dim, 0.0) * (1.0 - evaluation.dimension_scores.get(dim, 1.0))
        for dim in _REPAIRABLE_DIMENSIONS
    }
    shortfalls = {d: s for d, s in shortfalls.items() if s > 1e-6}
    if not shortfalls:
        return None
    dims = list(shortfalls)
    return rng.choices(dims, weights=[shortfalls[d] for d in dims], k=1)[0]


def _clamp(room: Room, plan: FloorPlan) -> None:
    room.width = min(room.width, plan.plot_width)
    room.height = min(room.height, plan.plot_height)
    room.x = max(0, min(room.x, plan.plot_width - room.width))
    room.y = max(0, min(room.y, plan.plot_height - room.height))


def _snap_adjacent(target: Room, other: Room, plan: FloorPlan) -> None:
    """Move `target` so it shares an edge with `other`, choosing the side of
    `other` that collides least with the remaining rooms, then the closest one."""
    def along_wall(t_start, t_len, o_start, o_len):
        # Keep target's position along the shared wall if it already overlaps
        # it, otherwise slide it to the nearest end (at least 1 ft of contact).
        lo, hi = o_start - t_len + 1.0, o_start + o_len - 1.0
        return max(lo, min(t_start, hi))

    ys = along_wall(target.y, target.height, other.y, other.height)
    xs = along_wall(target.x, target.width, other.x, other.width)
    options = [
        (other.x - target.width, ys),   # left of other
        (other.right, ys),              # right of other
        (xs, other.y - target.height),  # below other
        (xs, other.top),                # above other
    ]
    rest = [r for r in plan.rooms if r is not target and r is not other]
    old_x, old_y = target.x, target.y

    def cost(pos):
        target.x, target.y = pos
        _clamp(target, plan)
        collision = sum(target.overlap_area(r) for r in rest) + target.overlap_area(other)
        return (round(collision, 2), (target.x - old_x) ** 2 + (target.y - old_y) ** 2)

    best = min(options, key=cost)
    target.x, target.y = best
    _clamp(target, plan)


def _repair_overlap(plan: FloorPlan, rng: random.Random, req: DesignRequirements) -> bool:
    pairs = [(a, b) for i, a in enumerate(plan.rooms) for b in plan.rooms[i + 1:]
             if a.overlap_area(b) > 0.01]
    if not pairs:
        return False
    a, b = rng.choice(pairs)
    mover, fixed = (a, b) if rng.random() < 0.5 else (b, a)
    # Push out along the axis that needs the smaller shift
    ox = min(mover.right, fixed.right) - max(mover.x, fixed.x)
    oy = min(mover.top, fixed.top) - max(mover.y, fixed.y)
    if ox < oy:
        mover.x += ox if mover.center[0] >= fixed.center[0] else -ox
    else:
        mover.y += oy if mover.center[1] >= fixed.center[1] else -oy
    _clamp(mover, plan)
    return True


def _trimmed_variants(plan: FloorPlan, i: int, j: int) -> List[FloorPlan]:
    """Ways to remove the overlap between rooms i and j by trimming one wall."""
    variants = []
    for mover_idx, fixed_idx in ((i, j), (j, i)):
        for axis in ("x", "y"):
            new = copy.deepcopy(plan)
            mover, fixed = new.rooms[mover_idx], new.rooms[fixed_idx]
            if axis == "x":
                ov = min(mover.right, fixed.right) - max(mover.x, fixed.x)
                if ov >= mover.width - 3:
                    continue
                if mover.center[0] >= fixed.center[0]:
                    mover.x += ov
                mover.width -= ov
            else:
                ov = min(mover.top, fixed.top) - max(mover.y, fixed.y)
                if ov >= mover.height - 3:
                    continue
                if mover.center[1] >= fixed.center[1]:
                    mover.y += ov
                mover.height -= ov
            variants.append(new)
    return variants


def _reconnect_variants(plan: FloorPlan) -> List[FloorPlan]:
    """Ways to reconnect rooms that cannot be reached from the entrance:
    snap an unreachable room against its nearest reachable room, or vice versa."""
    entrance = next((r for r in plan.rooms if r.room_type.value == "entrance"), None)
    if entrance is None:
        return []
    reached, frontier = {entrance.name}, [entrance]
    while frontier:
        room = frontier.pop()
        for other in plan.rooms:
            if other.name not in reached and room.shares_edge(other, tolerance=1.0):
                reached.add(other.name)
                frontier.append(other)

    variants = []
    for idx, room in enumerate(plan.rooms):
        if room.name in reached:
            continue
        near_idx = min(
            (k for k, r in enumerate(plan.rooms) if r.name in reached),
            key=lambda k: room.distance_to(plan.rooms[k]),
        )
        for mover_idx, anchor_idx in ((idx, near_idx), (near_idx, idx)):
            new = copy.deepcopy(plan)
            _snap_adjacent(new.rooms[mover_idx], new.rooms[anchor_idx], new)
            variants.append(new)
    return variants


def _polish(
    plan: FloorPlan, requirements: DesignRequirements, critic: SpatialCritic
) -> Tuple[FloorPlan, EvaluationResult]:
    """Clear leftover overlaps and circulation breaks that the weighted score
    barely penalises.  A change is kept only if it reduces the number of
    violations without lowering the score."""
    best = plan
    best_eval = critic.evaluate(best, requirements)
    for _ in range(len(plan.rooms) ** 2):
        pairs = [(i, j) for i in range(len(best.rooms)) for j in range(i + 1, len(best.rooms))
                 if best.rooms[i].overlap_area(best.rooms[j]) > 0.01]
        candidates = [c for i, j in pairs for c in _trimmed_variants(best, i, j)]
        candidates += _reconnect_variants(best)
        improved = False
        for cand in candidates:
            ev = critic.evaluate(cand, requirements)
            if ev.total_score >= best_eval.total_score - 1e-9 and len(ev.violations) < len(best_eval.violations):
                best, best_eval, improved = cand, ev, True
                break
        if not improved:
            break
    return best, best_eval


def _repair_boundary(plan: FloorPlan, rng: random.Random, req: DesignRequirements) -> bool:
    for room in plan.rooms:
        _clamp(room, plan)
    return True


def _repair_dimensions(plan: FloorPlan, rng: random.Random, req: DesignRequirements) -> bool:
    req_map = {r.name: r for r in req.rooms}
    small = [room for room in plan.rooms if room.name in req_map and (
        room.width < req_map[room.name].min_width * 0.8
        or room.height < req_map[room.name].min_height * 0.8)]
    if not small:
        return False
    room = rng.choice(small)
    rr = req_map[room.name]
    room.width = max(room.width, rr.min_width)
    room.height = max(room.height, rr.min_height)
    _clamp(room, plan)
    return True


def _repair_relationship(
    plan: FloorPlan, rng: random.Random, req: DesignRequirements, rel_type: RelationshipType
) -> bool:
    broken = []
    for rel in req.relationships:
        if rel.relationship != rel_type:
            continue
        ra, rb = plan.get_room(rel.room_a), plan.get_room(rel.room_b)
        if ra is not None and rb is not None and not ra.shares_edge(rb, tolerance=1.0):
            broken.append((ra, rb))
    if not broken:
        return False
    ra, rb = rng.choice(broken)
    target, other = (ra, rb) if rng.random() < 0.5 else (rb, ra)
    _snap_adjacent(target, other, plan)
    return True


def _repair_separation(plan: FloorPlan, rng: random.Random, req: DesignRequirements) -> bool:
    threshold = 0.3 * (plan.plot_width ** 2 + plan.plot_height ** 2) ** 0.5
    close = []
    for rel in req.relationships:
        if rel.relationship != RelationshipType.AWAY_FROM:
            continue
        ra, rb = plan.get_room(rel.room_a), plan.get_room(rel.room_b)
        if ra is not None and rb is not None and ra.distance_to(rb) < threshold:
            close.append((ra, rb))
    if not close:
        return False
    ra, rb = rng.choice(close)
    mover, fixed = (ra, rb) if rng.random() < 0.5 else (rb, ra)
    dx = mover.center[0] - fixed.center[0]
    dy = mover.center[1] - fixed.center[1]
    norm = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    step = (threshold - norm) * rng.uniform(0.3, 1.0)
    mover.x += dx / norm * step
    mover.y += dy / norm * step
    _clamp(mover, plan)
    return True


def _repair_utilization(plan: FloorPlan, rng: random.Random, req: DesignRequirements) -> bool:
    if plan.utilization < 0.7:
        plan.rooms = _expand_room(plan, rng).rooms
    else:
        room = rng.choice(plan.rooms)
        room.width = max(3, room.width - 1.0)
        room.height = max(3, room.height - 1.0)
    return True


_REPAIRS = {
    "overlap_penalty": _repair_overlap,
    "boundary_compliance": _repair_boundary,
    "room_dimensions": _repair_dimensions,
    "adjacency": lambda p, rng, req: _repair_relationship(p, rng, req, RelationshipType.NEAR),
    "connectivity": lambda p, rng, req: _repair_relationship(p, rng, req, RelationshipType.CONNECTED_TO),
    "separation": _repair_separation,
    "space_utilization": _repair_utilization,
}


def _targeted_repair(
    plan: FloorPlan,
    rng: random.Random,
    requirements: DesignRequirements,
    evaluation: EvaluationResult,
) -> Tuple[FloorPlan, Optional[str]]:
    """Repair the weakest constraint dimension of `plan`.

    Returns (modified_plan, targeted_dimension). Falls back to a random move
    when no repairable dimension is below its maximum.
    """
    dim = pick_weakest_dimension(evaluation, rng) if plan.rooms else None
    if dim is None:
        return _move_room(plan, rng), None
    new = copy.deepcopy(plan)
    if not _REPAIRS[dim](new, rng, requirements):
        return _move_room(plan, rng), None
    return new, dim


# ---------------------------------------------------------------------------
# Simulated Annealing optimizer
# ---------------------------------------------------------------------------

class SimulatedAnnealingOptimizer:
    """
    Two-phase optimization of floor plans against spatial constraints:
    Phase 1: Greedy room expansion to improve space utilization
    Phase 2: SA refinement — each step either repairs the weakest constraint
             dimension reported by the critic, or applies a random perturbation
             to keep exploring.  Every proposal is re-evaluated by the critic.
    Phase 3: Polish — trim overlapping walls and reconnect rooms cut off
             from the entrance, without lowering the score
    """

    def __init__(
        self,
        max_iterations: int = 500,
        initial_temp: float = 0.15,
        cooling_rate: float = 0.997,
        seed: Optional[int] = 42,
        patience: int = 150,
    ):
        self.max_iterations = max_iterations
        self.patience = patience
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
        self.rng = random.Random(seed)
        self.critic = SpatialCritic()
        self.history: List[Dict] = []

    def _greedy_expand(self, plan: FloorPlan, requirements: DesignRequirements) -> FloorPlan:
        """Phase 1: Greedily expand each room to fill empty space.
        Rooms are capped at 3x their preferred area to stay realistic."""
        new = copy.deepcopy(plan)
        step = 1.0

        # Build max-area lookup from requirements
        max_area = {}
        for rr in requirements.rooms:
            max_area[rr.name] = max(rr.preferred_area * 3, rr.min_width * rr.min_height * 3)

        improved = True
        iterations = 0
        while improved and iterations < 50:
            improved = False
            iterations += 1
            for room in new.rooms:
                area_limit = max_area.get(room.name, room.area * 3)
                others = [r for r in new.rooms if r.name != room.name]
                for direction in ["right", "down", "left", "up"]:
                    old_x, old_y, old_w, old_h = room.x, room.y, room.width, room.height
                    if direction == "right":
                        room.width += step
                    elif direction == "down":
                        room.height += step
                    elif direction == "left":
                        room.x -= step
                        room.width += step
                    elif direction == "up":
                        room.y -= step
                        room.height += step
                    # Validate: bounds + no overlap + area cap
                    ok = (room.x >= 0 and room.y >= 0
                           and room.right <= new.plot_width + 0.01
                           and room.top <= new.plot_height + 0.01
                           and room.area <= area_limit
                           and not any(room.overlaps(o) for o in others))
                    if ok:
                        improved = True
                    else:
                        room.x, room.y, room.width, room.height = old_x, old_y, old_w, old_h
        return new

    def optimize(
        self,
        plan: FloorPlan,
        requirements: DesignRequirements,
        verbose: bool = False,
    ) -> Tuple[FloorPlan, EvaluationResult, List[Dict]]:
        """
        Run two-phase optimization.

        Returns:
            (best_plan, best_eval, history)
        """
        self.history = []

        # Phase 1: Greedy expansion
        if verbose:
            print("  Phase 1: Greedy room expansion...")
        current = self._greedy_expand(plan, requirements)
        current_eval = self.critic.evaluate(current, requirements)
        current_score = current_eval.total_score

        if verbose:
            print(f"  After expansion: score={current_score:.4f}  "
                  f"utilization={current.utilization:.1%}  "
                  f"violations={len(current_eval.violations)}")

        best = copy.deepcopy(current)
        best_eval = copy.deepcopy(current_eval)
        best_score = current_score

        # Phase 2: SA refinement
        if verbose:
            print(f"  Phase 2: SA refinement ({self.max_iterations} iterations)...")

        temp = self.initial_temp
        operators = [
            lambda p: _move_room(p, self.rng, max_shift=2.0),
            lambda p: _resize_room(p, self.rng, max_delta=1.0),
            lambda p: _swap_rooms(p, self.rng),
            lambda p: _nudge_toward_partner(p, self.rng, requirements),
            lambda p: _expand_room(p, self.rng),
        ]
        operator_weights = [1.0, 0.5, 0.8, 2.5, 1.5]
        targeted_share = 0.5   # fraction of steps spent repairing the weakest dimension
        targeted_counts: Dict[str, int] = {}

        last_improvement = 0
        for iteration in range(self.max_iterations):
            if self.rng.random() < targeted_share:
                candidate, dim = _targeted_repair(current, self.rng, requirements, current_eval)
                if dim is not None:
                    targeted_counts[dim] = targeted_counts.get(dim, 0) + 1
            else:
                op = self.rng.choices(operators, weights=operator_weights, k=1)[0]
                candidate = op(current)

            cand_eval = self.critic.evaluate(candidate, requirements)
            cand_score = cand_eval.total_score
            delta = cand_score - current_score

            if delta > 0 or self.rng.random() < math.exp(delta / max(temp, 1e-10)):
                current = candidate
                current_eval = cand_eval
                current_score = cand_score

            if current_score > best_score:
                if current_score > best_score + 1e-4:
                    last_improvement = iteration
                best = copy.deepcopy(current)
                best_eval = copy.deepcopy(current_eval)
                best_score = current_score

            # Quality has stabilised: perfect score, or no gain for `patience` steps
            stabilised = best_score >= 1.0 - 1e-9 or iteration - last_improvement >= self.patience

            if iteration % 50 == 0 or iteration == self.max_iterations - 1 or stabilised:
                self.history.append({
                    "iteration": iteration,
                    "current_score": current_score,
                    "best_score": best_score,
                    "temperature": temp,
                    "violations": len(current_eval.violations),
                    "targeted_repairs": dict(targeted_counts),
                    "stabilised": stabilised,
                })
                if verbose:
                    print(
                        f"  iter {iteration:4d}  score={current_score:.4f}  "
                        f"best={best_score:.4f}  temp={temp:.4f}  "
                        f"violations={len(current_eval.violations)}"
                    )

            if stabilised:
                if verbose:
                    print(f"  Quality stabilised at iteration {iteration} — stopping.")
                break

            temp *= self.cooling_rate

        # Phase 3: clear leftover overlaps and circulation breaks
        best, best_eval = _polish(best, requirements, self.critic)

        return best, best_eval, self.history


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def optimize_floor_plan(
    plan: FloorPlan,
    requirements: DesignRequirements,
    max_iterations: int = 500,
    seed: int = 42,
    verbose: bool = False,
) -> Tuple[FloorPlan, EvaluationResult, List[Dict]]:
    """Convenience wrapper."""
    opt = SimulatedAnnealingOptimizer(
        max_iterations=max_iterations,
        seed=seed,
    )
    return opt.optimize(plan, requirements, verbose=verbose)


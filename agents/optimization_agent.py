"""
Optimization Agent — iteratively improves a floor plan using Simulated Annealing.

Loop:
  1. Evaluate current layout → score + violations
  2. Propose a random modification (move, resize, swap)
  3. Evaluate modified layout
  4. Accept/reject based on SA criterion
  5. Repeat for N iterations
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
    Room,
)
from evaluation.spatial_critic import SpatialCritic, EvaluationResult


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
# Simulated Annealing optimizer
# ---------------------------------------------------------------------------

class SimulatedAnnealingOptimizer:
    """
    Two-phase optimization of floor plans against spatial constraints:
    Phase 1: Greedy room expansion to improve space utilization
    Phase 2: SA refinement for spatial relationships
    """

    def __init__(
        self,
        max_iterations: int = 500,
        initial_temp: float = 0.15,
        cooling_rate: float = 0.997,
        seed: Optional[int] = 42,
    ):
        self.max_iterations = max_iterations
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

        for iteration in range(self.max_iterations):
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
                best = copy.deepcopy(current)
                best_eval = copy.deepcopy(current_eval)
                best_score = current_score

            if iteration % 50 == 0 or iteration == self.max_iterations - 1:
                self.history.append({
                    "iteration": iteration,
                    "current_score": current_score,
                    "best_score": best_score,
                    "temperature": temp,
                    "violations": len(current_eval.violations),
                })
                if verbose:
                    print(
                        f"  iter {iteration:4d}  score={current_score:.4f}  "
                        f"best={best_score:.4f}  temp={temp:.4f}  "
                        f"violations={len(current_eval.violations)}"
                    )

            temp *= self.cooling_rate

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


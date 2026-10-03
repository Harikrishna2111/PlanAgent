"""
End-to-End Pipeline — Agentic AI Framework for Constraint-Aware Architectural Design.

Orchestrates the complete flow:
  NL Input → Requirement Agent → Spatial Graph → Floor-Plan Generator
  → Spatial Critic → Optimization Agent → Visualization

Usage:
  python run_pipeline.py
  python run_pipeline.py --input "Design a 3BHK house on a 50x70 ft plot ..."
  python run_pipeline.py --iterations 1000 --candidates 8
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import DesignRequirements, FloorPlan
from agents.requirement_agent import create_requirement_agent
from spatial.graph import add_implicit_relationships, build_spatial_graph, graph_summary
from generation.floor_plan_generator import generate_floor_plans
from evaluation.spatial_critic import SpatialCritic, EvaluationResult
from agents.optimization_agent import optimize_floor_plan
from visualization.renderer import (
    render_floor_plan,
    render_comparison,
    render_spatial_graph,
    render_optimization_history,
)


# ---------------------------------------------------------------------------
# Default example input
# ---------------------------------------------------------------------------

DEFAULT_INPUT = (
    "Design a 2BHK house on a 40 × 60 ft plot with two bedrooms, "
    "two bathrooms, kitchen, living room and dining area. "
    "The kitchen should be near the dining area, "
    "bedrooms should be close to bathrooms, "
    "and the entrance should connect to the living room."
)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    nl_input: str = DEFAULT_INPUT,
    num_candidates: int = 5,
    optimization_iterations: int = 500,
    output_dir: str = "output",
    backend: str = "rules",
    verbose: bool = True,
) -> dict:
    """
    Execute the full agentic pipeline.

    Returns a summary dict with scores, paths, and timing.
    """
    os.makedirs(output_dir, exist_ok=True)
    results = {}
    t0 = time.time()

    # ── Step 1: Requirement Agent ──────────────────────────────────────────
    if verbose:
        print("=" * 70)
        print("STEP 1 — Requirement Agent")
        print("=" * 70)

    agent = create_requirement_agent(backend=backend)
    requirements = agent.parse(nl_input)
    # Spatial planning: add standard relationships the brief left unstated
    add_implicit_relationships(requirements)

    if verbose:
        print(f"Plot: {requirements.plot_width} × {requirements.plot_height} ft")
        print(f"Rooms ({len(requirements.rooms)}):")
        for r in requirements.rooms:
            print(f"  {r.name} ({r.room_type.value}) — "
                  f"{r.min_width}×{r.min_height} ft, area≈{r.preferred_area} sqft")
        print(f"Relationships ({len(requirements.relationships)}):")
        for rel in requirements.relationships:
            print(f"  {rel.room_a} → {rel.relationship.value} → {rel.room_b}")

    # Save structured requirements
    req_path = os.path.join(output_dir, "requirements.json")
    with open(req_path, "w") as f:
        f.write(requirements.to_json())
    results["requirements_path"] = req_path

    # ── Step 2: Spatial Graph ──────────────────────────────────────────────
    if verbose:
        print("\n" + "=" * 70)
        print("STEP 2 — Spatial Relationship Graph")
        print("=" * 70)

    graph = build_spatial_graph(requirements)
    if verbose:
        print(graph_summary(graph))

    # Visualize graph
    graph_path = os.path.join(output_dir, "spatial_graph.png")
    render_spatial_graph(requirements, save_path=graph_path)
    results["spatial_graph_path"] = graph_path

    # ── Step 3: Floor-Plan Generation ─────────────────────────────────────
    if verbose:
        print("\n" + "=" * 70)
        print("STEP 3 — Floor-Plan Generation")
        print("=" * 70)

    candidates = generate_floor_plans(
        requirements,
        num_candidates=num_candidates,
        seed=42,
    )
    if verbose:
        print(f"Generated {len(candidates)} candidate floor plans.")

    # ── Step 4: Spatial Critic — evaluate all candidates ──────────────────
    if verbose:
        print("\n" + "=" * 70)
        print("STEP 4 — Spatial Critic (Evaluation)")
        print("=" * 70)

    critic = SpatialCritic()
    evaluations = []
    for i, plan in enumerate(candidates):
        ev = critic.evaluate(plan, requirements)
        evaluations.append(ev)
        if verbose:
            print(f"\n  Candidate {i+1}: score = {ev.total_score:.4f}  "
                  f"violations = {len(ev.violations)}")
            for dim, s in ev.dimension_scores.items():
                print(f"    {dim:25s}  {s:.3f}")

    # Select best candidate
    best_idx = max(range(len(candidates)), key=lambda i: evaluations[i].total_score)
    best_candidate = candidates[best_idx]
    best_eval = evaluations[best_idx]

    if verbose:
        print(f"\n  ▶ Best candidate: #{best_idx+1} (score={best_eval.total_score:.4f})")

    # Save & render best candidate (pre-optimisation)
    before_path = os.path.join(output_dir, "floor_plan_before.png")
    render_floor_plan(best_candidate, title="Best Candidate (Before Optimization)", save_path=before_path)
    results["before_path"] = before_path
    results["before_score"] = best_eval.total_score

    # Render all candidates
    if len(candidates) > 1:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        cols = min(3, len(candidates))
        rows = (len(candidates) + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(7 * cols, 6 * rows))
        if rows == 1 and cols == 1:
            axes = [[axes]]
        elif rows == 1:
            axes = [axes]
        elif cols == 1:
            axes = [[ax] for ax in axes]
        for i, plan in enumerate(candidates):
            r, c = divmod(i, cols)
            render_floor_plan(
                plan,
                title=f"Candidate {i+1} (score={plan.score:.4f})",
                ax=axes[r][c],
            )
        # Hide unused axes
        for i in range(len(candidates), rows * cols):
            r, c = divmod(i, cols)
            axes[r][c].axis("off")
        plt.tight_layout()
        all_path = os.path.join(output_dir, "all_candidates.png")
        fig.savefig(all_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        results["all_candidates_path"] = all_path
        if verbose:
            print(f"[Viz] All candidates saved to {all_path}")

    # ── Step 5: Optimization ──────────────────────────────────────────────
    if verbose:
        print("\n" + "=" * 70)
        print("STEP 5 — Optimization (Simulated Annealing)")
        print("=" * 70)
        print(f"  Starting score: {best_eval.total_score:.4f}")
        print(f"  Violations: {len(best_eval.violations)}")
        if best_eval.violations:
            print("  Current violations:")
            for v in best_eval.violations:
                print(f"    [{v.category}] {v.description}")
        print(f"\n  Running {optimization_iterations} iterations...")

    optimized, opt_eval, history = optimize_floor_plan(
        best_candidate,
        requirements,
        max_iterations=optimization_iterations,
        seed=42,
        verbose=verbose,
    )

    if verbose:
        print(f"\n  Final score: {opt_eval.total_score:.4f}")
        print(f"  Improvement: {opt_eval.total_score - best_eval.total_score:+.4f}")
        print(f"  Violations: {len(opt_eval.violations)}")
        if opt_eval.violations:
            print("  Remaining violations:")
            for v in opt_eval.violations:
                print(f"    [{v.category}] {v.description}")

    results["after_score"] = opt_eval.total_score
    results["improvement"] = opt_eval.total_score - best_eval.total_score
    results["violations_before"] = len(best_eval.violations)
    results["violations_after"] = len(opt_eval.violations)

    # ── Step 6: Visualization ─────────────────────────────────────────────
    if verbose:
        print("\n" + "=" * 70)
        print("STEP 6 — Final Visualization")
        print("=" * 70)

    after_path = os.path.join(output_dir, "floor_plan_after.png")
    render_floor_plan(optimized, title="Optimized Floor Plan", save_path=after_path)
    results["after_path"] = after_path

    comp_path = os.path.join(output_dir, "comparison.png")
    render_comparison(best_candidate, optimized, save_path=comp_path)
    results["comparison_path"] = comp_path

    hist_path = os.path.join(output_dir, "optimization_history.png")
    render_optimization_history(history, save_path=hist_path)
    results["history_path"] = hist_path

    # ── Summary ───────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    results["elapsed_seconds"] = round(elapsed, 2)

    if verbose:
        print("\n" + "=" * 70)
        print("PIPELINE COMPLETE")
        print("=" * 70)
        print(f"  Time elapsed:       {elapsed:.2f}s")
        print(f"  Candidates:         {len(candidates)}")
        print(f"  Best candidate:     #{best_idx+1}")
        print(f"  Score before opt:   {results['before_score']:.4f}")
        print(f"  Score after opt:    {results['after_score']:.4f}")
        print(f"  Score improvement:  {results['improvement']:+.4f}")
        print(f"  Violations before:  {results['violations_before']}")
        print(f"  Violations after:   {results['violations_after']}")
        print(f"\n  Output directory:   {os.path.abspath(output_dir)}")
        print(f"  Files:")
        for k, v in results.items():
            if k.endswith("_path"):
                print(f"    {k}: {v}")

    # Save results JSON
    summary_path = os.path.join(output_dir, "pipeline_results.json")
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)

    # Save detailed evaluation
    eval_path = os.path.join(output_dir, "evaluation_details.json")
    with open(eval_path, "w") as f:
        json.dump({
            "before": {
                "total_score": best_eval.total_score,
                "dimension_scores": best_eval.dimension_scores,
                "violations": [
                    {"category": v.category, "description": v.description}
                    for v in best_eval.violations
                ],
            },
            "after": {
                "total_score": opt_eval.total_score,
                "dimension_scores": opt_eval.dimension_scores,
                "violations": [
                    {"category": v.category, "description": v.description}
                    for v in opt_eval.violations
                ],
            },
            "optimized_plan": optimized.to_dict(),
        }, f, indent=2)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Agentic AI Framework for Constraint-Aware Architectural Design",
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=DEFAULT_INPUT,
        help="Natural-language architectural brief",
    )
    parser.add_argument(
        "--candidates", "-c",
        type=int,
        default=5,
        help="Number of candidate floor plans to generate",
    )
    parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=500,
        help="SA optimization iterations",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="output",
        help="Output directory for results",
    )
    parser.add_argument(
        "--backend",
        choices=["rules", "llm"],
        default="rules",
        help="Requirement agent backend",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose output",
    )

    args = parser.parse_args()
    run_pipeline(
        nl_input=args.input,
        num_candidates=args.candidates,
        optimization_iterations=args.iterations,
        output_dir=args.output,
        backend=args.backend,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()

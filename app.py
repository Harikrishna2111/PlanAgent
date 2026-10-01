"""
Flask Web Server — Agentic AI Framework for Constraint-Aware Architectural Design.

Serves a premium web UI and exposes the pipeline as a REST API.

Usage:
    python app.py
    → Open http://localhost:5000
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import traceback

from flask import Flask, render_template, request, jsonify, send_from_directory

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from models import DesignRequirements, FloorPlan
from agents.requirement_agent import create_requirement_agent
from spatial.graph import build_spatial_graph, graph_summary
from generation.floor_plan_generator import generate_floor_plans
from evaluation.spatial_critic import SpatialCritic
from agents.optimization_agent import optimize_floor_plan
from visualization.renderer import (
    render_floor_plan,
    render_comparison,
    render_spatial_graph,
    render_optimization_history,
)

app = Flask(
    __name__,
    template_folder="web/templates",
    static_folder="web/static",
)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route("/favicon.ico")
def favicon():
    return "", 204


def _fig_to_base64(fig) -> str:
    """Convert matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/pipeline", methods=["POST"])
def run_pipeline_api():
    """Execute the full pipeline and return results as JSON with embedded images."""
    try:
        data = request.get_json()
        nl_input = data.get("input", "").strip()
        num_candidates = int(data.get("candidates", 5))
        iterations = int(data.get("iterations", 300))
        backend = data.get("backend", "rules")

        if not nl_input:
            return jsonify({"error": "Please provide an architectural brief."}), 400

        results = {}
        t0 = time.time()

        # ── Step 1: Requirement Agent ──────────────────────────────────────
        agent = create_requirement_agent(backend=backend)
        requirements = agent.parse(nl_input)

        results["requirements"] = {
            "plot_width": requirements.plot_width,
            "plot_height": requirements.plot_height,
            "rooms": [r.to_dict() for r in requirements.rooms],
            "relationships": [r.to_dict() for r in requirements.relationships],
        }

        # ── Step 2: Spatial Graph ──────────────────────────────────────────
        graph = build_spatial_graph(requirements)
        results["graph_summary"] = graph_summary(graph)

        fig = render_spatial_graph(requirements)
        fig.patch.set_facecolor("#0f1117")
        for ax in fig.get_axes():
            ax.set_facecolor("#0f1117")
            ax.title.set_color("white")
            for text in ax.texts:
                text.set_color("white")
        results["spatial_graph_img"] = _fig_to_base64(fig)

        # ── Step 3: Floor-Plan Generation ─────────────────────────────────
        candidates = generate_floor_plans(
            requirements, num_candidates=num_candidates, seed=42
        )

        # ── Step 4: Spatial Critic ────────────────────────────────────────
        critic = SpatialCritic()
        evaluations = []
        for plan in candidates:
            ev = critic.evaluate(plan, requirements)
            evaluations.append(ev)

        candidate_data = []
        for i, (plan, ev) in enumerate(zip(candidates, evaluations)):
            fig = render_floor_plan(plan, title=f"Candidate {i+1}")
            fig.patch.set_facecolor("#0f1117")
            for ax in fig.get_axes():
                ax.set_facecolor("#181c25")
            candidate_data.append({
                "index": i + 1,
                "score": round(ev.total_score, 4),
                "violations": len(ev.violations),
                "dimension_scores": {k: round(v, 4) for k, v in ev.dimension_scores.items()},
                "violation_details": [
                    {"category": v.category, "description": v.description}
                    for v in ev.violations
                ],
                "image": _fig_to_base64(fig),
            })

        results["candidates"] = candidate_data

        # Select best
        best_idx = max(range(len(candidates)), key=lambda i: evaluations[i].total_score)
        best_candidate = candidates[best_idx]
        best_eval = evaluations[best_idx]

        results["best_candidate_index"] = best_idx + 1
        results["before_score"] = round(best_eval.total_score, 4)
        results["before_violations"] = len(best_eval.violations)
        results["before_violation_details"] = [
            {"category": v.category, "description": v.description}
            for v in best_eval.violations
        ]
        results["before_dimension_scores"] = {
            k: round(v, 4) for k, v in best_eval.dimension_scores.items()
        }

        # Before plan image
        fig = render_floor_plan(best_candidate, title="Before Optimization")
        fig.patch.set_facecolor("#0f1117")
        for ax in fig.get_axes():
            ax.set_facecolor("#181c25")
        results["before_plan_img"] = _fig_to_base64(fig)

        # ── Step 5: Optimization ──────────────────────────────────────────
        optimized, opt_eval, history = optimize_floor_plan(
            best_candidate, requirements,
            max_iterations=iterations, seed=42, verbose=False,
        )

        results["after_score"] = round(opt_eval.total_score, 4)
        results["after_violations"] = len(opt_eval.violations)
        results["after_violation_details"] = [
            {"category": v.category, "description": v.description}
            for v in opt_eval.violations
        ]
        results["after_dimension_scores"] = {
            k: round(v, 4) for k, v in opt_eval.dimension_scores.items()
        }
        results["improvement"] = round(opt_eval.total_score - best_eval.total_score, 4)

        # After plan image
        fig = render_floor_plan(optimized, title="Optimized Floor Plan")
        fig.patch.set_facecolor("#0f1117")
        for ax in fig.get_axes():
            ax.set_facecolor("#181c25")
        results["after_plan_img"] = _fig_to_base64(fig)

        # Comparison image
        fig = render_comparison(best_candidate, optimized)
        fig.patch.set_facecolor("#0f1117")
        for ax in fig.get_axes():
            ax.set_facecolor("#181c25")
        results["comparison_img"] = _fig_to_base64(fig)

        # Optimization history
        if history:
            fig = render_optimization_history(history)
            fig.patch.set_facecolor("#0f1117")
            for ax in fig.get_axes():
                ax.set_facecolor("#181c25")
                ax.xaxis.label.set_color("white")
                ax.yaxis.label.set_color("white")
                ax.title.set_color("white")
                ax.tick_params(colors="white")
                for spine in ax.spines.values():
                    spine.set_edgecolor("#333")
            results["history_img"] = _fig_to_base64(fig)
            results["history"] = history

        # Optimized plan room details
        results["optimized_rooms"] = [r.to_dict() for r in optimized.rooms]
        results["utilization_before"] = round(best_candidate.utilization * 100, 1)
        results["utilization_after"] = round(optimized.utilization * 100, 1)

        results["elapsed"] = round(time.time() - t0, 2)
        return jsonify(results)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/output/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PlanAgent — Agentic AI Architectural Design Framework")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 60 + "\n")
    app.run(debug=False, host="0.0.0.0", port=5000)

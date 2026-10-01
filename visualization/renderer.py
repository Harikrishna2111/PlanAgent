"""
Visualization module — renders 2D floor plans and spatial relationship graphs.

Outputs:
  - Floor plan with room rectangles, names, dimensions, and plot boundary
  - Spatial relationship graph (NetworkX + matplotlib)
  - Optimization convergence plot
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import networkx as nx
import numpy as np

from models import FloorPlan, Room, DesignRequirements, RelationshipType
from spatial.graph import build_spatial_graph


# ---------------------------------------------------------------------------
# Colour palette for room types
# ---------------------------------------------------------------------------

ROOM_COLORS = {
    "bedroom":     "#A8D8EA",
    "bathroom":    "#B8E6C8",
    "kitchen":     "#FFD3B6",
    "living_room": "#FFAAA5",
    "dining":      "#DCEDC1",
    "entrance":    "#D5AAFF",
    "hallway":     "#F0E68C",
    "balcony":     "#C4FAF8",
    "study":       "#F4C2C2",
    "pooja":       "#FFE4B5",
    "utility":     "#D3D3D3",
    "garage":      "#C0C0C0",
    "staircase":   "#E6E6FA",
    "store":       "#DEB887",
}


# ---------------------------------------------------------------------------
# Floor plan rendering
# ---------------------------------------------------------------------------

def render_floor_plan(
    plan: FloorPlan,
    title: str = "Floor Plan",
    ax: Optional[plt.Axes] = None,
    show_dimensions: bool = True,
    save_path: Optional[str] = None,
) -> Optional[plt.Figure]:
    """
    Render a 2D floor plan with room rectangles, labels, and plot boundary.
    """
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    else:
        fig = ax.get_figure()

    # Plot boundary
    boundary = patches.Rectangle(
        (0, 0), plan.plot_width, plan.plot_height,
        linewidth=2.5, edgecolor="black", facecolor="#F5F5F5",
        linestyle="--", label="Plot Boundary",
    )
    ax.add_patch(boundary)

    # Draw rooms
    for room in plan.rooms:
        color = ROOM_COLORS.get(room.room_type.value, "#DDDDDD")
        rect = patches.Rectangle(
            (room.x, room.y), room.width, room.height,
            linewidth=1.5, edgecolor="#333333", facecolor=color,
            alpha=0.85,
        )
        ax.add_patch(rect)

        # Room name
        cx, cy = room.center
        label = room.name
        fontsize = max(6, min(9, int(min(room.width, room.height) * 0.8)))
        ax.text(
            cx, cy, label,
            ha="center", va="center", fontsize=fontsize,
            fontweight="bold", color="#222222",
            wrap=True,
        )

        # Dimensions
        if show_dimensions:
            dim_text = f"{room.width:.0f}×{room.height:.0f}"
            ax.text(
                cx, cy - fontsize * 0.15,
                dim_text,
                ha="center", va="top", fontsize=max(5, fontsize - 2),
                color="#555555", style="italic",
            )

    # Axes
    margin = 3
    ax.set_xlim(-margin, plan.plot_width + margin)
    ax.set_ylim(-margin, plan.plot_height + margin)
    ax.set_aspect("equal")
    ax.set_xlabel("Width (ft)")
    ax.set_ylabel("Height (ft)")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.2)

    # Score annotation
    if plan.score is not None:
        ax.text(
            plan.plot_width + margin - 1, -margin + 0.5,
            f"Score: {plan.score:.4f}",
            ha="right", va="bottom", fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", edgecolor="gray"),
        )

    if standalone:
        plt.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"[Viz] Floor plan saved to {save_path}")
        return fig
    return None


def render_comparison(
    before: FloorPlan,
    after: FloorPlan,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Side-by-side before/after comparison."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
    render_floor_plan(before, title="Before Optimization", ax=ax1)
    render_floor_plan(after, title="After Optimization", ax=ax2)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"[Viz] Comparison saved to {save_path}")
    return fig


# ---------------------------------------------------------------------------
# Spatial graph rendering
# ---------------------------------------------------------------------------

def render_spatial_graph(
    requirements: DesignRequirements,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Render the spatial relationship graph."""
    G = build_spatial_graph(requirements)

    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    pos = nx.spring_layout(G, seed=42, k=2.0)

    # Colour nodes by room type
    node_colors = []
    for node in G.nodes():
        rtype = G.nodes[node].get("room_type", "utility")
        node_colors.append(ROOM_COLORS.get(rtype, "#DDDDDD"))

    # Edge colours by relationship type
    edge_colors = []
    edge_styles = []
    edge_labels = {}
    for u, v, data in G.edges(data=True):
        rel = data.get("relationship", "near")
        if rel == "connected_to":
            edge_colors.append("#2196F3")
            edge_styles.append("solid")
        elif rel == "away_from":
            edge_colors.append("#F44336")
            edge_styles.append("dashed")
        else:
            edge_colors.append("#4CAF50")
            edge_styles.append("solid")
        edge_labels[(u, v)] = rel

    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=node_colors, node_size=2000,
        edgecolors="#333333", linewidths=1.5,
    )
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=8, font_weight="bold")

    # Draw edges one-by-one to support different styles
    for i, (u, v) in enumerate(G.edges()):
        nx.draw_networkx_edges(
            G, pos, ax=ax,
            edgelist=[(u, v)],
            edge_color=[edge_colors[i]],
            style=edge_styles[i],
            width=2.0,
            arrows=True,
            arrowstyle="-|>",
            arrowsize=15,
        )
    nx.draw_networkx_edge_labels(
        G, pos, ax=ax,
        edge_labels=edge_labels,
        font_size=7,
        font_color="#666666",
    )

    ax.set_title("Spatial Relationship Graph", fontsize=14, fontweight="bold")
    ax.axis("off")

    # Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color="#4CAF50", lw=2, label="near"),
        Line2D([0], [0], color="#2196F3", lw=2, label="connected_to"),
        Line2D([0], [0], color="#F44336", lw=2, linestyle="dashed", label="away_from"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=9)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"[Viz] Spatial graph saved to {save_path}")
    return fig


# ---------------------------------------------------------------------------
# Optimization history plot
# ---------------------------------------------------------------------------

def render_optimization_history(
    history: List[Dict],
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Plot score convergence over optimization iterations."""
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))

    iters = [h["iteration"] for h in history]
    current = [h["current_score"] for h in history]
    best = [h["best_score"] for h in history]

    ax.plot(iters, current, "o-", color="#2196F3", alpha=0.6, label="Current Score", markersize=3)
    ax.plot(iters, best, "s-", color="#4CAF50", linewidth=2, label="Best Score", markersize=4)

    ax.set_xlabel("Iteration")
    ax.set_ylabel("Score")
    ax.set_title("Optimization Convergence", fontsize=13, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"[Viz] Optimization history saved to {save_path}")
    return fig

"""
Spatial Agent — LLM-powered reasoning about spatial arrangement strategy.

Given the structured requirements, this agent uses Gemini to reason about:
  - Optimal zone organisation (public vs private, front vs back)
  - Which adjacencies are most critical for the floor plan quality
  - Enhanced edge weights to guide the generator
  - Spatial strategy document for the DesignAgent to follow

Tools used: spatial.graph.build_spatial_graph (NetworkX)
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from models import DesignRequirements, RelationshipType
from spatial.graph import build_spatial_graph, graph_summary
from agents.base_agent import BaseAgent, AgentMessage


class SpatialAgent(BaseAgent):
    """
    Reasons about the spatial layout strategy before generation.
    Produces enhanced relationship weights + a strategy document.
    """

    NAME = "SpatialAgent"

    ROLE_PROMPT = """You are an expert architectural spatial planning agent.
Your role is to analyse the structured room requirements and produce a spatial strategy
that will guide floor plan generation.

You reason about:
- Public vs private zone separation (entrance, living, dining = public; bedrooms, bathrooms = private)
- Traffic flow and circulation paths
- Which adjacencies are critical vs nice-to-have
- Which rooms anchor each zone of the plot

You output JSON with the following schema:
{
  "spatial_strategy": "<2-3 sentence summary of the layout approach>",
  "zones": {
    "public": ["<room names>"],
    "private": ["<room names>"],
    "service": ["<room names>"]
  },
  "critical_adjacencies": [
    {"room_a": "<name>", "room_b": "<name>", "reason": "<why>", "priority": <1-5>}
  ],
  "anchor_rooms": {
    "front": "<room name that anchors the front of the plot>",
    "back": "<room name that anchors the back>",
    "center": "<room name that should be central>"
  },
  "placement_hints": [
    "<hint for the floor plan generator about where to place which room>"
  ]
}"""

    def analyse(
        self,
        requirements: DesignRequirements,
        fallback_ok: bool = True,
    ) -> Tuple[dict, AgentMessage]:
        """
        Run spatial analysis. Returns (strategy_dict, log_message).
        If LLM unavailable and fallback_ok, returns a heuristic strategy.
        """
        # Build spatial graph (always done deterministically)
        graph = build_spatial_graph(requirements)
        graph_text = graph_summary(graph)

        room_names = [r.name for r in requirements.rooms]
        rel_text = "\n".join(
            f"  {r.room_a} → {r.relationship.value} → {r.room_b}"
            for r in requirements.relationships
        )

        prompt = f"""Analyse this architectural brief and produce a spatial strategy.

Plot size: {requirements.plot_width} ft × {requirements.plot_height} ft
Rooms: {', '.join(room_names)}
Spatial relationships:
{rel_text}

Spatial graph summary:
{graph_text}

Produce a spatial strategy JSON as described in your role."""

        if not self.api_key:
            strategy = self._heuristic_strategy(requirements)
            msg = self.log(
                action="Spatial analysis (heuristic — no API key)",
                reasoning="Used built-in heuristics: public rooms at front, private at back, service rooms at perimeter.",
                payload=strategy,
            )
            return strategy, msg

        result = self.llm_call(prompt)
        if "error" in result:
            strategy = self._heuristic_strategy(requirements)
            msg = self.log(
                action="Spatial analysis (heuristic fallback — LLM error)",
                reasoning=f"LLM call failed: {result['error']}. Using heuristics.",
                payload=strategy,
            )
        else:
            msg = self.log(
                action="Spatial strategy established",
                reasoning=result.get("spatial_strategy", ""),
                payload=result,
            )
            strategy = result

        return strategy, msg

    # ---- heuristic fallback --------------------------------------------------

    def _heuristic_strategy(self, req: DesignRequirements) -> dict:
        """Rule-based spatial strategy when LLM is unavailable."""
        public_types = {"living_room", "dining", "entrance", "kitchen"}
        private_types = {"bedroom", "bathroom", "study", "pooja"}
        service_types = {"utility", "garage", "store", "staircase", "hallway", "balcony"}

        public_rooms = [r.name for r in req.rooms if r.room_type.value in public_types]
        private_rooms = [r.name for r in req.rooms if r.room_type.value in private_types]
        service_rooms = [r.name for r in req.rooms if r.room_type.value in service_types]

        # Build critical adjacencies from "near" and "connected_to" relationships
        critical = []
        for rel in req.relationships:
            if rel.relationship in (RelationshipType.NEAR, RelationshipType.CONNECTED_TO):
                priority = 5 if rel.relationship == RelationshipType.CONNECTED_TO else 3
                critical.append({
                    "room_a": rel.room_a,
                    "room_b": rel.room_b,
                    "reason": f"Required by {rel.relationship.value} constraint",
                    "priority": priority,
                })

        entrance = next((r.name for r in req.rooms if r.room_type.value == "entrance"), None)
        living = next((r.name for r in req.rooms if r.room_type.value == "living_room"), None)
        bedroom = next((r.name for r in req.rooms if r.room_type.value == "bedroom"), None)

        return {
            "spatial_strategy": (
                f"Place public rooms ({', '.join(public_rooms[:3])}) at the front of the plot near the entrance. "
                f"Group private rooms ({', '.join(private_rooms[:3])}) at the back. "
                f"Service rooms at the perimeter."
            ),
            "zones": {
                "public": public_rooms,
                "private": private_rooms,
                "service": service_rooms,
            },
            "critical_adjacencies": critical,
            "anchor_rooms": {
                "front": entrance or (public_rooms[0] if public_rooms else ""),
                "back": bedroom or (private_rooms[0] if private_rooms else ""),
                "center": living or (public_rooms[1] if len(public_rooms) > 1 else ""),
            },
            "placement_hints": [
                "Place entrance at the bottom edge of the plot",
                "Living room should be directly accessible from entrance",
                "Bedrooms should be grouped together away from entrance",
                "Kitchen should be near dining area",
                "Bathrooms should be adjacent to bedrooms",
            ],
        }

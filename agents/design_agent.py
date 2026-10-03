"""
Design Agent — LLM-guided floor plan generation.

Uses the spatial strategy from SpatialAgent and (from round 2+) the feedback
from CriticAgent to guide the ProceduralGenerator toward better layouts.

The LLM reasons about placement strategy; the ProceduralGenerator (as a tool)
does the actual geometry. The agent can request different variations, seeding
strategies, and incorporate specific critic feedback.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from models import DesignRequirements, FloorPlan
from generation.floor_plan_generator import generate_floor_plans
from agents.base_agent import BaseAgent, AgentMessage


class DesignAgent(BaseAgent):
    """
    LLM-guided floor plan generation agent.

    Round 1: Uses spatial strategy to pick best generation parameters.
    Round 2+: Incorporates CriticAgent feedback to improve the layout.
    """

    NAME = "DesignAgent"

    ROLE_PROMPT = """You are an expert architectural floor plan design agent.
Your role is to decide the generation strategy for floor plan candidates.

Given the spatial strategy, plot dimensions, room requirements, and (in later rounds)
critic feedback, you decide:
- How many candidates to generate
- Which variation strategies to emphasise (entrance-first, largest-first, graph-degree, random)
- The random seed offset to use for diversity
- Specific placement guidance based on critic feedback

You output JSON with this schema:
{
  "generation_plan": "<1-2 sentence description of your generation approach>",
  "num_candidates": <integer, 3-8>,
  "variation_emphasis": "<one of: entrance_first | largest_first | graph_degree | mixed>",
  "seed_offset": <integer 0-999>,
  "addressing_feedback": "<how you are addressing the critic's suggestions, or 'N/A' for round 1>",
  "key_constraints_to_prioritise": ["<room relationship to prioritise>"]
}"""

    def plan_generation(
        self,
        requirements: DesignRequirements,
        spatial_strategy: dict,
        num_candidates: int,
        round_num: int = 1,
        critic_feedback: Optional[dict] = None,
    ) -> Tuple[List[FloorPlan], AgentMessage]:
        """
        Reason about generation strategy then generate candidates.
        Returns (candidates, log_message).
        """
        prompt = self._build_prompt(
            requirements, spatial_strategy, num_candidates, round_num, critic_feedback
        )

        if not self.api_key:
            plan = self._heuristic_plan(round_num, num_candidates, critic_feedback)
        else:
            result = self.llm_call(prompt)
            if "error" in result:
                plan = self._heuristic_plan(round_num, num_candidates, critic_feedback)
                plan["_llm_error"] = result["error"]
            else:
                plan = result

        # Execute generation using the plan
        seed = 42 + plan.get("seed_offset", 0)
        n = plan.get("num_candidates", num_candidates)
        n = max(1, min(n, 8))  # clamp to sane range

        candidates = generate_floor_plans(requirements, num_candidates=n, seed=seed)

        addressing = plan.get("addressing_feedback", "N/A")
        generation_plan = plan.get("generation_plan", "Generating candidates with procedural heuristic.")

        reasoning = f"Round {round_num}: {generation_plan}"
        if addressing and addressing != "N/A":
            reasoning += f" Addressing feedback: {addressing}"

        msg = self.log(
            action=f"Generated {len(candidates)} candidates (Round {round_num})",
            reasoning=reasoning,
            payload={
                "round": round_num,
                "num_candidates": len(candidates),
                "seed": seed,
                "generation_plan": generation_plan,
                "addressing_feedback": addressing,
            },
        )

        return candidates, msg

    # ---- prompt builder ------------------------------------------------------

    def _build_prompt(
        self,
        req: DesignRequirements,
        strategy: dict,
        num_candidates: int,
        round_num: int,
        feedback: Optional[dict],
    ) -> str:
        room_list = ", ".join(r.name for r in req.rooms)
        strategy_text = strategy.get("spatial_strategy", "")
        hints = "\n".join(f"  - {h}" for h in strategy.get("placement_hints", []))

        prompt = f"""You are designing floor plans for a {req.plot_width}×{req.plot_height} ft plot.
Rooms: {room_list}
Spatial strategy: {strategy_text}
Placement hints:
{hints}
Generation round: {round_num}
Requested candidates: {num_candidates}
"""
        if feedback and round_num > 1:
            verdict = feedback.get("verdict", "")
            suggestions = feedback.get("suggestions", [])
            weak = feedback.get("weak_dimensions", [])
            suggestion_text = "\n".join(f"  - {s}" for s in suggestions)
            prompt += f"""
Critic feedback from previous round:
  Verdict: {verdict}
  Weak dimensions: {', '.join(weak)}
  Suggestions:
{suggestion_text}

Adapt your generation strategy to address this feedback.
"""
        prompt += "\nOutput your generation plan as JSON."
        return prompt

    # ---- heuristic fallback --------------------------------------------------

    def _heuristic_plan(
        self,
        round_num: int,
        num_candidates: int,
        feedback: Optional[dict],
    ) -> dict:
        """Rule-based generation plan when LLM is unavailable."""
        emphasis_options = ["entrance_first", "largest_first", "graph_degree", "mixed"]

        if round_num == 1:
            emphasis = "entrance_first"
            seed_offset = 0
            addressing = "N/A"
        elif feedback and feedback.get("weak_dimensions"):
            # Try a different ordering strategy if previous round was weak
            emphasis = "graph_degree"
            seed_offset = round_num * 100
            suggestions = feedback.get("suggestions", [])
            addressing = f"Trying graph-degree ordering to improve {', '.join(feedback.get('weak_dimensions', [])[:2])}"
        else:
            emphasis = "mixed"
            seed_offset = round_num * 50
            addressing = "Increasing diversity with mixed ordering"

        return {
            "generation_plan": f"Round {round_num}: Using {emphasis} ordering with seed offset {seed_offset}.",
            "num_candidates": num_candidates,
            "variation_emphasis": emphasis,
            "seed_offset": seed_offset,
            "addressing_feedback": addressing,
            "key_constraints_to_prioritise": [],
        }

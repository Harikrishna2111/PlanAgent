"""
Orchestrator Agent — LLM-powered pipeline coordinator.

The Orchestrator:
  1. Kicks off the pipeline by briefing all agents
  2. Manages the Generate → Critique → (Feedback) → Generate loop
  3. Decides when to stop (based on verdict + round limits)
  4. Hands off the best plan to the OptimizationAgent
  5. Produces a final summary of the entire agentic run

This is the brain of the agentic system.
"""

from __future__ import annotations

import copy
import time
from typing import Dict, List, Optional, Tuple

from models import DesignRequirements, FloorPlan
from evaluation.spatial_critic import EvaluationResult
from agents.base_agent import BaseAgent, AgentMessage
from spatial.graph import add_implicit_relationships
from agents.requirement_agent import RuleBasedRequirementAgent, LLMRequirementAgent
from agents.spatial_agent import SpatialAgent
from agents.design_agent import DesignAgent
from agents.critic_agent import CriticAgent
from agents.optimization_agent import optimize_floor_plan
from visualization.renderer import (
    render_floor_plan,
    render_comparison,
    render_spatial_graph,
    render_optimization_history,
)


class OrchestratorAgent(BaseAgent):
    """
    Coordinates all agents through the full agentic pipeline with feedback loops.
    """

    NAME = "OrchestratorAgent"

    ROLE_PROMPT = """You are the master orchestrator of an agentic architectural design system.
You coordinate multiple specialist agents: RequirementAgent, SpatialAgent, DesignAgent,
CriticAgent, and OptimizationAgent.

Your job at the start of the pipeline is to assess the brief and decide:
- How many design rounds to attempt (1-3)
- What the primary design challenge is
- What success looks like for this brief

Your job at the end is to write a final summary of what the agentic system achieved.

You output JSON with this schema (for start-of-pipeline):
{
  "brief_assessment": "<1-2 sentences about the brief complexity and key challenges>",
  "planned_rounds": <integer 1-3>,
  "primary_challenge": "<the main design challenge to solve>",
  "success_criteria": "<what a good floor plan for this brief looks like>"
}

Or for end-of-pipeline:
{
  "final_summary": "<2-3 sentence summary of what the pipeline achieved>",
  "score_improvement": "<summary of score progression across rounds>",
  "key_achievements": ["<what worked well>"],
  "remaining_limitations": ["<what could be better>"]
}"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3.8-flash",
        max_rounds: int = 3,
        num_candidates: int = 5,
        optimization_iterations: int = 300,
    ):
        super().__init__(api_key=api_key, model=model)
        self.max_rounds = max_rounds
        self.num_candidates = num_candidates
        self.optimization_iterations = optimization_iterations

        # Instantiate sub-agents (all share same API key)
        self.spatial_agent = SpatialAgent(api_key=api_key, model=model)
        self.design_agent = DesignAgent(api_key=api_key, model=model)
        self.critic_agent = CriticAgent(api_key=api_key, model=model)

    def run(
        self,
        nl_input: str,
        backend: str = "agentic",
    ) -> dict:
        """
        Execute the full agentic pipeline.

        Returns a comprehensive results dict (same shape as the classic pipeline
        result, plus agent_activity and agentic metadata).
        """
        t0 = time.time()
        all_activity: List[dict] = []

        # ── Step 0: Parse requirements ─────────────────────────────────────
        requirements = self._parse_requirements(nl_input, backend, all_activity)

        # ── Step 1: Orchestrator assesses the brief ────────────────────────
        assessment = self._assess_brief(requirements, all_activity)
        planned_rounds = min(
            assessment.get("planned_rounds", 2),
            self.max_rounds,
        )

        # ── Step 2: Spatial analysis ───────────────────────────────────────
        inferred = add_implicit_relationships(requirements)
        if inferred:
            infer_msg = self.spatial_agent.log(
                action=f"Inferred {len(inferred)} implicit spatial relationship(s)",
                reasoning=(
                    "Added standard residential constraints the brief left unstated "
                    "(explicit constraints on the same room pair take precedence)."
                ),
                payload={"inferred": [r.to_dict() for r in inferred]},
            )
            all_activity.append(infer_msg.to_dict())

        spatial_strategy, sp_msg = self.spatial_agent.analyse(requirements)
        all_activity.append(sp_msg.to_dict())

        # ── Step 3: Design → Critique feedback loop ────────────────────────
        best_plan: Optional[FloorPlan] = None
        best_eval: Optional[EvaluationResult] = None
        critic_feedback: Optional[dict] = None
        round_scores: List[float] = []

        for round_num in range(1, planned_rounds + 1):
            # 3a. Design
            candidates, design_msg = self.design_agent.plan_generation(
                requirements=requirements,
                spatial_strategy=spatial_strategy,
                num_candidates=self.num_candidates,
                round_num=round_num,
                critic_feedback=critic_feedback,
            )
            all_activity.append(design_msg.to_dict())

            # 3b. Critique
            best_plan, best_eval, critic_feedback, critic_msg = self.critic_agent.evaluate(
                candidates=candidates,
                requirements=requirements,
                round_num=round_num,
            )
            all_activity.append(critic_msg.to_dict())
            round_scores.append(best_eval.total_score)

            verdict = critic_feedback.get("verdict", "NEEDS_IMPROVEMENT")

            # Orchestrator decides whether to continue
            if verdict in ("EXCELLENT", "ACCEPTABLE") and round_num >= 1:
                stop_msg = self.log(
                    action=f"Stopping design loop after Round {round_num}",
                    reasoning=(
                        f"CriticAgent verdict '{verdict}' with score {best_eval.total_score:.3f}. "
                        f"No further design rounds needed."
                    ),
                    payload={"verdict": verdict, "round": round_num, "score": best_eval.total_score},
                )
                all_activity.append(stop_msg.to_dict())
                break
            elif round_num < planned_rounds:
                continue_msg = self.log(
                    action=f"Requesting redesign after Round {round_num}",
                    reasoning=(
                        f"Verdict '{verdict}' — score {best_eval.total_score:.3f}. "
                        f"Passing critic feedback to DesignAgent for Round {round_num + 1}."
                    ),
                    payload={"round": round_num, "feedback_passed": critic_feedback.get("suggestions", [])},
                )
                all_activity.append(continue_msg.to_dict())

        rounds_completed = len(round_scores)
        before_score = best_eval.total_score

        # ── Step 4: Optimization ───────────────────────────────────────────
        opt_msg = self.log(
            action="Starting optimization phase",
            reasoning=(
                f"Best plan (score={before_score:.3f}) handed to OptimizationAgent "
                f"for greedy expansion + simulated annealing ({self.optimization_iterations} iterations)."
            ),
            payload={"before_score": round(before_score, 4)},
        )
        all_activity.append(opt_msg.to_dict())

        plan_before = copy.deepcopy(best_plan)
        optimized, opt_eval, history = optimize_floor_plan(
            best_plan,
            requirements,
            max_iterations=self.optimization_iterations,
            seed=42,
            verbose=False,
        )

        opt_done_msg = self.log(
            action="Optimization complete",
            reasoning=(
                f"Score improved from {before_score:.3f} → {opt_eval.total_score:.3f} "
                f"({opt_eval.total_score - before_score:+.3f}). "
                f"Space utilization: {optimized.utilization:.1%}."
            ),
            payload={
                "after_score": round(opt_eval.total_score, 4),
                "improvement": round(opt_eval.total_score - before_score, 4),
            },
        )
        all_activity.append(opt_done_msg.to_dict())

        # ── Step 5: Final orchestrator summary ────────────────────────────
        final_summary = self._final_summary(
            requirements, round_scores, before_score, opt_eval.total_score, all_activity
        )

        # All agent events were appended inline — just sort by timestamp
        all_activity.sort(key=lambda m: m.get("timestamp", 0))

        elapsed = time.time() - t0

        return {
            "requirements": requirements,
            "spatial_strategy": spatial_strategy,
            "plan_before": plan_before,
            "plan_after": optimized,
            "eval_before": best_eval,
            "eval_after": opt_eval,
            "history": history,
            "agent_activity": all_activity,
            "rounds_completed": rounds_completed,
            "round_scores": round_scores,
            "final_verdict": critic_feedback.get("verdict", "N/A"),
            "final_summary": final_summary,
            "elapsed": elapsed,
        }

    # ── Private methods ────────────────────────────────────────────────────

    def _parse_requirements(
        self,
        nl_input: str,
        backend: str,
        activity: List[dict],
    ) -> DesignRequirements:
        """Parse NL input using either LLM or rule-based agent."""
        if backend == "agentic" and self.api_key:
            agent = LLMRequirementAgent(api_key=self.api_key, model=self.model_name)
            method = "Gemini LLM"
        else:
            agent = RuleBasedRequirementAgent()
            method = "rule-based parser"

        requirements = agent.parse(nl_input)

        msg = self.log(
            action="Requirements parsed",
            reasoning=(
                f"Used {method}. Extracted {len(requirements.rooms)} rooms on a "
                f"{requirements.plot_width}×{requirements.plot_height} ft plot "
                f"with {len(requirements.relationships)} spatial relationships."
            ),
            payload={
                "plot_width": requirements.plot_width,
                "plot_height": requirements.plot_height,
                "num_rooms": len(requirements.rooms),
                "num_relationships": len(requirements.relationships),
                "rooms": [r.name for r in requirements.rooms],
                "method": method,
            },
        )
        activity.append(msg.to_dict())
        return requirements

    def _assess_brief(
        self,
        requirements: DesignRequirements,
        activity: List[dict],
    ) -> dict:
        """Orchestrator's initial assessment of the brief."""
        if not self.api_key:
            assessment = self._heuristic_assessment(requirements)
        else:
            room_list = ", ".join(r.name for r in requirements.rooms)
            rel_list = ", ".join(
                f"{r.room_a}→{r.relationship.value}→{r.room_b}"
                for r in requirements.relationships
            )
            prompt = f"""Assess this architectural design brief.

Plot: {requirements.plot_width}×{requirements.plot_height} ft
Rooms ({len(requirements.rooms)}): {room_list}
Relationships ({len(requirements.relationships)}): {rel_list}

Decide how many design rounds are needed (1-3) and what the main challenge is.
Output JSON."""

            result = self.llm_call(prompt)
            assessment = result if "error" not in result else self._heuristic_assessment(requirements)

        msg = self.log(
            action="Brief assessment complete",
            reasoning=(
                assessment.get("brief_assessment", "")
                + f" Planning {assessment.get('planned_rounds', 2)} design round(s)."
            ),
            payload=assessment,
        )
        activity.append(msg.to_dict())
        return assessment

    def _heuristic_assessment(self, req: DesignRequirements) -> dict:
        num_rooms = len(req.rooms)
        num_rels = len(req.relationships)
        rounds = 1 if num_rooms <= 4 else (2 if num_rooms <= 7 else 3)

        return {
            "brief_assessment": (
                f"Brief has {num_rooms} rooms and {num_rels} spatial relationships. "
                f"Complexity is {'low' if num_rooms <= 4 else ('medium' if num_rooms <= 7 else 'high')}."
            ),
            "planned_rounds": rounds,
            "primary_challenge": (
                "Satisfying all adjacency constraints within the plot boundary."
                if num_rels > 3 else "Fitting all rooms within the plot with good utilization."
            ),
            "success_criteria": "Score >= 0.75 with no critical violations.",
        }

    def _final_summary(
        self,
        req: DesignRequirements,
        round_scores: List[float],
        before_opt: float,
        after_opt: float,
        activity: List[dict],
    ) -> dict:
        """Generate final orchestrator summary."""
        if not self.api_key or not round_scores:
            return self._heuristic_final_summary(round_scores, before_opt, after_opt)

        score_progression = " → ".join(f"{s:.3f}" for s in round_scores)
        prompt = f"""Summarise what the agentic pipeline achieved.

Brief: {req.plot_width}×{req.plot_height} ft plot with {len(req.rooms)} rooms.
Design round scores: {score_progression}
Score before optimization: {before_opt:.3f}
Score after optimization: {after_opt:.3f}
Total improvement: {after_opt - (round_scores[0] if round_scores else before_opt):+.3f}
Total agent actions: {len(activity)}

Write a final summary JSON."""

        result = self.llm_call(prompt)
        if "error" in result:
            return self._heuristic_final_summary(round_scores, before_opt, after_opt)

        msg = self.log(
            action="Pipeline complete",
            reasoning=result.get("final_summary", ""),
            payload={"final_score": round(after_opt, 4)},
        )
        return result

    def _heuristic_final_summary(
        self, round_scores: List[float], before_opt: float, after_opt: float
    ) -> dict:
        improvement = after_opt - (round_scores[0] if round_scores else before_opt)
        score_prog = " → ".join(f"{s:.3f}" for s in round_scores) + f" → {after_opt:.3f} (optimized)"
        return {
            "final_summary": (
                f"Agentic pipeline completed {len(round_scores)} design round(s). "
                f"Final score: {after_opt:.3f} (total improvement: {improvement:+.3f}). "
                f"Score progression: {score_prog}."
            ),
            "score_improvement": score_prog,
            "key_achievements": [
                f"Generated and evaluated floor plans across {len(round_scores)} rounds",
                f"Optimization improved score by {after_opt - before_opt:+.3f}",
            ],
            "remaining_limitations": [
                "Room shapes are rectangular only",
                "No door or window placement",
            ],
        }

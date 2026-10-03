"""
Critic Agent — LLM-powered evaluation with qualitative feedback.

Combines two evaluation layers:
  1. Deterministic: SpatialCritic (geometric scoring, 8 dimensions)
  2. Qualitative: Gemini reasons about the scores and produces
     human-readable suggestions for the DesignAgent to incorporate

The Critic also decides whether the current plan is good enough to stop
(EXCELLENT / ACCEPTABLE) or needs another design round (NEEDS_IMPROVEMENT).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from models import DesignRequirements, FloorPlan
from evaluation.spatial_critic import SpatialCritic, EvaluationResult
from agents.base_agent import BaseAgent, AgentMessage


# Verdict thresholds
EXCELLENT_THRESHOLD = 0.88
ACCEPTABLE_THRESHOLD = 0.70


class CriticAgent(BaseAgent):
    """
    Evaluates floor plans with deterministic scoring + LLM qualitative analysis.
    Returns structured feedback for the DesignAgent.
    """

    NAME = "CriticAgent"

    ROLE_PROMPT = """You are an expert architectural critic agent.
You receive the numerical scores for a floor plan and your job is to:
1. Interpret what the scores mean in practical architectural terms
2. Identify the most impactful improvements
3. Produce specific, actionable suggestions for the floor plan generator
4. Decide whether to stop (the plan is acceptable) or request another design round

Scoring dimensions (each 0-1):
  room_completeness  (0.20 weight): All required rooms present
  room_dimensions    (0.10 weight): Rooms meet minimum size requirements
  overlap_penalty    (0.20 weight): No rooms overlap
  boundary_compliance(0.10 weight): All rooms inside the plot
  adjacency          (0.15 weight): "near" rooms are adjacent
  connectivity       (0.10 weight): "connected_to" rooms share an edge
  separation         (0.05 weight): "away_from" rooms are far apart
  space_utilization  (0.10 weight): 70-90% plot coverage is optimal

Output JSON with this schema:
{
  "qualitative_assessment": "<2-3 sentence overall assessment>",
  "verdict": "<EXCELLENT | ACCEPTABLE | NEEDS_IMPROVEMENT>",
  "weak_dimensions": ["<dimension names scoring below 0.7>"],
  "suggestions": [
    "<specific actionable suggestion for the floor plan generator>"
  ],
  "reasoning": "<why you gave this verdict>"
}"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.8-flash"):
        super().__init__(api_key=api_key, model=model)
        self._critic = SpatialCritic()

    def evaluate(
        self,
        candidates: List[FloorPlan],
        requirements: DesignRequirements,
        round_num: int = 1,
    ) -> Tuple[FloorPlan, EvaluationResult, dict, AgentMessage]:
        """
        Evaluate all candidates, pick the best, then run LLM analysis.

        Returns:
            (best_plan, best_eval, feedback_dict, log_message)
        """
        # ── Deterministic scoring of all candidates ──────────────────────────
        evaluations: List[EvaluationResult] = []
        for plan in candidates:
            ev = self._critic.evaluate(plan, requirements)
            evaluations.append(ev)

        best_idx = max(range(len(candidates)), key=lambda i: evaluations[i].total_score)
        best_plan = candidates[best_idx]
        best_eval = evaluations[best_idx]

        # ── LLM qualitative analysis ──────────────────────────────────────────
        feedback = self._llm_analyse(best_eval, requirements, round_num)

        # Ensure verdict always present
        if "verdict" not in feedback:
            feedback["verdict"] = self._score_to_verdict(best_eval.total_score)

        msg = self.log(
            action=f"Evaluated {len(candidates)} candidate(s) — Round {round_num}",
            reasoning=(
                f"Best score: {best_eval.total_score:.3f}. "
                f"Verdict: {feedback.get('verdict', 'N/A')}. "
                + feedback.get("qualitative_assessment", "")
            ),
            payload={
                "round": round_num,
                "best_score": round(best_eval.total_score, 4),
                "best_candidate_index": best_idx + 1,
                "dimension_scores": {k: round(v, 4) for k, v in best_eval.dimension_scores.items()},
                "violations": [
                    {"category": v.category, "description": v.description}
                    for v in best_eval.violations
                ],
                "verdict": feedback.get("verdict"),
                "suggestions": feedback.get("suggestions", []),
                "weak_dimensions": feedback.get("weak_dimensions", []),
                "qualitative_assessment": feedback.get("qualitative_assessment", ""),
            },
        )

        return best_plan, best_eval, feedback, msg

    # ---- LLM analysis --------------------------------------------------------

    def _llm_analyse(
        self,
        eval_result: EvaluationResult,
        requirements: DesignRequirements,
        round_num: int,
    ) -> dict:
        """Call Gemini to produce qualitative feedback. Falls back to heuristics."""
        if not self.api_key:
            return self._heuristic_feedback(eval_result)

        dim_text = "\n".join(
            f"  {dim}: {score:.3f}" for dim, score in eval_result.dimension_scores.items()
        )
        violation_text = "\n".join(
            f"  [{v.category}] {v.description}" for v in eval_result.violations
        ) or "  None"
        room_list = ", ".join(r.name for r in requirements.rooms)
        rel_text = "\n".join(
            f"  {r.room_a} → {r.relationship.value} → {r.room_b}"
            for r in requirements.relationships
        ) or "  None"

        prompt = f"""Evaluate this floor plan result (Round {round_num}).

Total score: {eval_result.total_score:.4f}
Dimension scores:
{dim_text}

Violations:
{violation_text}

Required rooms: {room_list}
Spatial relationships:
{rel_text}

Provide qualitative assessment and actionable suggestions.
Use verdict EXCELLENT if score >= {EXCELLENT_THRESHOLD},
ACCEPTABLE if >= {ACCEPTABLE_THRESHOLD},
NEEDS_IMPROVEMENT otherwise.
But you may override these thresholds based on architectural judgment.
"""

        result = self.llm_call(prompt)
        if "error" in result:
            return self._heuristic_feedback(eval_result)
        return result

    # ---- heuristic fallback --------------------------------------------------

    def _heuristic_feedback(self, ev: EvaluationResult) -> dict:
        """Rule-based feedback when LLM is unavailable."""
        weak = [dim for dim, score in ev.dimension_scores.items() if score < 0.7]
        suggestions = []

        if ev.dimension_scores.get("adjacency", 1) < 0.7:
            suggestions.append("Rooms with 'near' relationships are too far apart — move them closer together")
        if ev.dimension_scores.get("connectivity", 1) < 0.7:
            suggestions.append("'Connected_to' rooms do not share an edge — they need a shared wall")
        if ev.dimension_scores.get("space_utilization", 1) < 0.6:
            suggestions.append("Space utilization is low — expand rooms to fill more of the plot")
        if ev.dimension_scores.get("overlap_penalty", 1) < 0.8:
            suggestions.append("Rooms are overlapping — generator needs to enforce stricter placement")
        if ev.dimension_scores.get("room_completeness", 1) < 1.0:
            suggestions.append("Some required rooms are missing from the generated plan")

        verdict = self._score_to_verdict(ev.total_score)

        weak_str = ", ".join(weak)
        return {
            "qualitative_assessment": (
                f"Overall score {ev.total_score:.3f}. "
                f"{'Strong performance across dimensions.' if not weak else f'Weak areas: {weak_str}.'}"
            ),
            "verdict": verdict,
            "weak_dimensions": weak,
            "suggestions": suggestions,
            "reasoning": f"Score {ev.total_score:.3f} maps to verdict {verdict} by threshold rules.",
        }

    @staticmethod
    def _score_to_verdict(score: float) -> str:
        if score >= EXCELLENT_THRESHOLD:
            return "EXCELLENT"
        elif score >= ACCEPTABLE_THRESHOLD:
            return "ACCEPTABLE"
        else:
            return "NEEDS_IMPROVEMENT"

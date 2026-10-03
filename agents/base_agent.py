"""
BaseAgent — Foundation class for all LLM-powered agents in PlanAgent.

Every concrete agent inherits this class, which provides:
  - Gemini API interface with structured JSON output
  - Message log (agent's internal reasoning history)
  - Inter-agent communication helpers
  - Graceful fallback handling
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Agent message — the unit of inter-agent communication
# ---------------------------------------------------------------------------

@dataclass
class AgentMessage:
    """A structured message passed between agents or logged as agent activity."""
    agent: str                          # sender name e.g. "CriticAgent"
    action: str                         # short description e.g. "Evaluated Round 1"
    reasoning: str = ""                 # LLM's chain-of-thought or rationale
    payload: Dict[str, Any] = field(default_factory=dict)   # structured data
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "action": self.action,
            "reasoning": self.reasoning,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------

class BaseAgent:
    """
    Base class for all Gemini-powered agents.

    Subclasses should override:
      - NAME         (class attribute)
      - ROLE_PROMPT  (system prompt describing the agent's role)
      - think()      (LLM reasoning step)
      - act()        (algorithmic execution using tools)
    """

    NAME: str = "BaseAgent"
    ROLE_PROMPT: str = "You are a helpful AI agent."

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3.8-flash",
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model
        self.message_log: List[AgentMessage] = []
        self._genai = None   # lazy-loaded google.generativeai module

    # ---- LLM interface -------------------------------------------------------

    def _get_client(self):
        """Lazy-load and return a configured google.genai Client."""
        if self._genai is None:
            from google import genai
            from google.genai import types
            self._genai = genai.Client(api_key=self.api_key)
            self._genai_types = types
        return self._genai

    def llm_call(self, prompt: str, expect_keys: Optional[List[str]] = None) -> dict:
        """
        Call Gemini with a prompt. Returns parsed JSON dict.
        Retries up to 3 times with exponential backoff on transient errors (503/429).
        Falls back to an error dict only if all retries are exhausted.
        """
        if not self.api_key:
            return {"error": "No API key configured"}

        from google.genai import types
        import time as _time

        full_prompt = (
            prompt
            + "\n\nRespond ONLY with valid JSON. No explanations outside the JSON block."
        )

        last_error = "unknown"
        for attempt in range(1, 4):  # 3 attempts
            try:
                client = self._get_client()
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.ROLE_PROMPT,
                        temperature=0.2,
                    ),
                )
                content = response.text.strip()
                # Strip markdown fences
                content = re.sub(r"```json\s*", "", content)
                content = re.sub(r"```\s*", "", content)
                # Extract first JSON block from free-text response
                match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", content)
                if match:
                    content = match.group(1)
                return json.loads(content)

            except Exception as e:
                last_error = str(e)
                # Retry on transient server errors (503, 429, connection issues)
                is_transient = any(
                    code in last_error for code in ("503", "429", "UNAVAILABLE", "timeout", "Connection")
                )
                if is_transient and attempt < 3:
                    wait = 2 ** attempt  # 2s, 4s
                    _time.sleep(wait)
                    continue
                break  # Non-retryable error — stop immediately

        return {"error": last_error}


    # ---- Logging -------------------------------------------------------------

    def log(self, action: str, reasoning: str = "", payload: Optional[dict] = None) -> AgentMessage:
        """Record an action to this agent's message log."""
        msg = AgentMessage(
            agent=self.NAME,
            action=action,
            reasoning=reasoning,
            payload=payload or {},
        )
        self.message_log.append(msg)
        return msg

    def get_activity(self) -> List[dict]:
        """Return the full message log as a list of dicts for the API response."""
        return [m.to_dict() for m in self.message_log]

    def clear_log(self):
        self.message_log.clear()

"""
Requirement Agent — converts natural-language architectural briefs into
structured DesignRequirements.

Two backends:
  1. LLMRequirementAgent  — calls an OpenAI-compatible API (requires API key).
  2. RuleBasedRequirementAgent — deterministic regex/rule parser (no API key).

The pipeline uses the rule-based agent by default so the entire system can
run offline.  Swap in the LLM backend later by passing backend="llm".
"""

from __future__ import annotations

import re
import os
import json
from typing import List, Optional

from models import (
    DesignRequirements,
    RoomRequirement,
    RoomType,
    SpatialRelationship,
    RelationshipType,
)


# ---------------------------------------------------------------------------
# Default room dimensions (ft) — used when the user does not specify sizes
# ---------------------------------------------------------------------------

DEFAULT_ROOM_SPECS = {
    RoomType.BEDROOM:     {"min_w": 12, "min_h": 12, "area": 144},
    RoomType.BATHROOM:    {"min_w": 5,  "min_h": 7,  "area": 40},
    RoomType.KITCHEN:     {"min_w": 8,  "min_h": 10, "area": 100},
    RoomType.LIVING_ROOM: {"min_w": 12, "min_h": 14, "area": 200},
    RoomType.DINING:      {"min_w": 8,  "min_h": 10, "area": 100},
    RoomType.ENTRANCE:    {"min_w": 4,  "min_h": 5,  "area": 25},
    RoomType.HALLWAY:     {"min_w": 3,  "min_h": 8,  "area": 30},
    RoomType.BALCONY:     {"min_w": 4,  "min_h": 6,  "area": 30},
    RoomType.STUDY:       {"min_w": 8,  "min_h": 8,  "area": 64},
    RoomType.POOJA:       {"min_w": 4,  "min_h": 5,  "area": 25},
    RoomType.UTILITY:     {"min_w": 4,  "min_h": 5,  "area": 25},
    RoomType.GARAGE:      {"min_w": 10, "min_h": 18, "area": 200},
    RoomType.STAIRCASE:   {"min_w": 4,  "min_h": 8,  "area": 40},
    RoomType.STORE:       {"min_w": 4,  "min_h": 5,  "area": 25},
}


# ---------------------------------------------------------------------------
# Rule-based parser (deterministic fallback — no API key needed)
# ---------------------------------------------------------------------------

class RuleBasedRequirementAgent:
    """
    Deterministic NLP-lite parser that extracts plot dimensions, rooms, and
    spatial relationships from a natural-language brief using regex rules.
    """

    # Map of patterns → RoomType
    _ROOM_PATTERNS = [
        (r"living\s*room",        RoomType.LIVING_ROOM),
        (r"dining\s*(room|area)", RoomType.DINING),
        (r"bedroom",              RoomType.BEDROOM),
        (r"bathroom|washroom|toilet|restroom", RoomType.BATHROOM),
        (r"kitchen",              RoomType.KITCHEN),
        (r"entrance|foyer|entry", RoomType.ENTRANCE),
        (r"hallway|corridor",     RoomType.HALLWAY),
        (r"balcony",              RoomType.BALCONY),
        (r"study|office",         RoomType.STUDY),
        (r"pooja|prayer",         RoomType.POOJA),
        (r"utility|laundry",      RoomType.UTILITY),
        (r"garage|parking",       RoomType.GARAGE),
        (r"staircase|stairs",     RoomType.STAIRCASE),
        (r"store\s*room|storage", RoomType.STORE),
    ]

    # Relationship phrases
    _NEAR_PHRASES = [
        r"near\b", r"close\s+to", r"adjacent\s+to", r"next\s+to",
        r"beside", r"near\s+the", r"near\s+to",
    ]
    _AWAY_PHRASES = [
        r"away\s+from", r"far\s+from", r"separate\s+from",
        r"not\s+near", r"opposite",
    ]
    _CONNECTED_PHRASES = [
        r"connect(?:ed|s)?\s+to", r"open(?:s|ed)?\s+(?:into|to|onto)",
        r"lead(?:s|ing)?\s+to", r"accessible\s+from",
    ]

    # ---- public API -------------------------------------------------------

    def parse(self, text: str) -> DesignRequirements:
        text_lower = text.lower()
        plot_w, plot_h = self._extract_plot(text_lower)
        rooms = self._extract_rooms(text_lower)
        relationships = self._extract_relationships(text_lower, rooms)

        # Always add an entrance if not already present
        if not any(r.room_type == RoomType.ENTRANCE for r in rooms):
            spec = DEFAULT_ROOM_SPECS[RoomType.ENTRANCE]
            rooms.append(RoomRequirement(
                name="Entrance",
                room_type=RoomType.ENTRANCE,
                min_width=spec["min_w"],
                min_height=spec["min_h"],
                preferred_area=spec["area"],
            ))

        return DesignRequirements(
            plot_width=plot_w,
            plot_height=plot_h,
            rooms=rooms,
            relationships=relationships,
            raw_input=text,
        )

    # ---- internals --------------------------------------------------------

    def _extract_plot(self, text: str) -> tuple[float, float]:
        """Extract plot dimensions like '40 x 60 ft'."""
        patterns = [
            r"(\d+(?:\.\d+)?)\s*[x×by]\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|sq\.?\s*ft)?",
            r"(\d+(?:\.\d+)?)\s*(?:ft|feet)\s*[x×by]\s*(\d+(?:\.\d+)?)\s*(?:ft|feet)?",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return float(m.group(1)), float(m.group(2))
        return 40.0, 60.0  # sensible default

    def _extract_rooms(self, text: str) -> List[RoomRequirement]:
        """Identify required rooms from the text."""
        rooms: List[RoomRequirement] = []
        # Check for explicit counts like "two bedrooms", "2 bathrooms"
        word_to_num = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
        }

        for pattern, rtype in self._ROOM_PATTERNS:
            # Try to find a count before the room word
            count = 1
            count_pat = r"(?:(\d+|one|two|three|four|five|six)\s+)?" + pattern
            matches = list(re.finditer(count_pat, text))
            if matches:
                for m in matches:
                    if m.group(1):
                        count = word_to_num.get(m.group(1).lower(), 1)
                    break  # use the first match for count

                spec = DEFAULT_ROOM_SPECS.get(rtype, {"min_w": 8, "min_h": 8, "area": 64})
                for i in range(count):
                    suffix = f" {i+1}" if count > 1 else ""
                    name = rtype.value.replace("_", " ").title() + suffix
                    rooms.append(RoomRequirement(
                        name=name,
                        room_type=rtype,
                        min_width=spec["min_w"],
                        min_height=spec["min_h"],
                        preferred_area=spec["area"],
                    ))

        return rooms

    def _extract_relationships(
        self, text: str, rooms: List[RoomRequirement]
    ) -> List[SpatialRelationship]:
        """Extract spatial relationships from natural-language sentences."""
        rels: List[SpatialRelationship] = []
        sentences = re.split(r"[.,;]", text)

        # Build lookup: type keyword → list of room names
        type_to_names = {}
        for r in rooms:
            key = r.room_type.value.replace("_", " ")
            type_to_names.setdefault(key, []).append(r.name)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            rel_type = self._classify_relationship(sentence)
            if rel_type is None:
                continue

            # First try plural expansion (e.g. "bedrooms near bathrooms")
            pairs = self._expand_plural_rooms(sentence, rooms)
            if pairs:
                for a, b in pairs:
                    if a != b:
                        rels.append(SpatialRelationship(
                            room_a=a, room_b=b, relationship=rel_type,
                        ))
                continue

            # Otherwise find distinct room types mentioned
            mentioned = self._find_mentioned_rooms(sentence, rooms)
            if len(mentioned) >= 2:
                rels.append(SpatialRelationship(
                    room_a=mentioned[0],
                    room_b=mentioned[1],
                    relationship=rel_type,
                ))

        return rels

    def _classify_relationship(self, sentence: str) -> Optional[RelationshipType]:
        for pat in self._CONNECTED_PHRASES:
            if re.search(pat, sentence):
                return RelationshipType.CONNECTED_TO
        for pat in self._AWAY_PHRASES:
            if re.search(pat, sentence):
                return RelationshipType.AWAY_FROM
        for pat in self._NEAR_PHRASES:
            if re.search(pat, sentence):
                return RelationshipType.NEAR
        return None

    def _find_mentioned_rooms(
        self, sentence: str, rooms: List[RoomRequirement]
    ) -> List[str]:
        """Return one representative room name per distinct room type mentioned."""
        found = []
        seen_types = set()
        for r in rooms:
            type_keyword = r.room_type.value.replace("_", " ")
            if type_keyword in sentence and type_keyword not in seen_types:
                found.append(r.name)
                seen_types.add(type_keyword)
        return found

    def _expand_plural_rooms(
        self, sentence: str, rooms: List[RoomRequirement]
    ) -> List[tuple]:
        """Handle 'bedrooms near bathrooms' → pair Bedroom i with Bathroom i."""
        type_mentions = []
        for pattern, rtype in self._ROOM_PATTERNS:
            if re.search(pattern, sentence):
                matching = [r.name for r in rooms if r.room_type == rtype]
                if matching:
                    type_mentions.append(matching)
        if len(type_mentions) >= 2:
            list_a, list_b = type_mentions[0], type_mentions[1]
            # If same length, pair by index (Bedroom 1↔Bathroom 1)
            if len(list_a) == len(list_b):
                return list(zip(list_a, list_b))
            # Otherwise cross-product
            return [(a, b) for a in list_a for b in list_b]
        return []


# ---------------------------------------------------------------------------
# LLM-based parser (Gemini — requires GEMINI_API_KEY)
# ---------------------------------------------------------------------------

class LLMRequirementAgent:
    """
    Uses Google Gemini API to convert natural-language architectural briefs
    into structured JSON requirements.

    Requires:
        pip install google-generativeai

    Configuration:
        Set the GEMINI_API_KEY environment variable, or pass api_key directly.
        Falls back to RuleBasedRequirementAgent if no API key is available.
    """

    SYSTEM_PROMPT = """You are an expert architectural requirement extraction agent.
Given a natural-language architectural brief, extract ALL of the following:

1. plot_width and plot_height in feet (numeric values).
2. A list of rooms. For each room provide:
   - name (string, e.g. "Bedroom 1", "Kitchen")
   - room_type: MUST be one of: bedroom, bathroom, kitchen, living_room, dining, entrance, hallway, balcony, study, pooja, utility, garage, staircase, store
   - min_width (float, feet — use sensible architectural defaults if not specified)
   - min_height (float, feet)
   - preferred_area (float, square feet)
3. A list of spatial relationships. For each provide:
   - room_a (string, must match a room name from the rooms list)
   - room_b (string, must match a room name from the rooms list)
   - relationship: MUST be one of: near, away_from, connected_to

Rules:
- Always include an "Entrance" room if the user doesn't mention one explicitly.
- If the user says "2BHK" that means 2 bedrooms. "3BHK" means 3 bedrooms.
- Use realistic Indian residential room dimensions as defaults.
- "near" means rooms should be adjacent. "connected_to" means rooms share a doorway. "away_from" means rooms should be far apart.

Respond ONLY with valid JSON (no markdown fences, no commentary). The JSON schema:
{
  "plot_width": <float>,
  "plot_height": <float>,
  "rooms": [{"name": "<str>", "room_type": "<str>", "min_width": <float>, "min_height": <float>, "preferred_area": <float>}],
  "relationships": [{"room_a": "<str>", "room_b": "<str>", "relationship": "<str>"}]
}"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3.8-flash",
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model
        self._fallback = RuleBasedRequirementAgent()

    def parse(self, text: str) -> DesignRequirements:
        if not self.api_key:
            print("[RequirementAgent] No GEMINI_API_KEY found — using rule-based parser.")
            return self._fallback.parse(text)
        try:
            return self._call_gemini(text)
        except Exception as e:
            print(f"[RequirementAgent] Gemini call failed ({e}) — falling back to rules.")
            return self._fallback.parse(text)

    def _call_gemini(self, text: str) -> DesignRequirements:
        """Call Google Gemini API using the new google-genai SDK with retry logic."""
        import time as _time
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        full_prompt = (
            text
            + "\n\nRespond ONLY with valid JSON matching the schema above. No explanations outside the JSON block."
        )

        last_error = "unknown"
        for attempt in range(1, 4):
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.SYSTEM_PROMPT,
                        temperature=0.1,
                    ),
                )
                content = response.text.strip()
                content = re.sub(r"```json\s*", "", content)
                content = re.sub(r"```\s*", "", content)
                match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", content)
                if match:
                    content = match.group(1)

                d = json.loads(content)
                d["raw_input"] = text

                valid_types = {rt.value for rt in RoomType}
                for room in d.get("rooms", []):
                    if room.get("room_type") not in valid_types:
                        rt = room["room_type"].lower().replace(" ", "_")
                        room["room_type"] = rt if rt in valid_types else "study"

                for rel in d.get("relationships", []):
                    if rel.get("relationship") not in {"near", "away_from", "connected_to"}:
                        rel["relationship"] = "near"

                return DesignRequirements.from_dict(d)

            except Exception as e:
                last_error = str(e)
                is_transient = any(
                    code in last_error
                    for code in ("503", "429", "UNAVAILABLE", "timeout", "Connection")
                )
                if is_transient and attempt < 3:
                    _time.sleep(2 ** attempt)
                    continue
                break

        raise RuntimeError(f"Gemini API call failed after retries: {last_error}")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_requirement_agent(
    backend: str = "rules",
    api_key: Optional[str] = None,
) -> "RuleBasedRequirementAgent | LLMRequirementAgent":
    """
    Create a requirement parsing agent.

    Args:
        backend: "rules" for deterministic regex parser,
                 "llm" for Google Gemini-powered parser.
        api_key: Optional Gemini API key. If None, reads GEMINI_API_KEY env var.
    """
    if backend == "llm":
        return LLMRequirementAgent(api_key=api_key)
    return RuleBasedRequirementAgent()


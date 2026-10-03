# Project Context Rules — PlanAgent

## Critical Rules

1. **Always read `AGENTS.md` and `docs/CURRENT_STATUS.md` before making changes.**
2. **Do NOT change scoring weights** in `evaluation/spatial_critic.py` without explicit user approval.
3. **Do NOT change enum values** in `models.py` (`RoomType`, `RelationshipType`) — they are referenced across backend, frontend JS, CSS, and Gemini prompts.
4. **Do NOT change the `/api/pipeline` route** — the frontend JS hardcodes it.
5. **Matplotlib must use `"Agg"` backend** — set before any pyplot import.
6. **Preserve the LLM→rule-based fallback** in `requirement_agent.py` — it is intentional resilience.
7. **Never store API keys server-side** — they are passed per-request from the frontend.

## Architecture Constraints

- Python 3.10+, Flask, vanilla HTML/CSS/JS (no React, no Tailwind)
- No database — all data is in-memory; outputs go to `output/` directory
- Images in API responses are base64-encoded PNGs, not file URLs
- Dark UI theme: figure background `#0f1117`, axes background `#181c25`

## After Every Task

1. Run `python tests/test_pipeline.py` to verify nothing broke
2. Update `docs/CURRENT_STATUS.md` with what changed
3. Update `docs/DECISIONS.md` if a significant architectural decision was made

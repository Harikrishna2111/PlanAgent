# Development Workflow for AI Coding Agents

> This document defines how an AI coding agent should approach work on the PlanAgent project.

---

## BEFORE MAKING CHANGES

Follow these steps in order:

### 1. Read project context
```
Read: AGENTS.md                    — full project architecture, stack, constraints
Read: docs/CURRENT_STATUS.md       — what's done, what's broken, what's next
Read: docs/DECISIONS.md            — why things are the way they are
```

### 2. Check version control state
```bash
git status
git log --oneline -n 10
```

### 3. Inspect relevant existing code
- Read the actual source files related to your task
- Do NOT rely solely on README or documentation — verify against code
- Understand the data flow: `models.py` → `requirement_agent.py` → `graph.py` → `floor_plan_generator.py` → `spatial_critic.py` → `optimization_agent.py` → `renderer.py`

### 4. Understand the current implementation
- Trace the pipeline flow in `app.py` (web) or `run_pipeline.py` (CLI)
- Check how data models serialize/deserialize (`to_dict` / `from_dict`)
- Note which modules import from which — see dependency map in `AGENTS.md`

---

## WHILE WORKING

### Do
- Make the **smallest appropriate changes** that solve the task
- **Preserve existing working functionality** — run tests to verify
- Follow the **existing code style**: Python with type hints, docstrings, `from __future__ import annotations`
- Keep data model changes **backward-compatible** (add fields with defaults)
- Use `Optional` typing for new optional parameters
- Match the **dark UI theme** if modifying frontend (background: `#0f1117`, card: `rgba(14,17,26,0.72)`)
- Keep matplotlib figures using `"Agg"` backend
- Set dark backgrounds on matplotlib figures in `app.py` (`#0f1117` for figure, `#181c25` for axes)

### Don't
- Don't introduce new dependencies without good reason
- Don't rewrite working modules — modify them surgically
- Don't change `DEFAULT_WEIGHTS` in `spatial_critic.py` without explicit instruction
- Don't change enum values in `models.py` — they're used across backend and frontend
- Don't change the `/api/pipeline` route path — frontend hardcodes it
- Don't use a different matplotlib backend — `"Agg"` is required for Flask
- Don't remove the LLM-to-rules fallback in `requirement_agent.py`
- Don't store API keys on the server side

### Track your work
- Keep a mental list of files changed
- Note any new decisions made
- Note any new dependencies added
- Note any behavioral changes to existing features

---

## AFTER COMPLETING A TASK

### 1. Test the implementation
```bash
# Run unit tests
python tests/test_pipeline.py

# Test web server starts
python app.py
# Verify http://localhost:5000 loads

# If you changed the pipeline, run CLI
python -X utf8 run_pipeline.py
```

### 2. Inspect the final diff
```bash
git diff
git status
```

### 3. Update documentation

**Update `docs/CURRENT_STATUS.md`:**
- Move completed items to the "completed" section
- Add new items to "in progress" or "remaining"
- Update "files recently modified"
- Add any new bugs/limitations discovered
- Update "immediate next steps"

**Update `docs/DECISIONS.md`** if you made a significant architectural decision:
- Add a new numbered entry with: Date, Decision, Reason, Alternatives, Consequences

### 4. Report to the user
Clearly state:
- What was changed (files and behavior)
- What remains to be done
- Any unresolved issues or risks
- Any new dependencies added

---

## Key Files Quick Reference

| Need to... | Read this file |
|------------|---------------|
| Understand data structures | `models.py` |
| Change NL parsing | `agents/requirement_agent.py` |
| Change optimization | `agents/optimization_agent.py` |
| Change scoring | `evaluation/spatial_critic.py` |
| Change plan generation | `generation/floor_plan_generator.py` |
| Change visualizations | `visualization/renderer.py` |
| Change web API | `app.py` |
| Change web UI | `web/templates/index.html`, `web/static/js/app.js`, `web/static/css/style.css` |
| Change CLI | `run_pipeline.py` |
| Add tests | `tests/test_pipeline.py` |
| Add dependencies | `requirements.txt` |

---

## Common Pitfalls

1. **Forgetting to close matplotlib figures** — Always use `plt.close(fig)` after saving/encoding, or memory will leak under Flask.
2. **Breaking the frontend by changing API response shape** — The JS in `app.js` expects specific keys in the pipeline response. If you add/rename keys, update the JS too.
3. **Room type mismatch** — `ROOM_COLORS` and `ROOM_ICONS` in `app.js` must match `RoomType` enum values in `models.py`. If you add a room type, update both.
4. **CSS specificity** — The CSS file is large (~2500 lines). Use the browser inspector to find existing styles before adding new ones.
5. **Seed values** — Generation and optimization use `seed=42` for reproducibility. Change seeds deliberately, not accidentally.

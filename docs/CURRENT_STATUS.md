# Current Project Status

> **Last Updated**: 2026-10-02
> **Updated By**: AI Agent (Antigravity IDE)

---

## Overall Status
🟡 **50% Milestone Prototype — Functional with recent enhancements**

The core pipeline (NL parsing → spatial graph → generation → evaluation → optimization → visualization) is fully working via both CLI and web UI. Gemini LLM integration was recently added but has not been fully tested with a live API key.

---

## What Has Been Completed

### Core Pipeline (all working)
- [x] Rule-based natural language requirement parser (`RuleBasedRequirementAgent`)
- [x] Gemini LLM-based requirement parser (`LLMRequirementAgent`) — NEW, uses `gemini-2.0-flash`
- [x] Spatial relationship graph construction (NetworkX)
- [x] Constraint-based procedural floor plan generation (strip-packing heuristic)
- [x] 8-dimension deterministic spatial critic (scoring + violations)
- [x] Two-phase optimization (greedy expansion + simulated annealing)
- [x] Visualization: floor plans, spatial graphs, comparison views, convergence charts
- [x] CLI pipeline runner (`run_pipeline.py`) with argparse
- [x] Web UI (`app.py` + `web/`) — premium dark glassmorphic design

### Web UI Features
- [x] Dark-themed glassmorphic design with particle canvas background
- [x] Animated hero section with stats
- [x] 5-step pipeline flow indicator with animation
- [x] Textarea input with character count and `Ctrl+Enter` shortcut
- [x] Candidate count / iteration stepper controls
- [x] Backend selector (Rule-based / Gemini LLM)
- [x] Gemini API key input panel (shows/hides based on backend selection)
- [x] API key persistence in browser localStorage
- [x] 4 example prompt templates (2BHK, 3BHK Villa, Studio, Office)
- [x] Loading overlay with step-by-step progress animation
- [x] Score gauges (SVG circular with count-up animation)
- [x] Tabbed results: Optimization, Candidates, Spatial Graph, Requirements, Scoring & Audit
- [x] Before/after comparison view
- [x] Optimization convergence chart
- [x] Dual-track dimension score bars (before vs after)
- [x] Violations list with resolved/remaining indicators
- [x] Optimized room details table
- [x] Lightbox for full-size image viewing with download
- [x] JSON export of complete results
- [x] Mobile-responsive navigation with hamburger menu

### Testing
- [x] 18 unit tests covering pipeline stages (all passing as of last run)
- [ ] No tests for Flask API endpoints
- [ ] No tests for Gemini LLM integration
- [ ] No tests for frontend

---

## What Is Currently Being Worked On
- Nothing actively in progress. Last session completed Gemini LLM integration.

---

## What Remains to Be Implemented

### High Priority
- [ ] Test Gemini LLM integration with a live API key end-to-end
- [ ] BIM model generation (IFC export)
- [ ] Building code compliance checking

### Medium Priority
- [ ] Cost estimation module
- [ ] Daylight and ventilation analysis
- [ ] Energy performance simulation
- [ ] Multi-storey support
- [ ] Room proportion constraints during greedy expansion

### Low Priority
- [ ] HouseGAN++ integration for learned generation
- [ ] API endpoint tests
- [ ] Frontend tests (e.g., Playwright/Cypress)
- [ ] CI/CD pipeline
- [ ] Docker containerization

---

## Current Bugs / Issues
- **protobuf version conflict**: `pip install google-generativeai` installed `protobuf==5.29.6` which conflicts with `tf2onnx` (requires `protobuf~=3.20`). This is a warning only — does not affect PlanAgent functionality.
- **No error boundary in frontend**: If the pipeline API returns an unexpected shape, the JS may silently fail to render some sections.

---

## Known Limitations
1. Floor plan generation uses a **procedural heuristic** (strip-packing), not a learned model — quality is acceptable but not optimal.
2. The spatial critic uses **deterministic geometric scoring** — no AI/ML in evaluation.
3. Simulated annealing uses a **fixed cooling schedule** (T₀=0.15, rate=0.997) — not adaptive.
4. Room shapes are **rectangular only** — no L-shapes, curves, or irregular geometries.
5. Single floor only — **no multi-storey** support.
6. Matplotlib renders **static PNG images** for plans — no interactive SVG/Canvas rendering in the browser.
7. No **door/window placement** — rooms only show rectangular boundaries.
8. No **persistent storage** — results exist only in memory during a session; output files are overwritten each run.
9. The web UI sends the Gemini API key **in plaintext** over the network (ok for localhost, not for production).

---

## Files Recently Modified (uncommitted)

| File | Change |
|------|--------|
| `agents/requirement_agent.py` | Replaced OpenAI `LLMRequirementAgent` with Google Gemini-based implementation using `google-generativeai` SDK |
| `app.py` | Added `api_key` extraction from request body, validation for LLM backend, passthrough to `create_requirement_agent()` |
| `requirements.txt` | Added `google-generativeai>=0.8.0` |
| `web/templates/index.html` | Added Gemini API key panel (input, save, visibility toggle), updated backend dropdown labels |
| `web/static/js/app.js` | Added `initGeminiApiKey()`, `toggleApiKeyPanel()`, `toggleApiKeyVisibility()`, `saveApiKey()`, updated `runPipeline()` to send `api_key` |
| `web/static/css/style.css` | Added ~190 lines of CSS for `.api-key-panel`, `.api-key-input`, `.api-key-save-btn`, etc. |
| `README.md` | Updated implementation status sections to reflect Gemini integration and web UI |

---

## Important Implementation Details

### Gemini LLM Integration
- Uses `google-generativeai` SDK (v0.8.6 installed)
- Default model: `gemini-2.0-flash`
- Uses `response_mime_type="application/json"` for structured output
- System prompt requests JSON matching `DesignRequirements` schema
- Validates room_type and relationship values before constructing dataclasses
- Falls back to `RuleBasedRequirementAgent` on any error
- API key can come from: (1) request body `api_key` field, (2) `GEMINI_API_KEY` env var

### Optimization Parameters
- Greedy expansion: up to 50 iterations, 1ft step, rooms capped at 3× preferred area
- SA: T₀=0.15, cooling=0.997, 5 mutation operators with weights [move:1.0, resize:0.5, swap:0.8, nudge:2.5, expand:1.5]
- History logged every 50 iterations

### Frontend State
- `pipelineResult` global holds last API response
- API key stored in `localStorage` under key `planagent_gemini_key`
- Tab indicator uses absolute positioning with JS-computed offsets

---

## Database Changes
N/A — No database is used.

## API Changes
- `POST /api/pipeline` now accepts optional `api_key` field in request body (added for Gemini integration)

---

## Immediate Next Steps
1. Commit the Gemini integration changes
2. Test Gemini LLM parsing with a real API key
3. Add API endpoint tests

---

## Longer-term TODOs
1. BIM/IFC export module
2. Building code compliance
3. Multi-storey support
4. Replace procedural generator with HouseGAN++ or similar
5. Interactive floor plan editing in the browser
6. Docker deployment configuration

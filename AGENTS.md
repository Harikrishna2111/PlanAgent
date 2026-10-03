# AGENTS.md — PlanAgent Project Context

## Project Name
**PlanAgent** — Agentic AI Framework for Constraint-Aware Architectural Design and BIM-Based Decision Support

## Purpose
Academic project (50% milestone prototype) that converts natural-language architectural briefs into optimized 2D floor plans through a multi-agent pipeline: NL parsing → spatial graph → procedural generation → constraint evaluation → simulated annealing optimization → visualization.

---

## Technology Stack

| Layer | Technology | Version Constraint |
|-------|-----------|-------------------|
| Language | Python 3.10+ | Uses `from __future__ import annotations` throughout |
| Web Framework | Flask | `>=2.3.0` |
| Graph Library | NetworkX | `>=2.8` |
| Visualization | Matplotlib | `>=3.5.0` |
| Numerical | NumPy | `>=1.21.0` |
| Image | Pillow | `>=9.0.0` |
| LLM SDK | google-generativeai | `>=0.8.0` |
| Frontend | Vanilla HTML/CSS/JS | No framework (no React, no Tailwind) |
| Fonts | Google Fonts | Inter, JetBrains Mono, Outfit |

**No database is used.** All data is in-memory during pipeline execution; outputs are saved as JSON/PNG files to the `output/` directory.

---

## Architecture Overview

```
Natural Language Input
        ↓
┌─────────────────────────────────┐
│ Requirement Agent               │  agents/requirement_agent.py
│ (Rule-based OR Gemini LLM)      │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ Spatial Graph (NetworkX)        │  spatial/graph.py
│ (+ inferred default relations)  │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ Floor-Plan Generator            │  generation/floor_plan_generator.py
│ (Strip-packing heuristic)       │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ Spatial Critic                  │  evaluation/spatial_critic.py
│ (8-dimension deterministic)     │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ Optimization Agent              │  agents/optimization_agent.py
│ (Greedy + targeted SA + polish) │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ Visualization Renderer          │  visualization/renderer.py
└─────────────────────────────────┘
```

### Two entry points:
1. **CLI**: `python run_pipeline.py` — runs the full pipeline and saves output to `output/`
2. **Web UI**: `python app.py` — Flask server at `http://localhost:5000` with REST API

---

## Project Structure

```
PlanAgent/
├── AGENTS.md                         ← This file
├── README.md                         # Original project README
├── models.py                         # Core dataclasses (Room, FloorPlan, Requirements, enums)
├── app.py                            # Flask web server + REST API
├── run_pipeline.py                   # CLI orchestrator
├── run.bat                           # Windows convenience script
├── requirements.txt                  # Python dependencies
│
├── agents/
│   ├── __init__.py
│   ├── requirement_agent.py          # NL→structured reqs (RuleBased + Gemini LLM)
│   └── optimization_agent.py         # Greedy expansion + Simulated Annealing
│
├── spatial/
│   ├── __init__.py
│   └── graph.py                      # NetworkX graph builder
│
├── generation/
│   ├── __init__.py
│   └── floor_plan_generator.py       # Constraint-based procedural generator
│
├── evaluation/
│   ├── __init__.py
│   └── spatial_critic.py             # 8-dimension deterministic scorer
│
├── visualization/
│   ├── __init__.py
│   └── renderer.py                   # Matplotlib renderers (plans, graphs, history)
│
├── web/
│   ├── templates/
│   │   └── index.html                # Single-page app template (Jinja2)
│   └── static/
│       ├── css/style.css             # Premium dark glassmorphic UI (~2500 lines)
│       └── js/app.js                 # Frontend logic, particles, gauges, API calls
│
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py              # 18 unit tests (unittest)
│
├── output/                           # Generated artifacts (gitignored content)
│   ├── requirements.json
│   ├── spatial_graph.png
│   ├── floor_plan_before.png
│   ├── floor_plan_after.png
│   ├── comparison.png
│   ├── all_candidates.png
│   ├── optimization_history.png
│   ├── pipeline_results.json
│   └── evaluation_details.json
│
└── docs/                             # Project documentation
    ├── CURRENT_STATUS.md
    ├── DECISIONS.md
    └── DEVELOPMENT_WORKFLOW.md
```

---

## Core Data Models (`models.py`)

### Enums
- `RoomType`: bedroom, bathroom, kitchen, living_room, dining, entrance, hallway, balcony, study, pooja, utility, garage, staircase, store
- `RelationshipType`: near, away_from, connected_to

### Key Dataclasses
- `RoomRequirement`: name, room_type, min_width, min_height, preferred_area
- `SpatialRelationship`: room_a, room_b, relationship
- `DesignRequirements`: plot_width, plot_height, rooms[], relationships[], raw_input
- `Room`: name, room_type, x, y, width, height (with geometry methods: overlaps, shares_edge, distance_to, overlap_area)
- `FloorPlan`: plot_width, plot_height, rooms[], score, score_details

All models have `to_dict()` / `from_dict()` / `to_json()` / `from_json()` serialization.

---

## Scoring Dimensions (Spatial Critic)

| Dimension | Weight | Description |
|-----------|--------|-------------|
| room_completeness | 0.20 | All required rooms present |
| room_dimensions | 0.10 | Rooms meet min size (80% threshold) |
| overlap_penalty | 0.20 | No room overlaps |
| boundary_compliance | 0.10 | All rooms inside plot |
| adjacency | 0.15 | "near" rooms are adjacent |
| connectivity | 0.10 | "connected_to" rooms share edge |
| separation | 0.05 | "away_from" rooms far apart (30% of plot diagonal) |
| space_utilization | 0.10 | 70-90% coverage is optimal |

Weights are defined in `evaluation/spatial_critic.py` as `DEFAULT_WEIGHTS`.

A **circulation** check (every room reachable from the Entrance through rooms that share a wall) is also run. It only adds `circulation` violations and is **not** part of the weighted score.

### Implicit relationships
`spatial.graph.add_implicit_relationships()` runs right after requirement parsing (in `app.py`, `run_pipeline.py` and the orchestrator). It adds Kitchen→near→Dining, Bedroom i→near→Bathroom i, Bedroom→away_from→Entrance and Living Room→connected_to→Entrance, unless the brief already relates that room pair.

### Optimization phases
1. Greedy expansion to raise utilization
2. Simulated annealing: half the steps repair the weakest repairable dimension (sampled by `weight × (1 − score)`), half are random moves/resizes/swaps/expansions
3. Polish: trims overlapping walls and reconnects rooms cut off from the entrance, only when this reduces violations without lowering the score

---

## API Structure

### `POST /api/pipeline`

**Request body** (JSON):
```json
{
  "input": "Design a 2BHK house on a 40x60 ft plot...",
  "candidates": 5,
  "iterations": 300,
  "backend": "rules",
  "api_key": "optional-gemini-key"
}
```

**Response** (JSON): Contains requirements, graph_summary, spatial_graph_img (base64), candidates[] (with base64 images), before/after scores, dimension_scores, violation_details, plan images (base64), history, optimized_rooms, utilization values, elapsed time.

All images are embedded as base64 PNG strings — no file URLs are returned.

### Other Routes
- `GET /` — serves `index.html`
- `GET /favicon.ico` — returns 204
- `GET /output/<filename>` — serves files from `output/` directory

---

## Frontend Structure

Single-page app in `web/templates/index.html`:
- **Particle canvas background** with ambient gradient orbs
- **Hero section** with stats badges
- **Pipeline flow indicator** (5-step visual)
- **Input section**: textarea, candidate/iteration steppers, backend selector, Gemini API key panel, example templates
- **Loading overlay** with step-by-step progress animation
- **Results section** with tabbed interface:
  - Optimization (before/after comparison + convergence chart)
  - Candidates (grid of all generated plans)
  - Spatial Graph (relationship visualization)
  - Requirements (rooms list + relationships)
  - Scoring & Audit (dimension bars + violations table + room details)
- **Lightbox** for full-size image viewing
- **Export** — JSON download of full results

Frontend JS (`web/static/js/app.js`): ~900 lines handling particles, tab management, API calls, result rendering, gauges, lightbox, API key management (localStorage).

---

## Authentication / Authorization
- **None** — no user authentication system.
- Gemini API key is passed per-request from the frontend. It is stored in `localStorage` on the client side and never persisted on the server.
- The `GEMINI_API_KEY` environment variable is also checked as a fallback.

---

## Environment / Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Optional | Fallback Gemini API key (if not passed per-request from UI) |
| Python 3.10+ | Required | Uses `__future__` annotations, `match` not used |

No `.env` file exists. No config files beyond `requirements.txt`.

Flask runs with `debug=False`, `host=0.0.0.0`, `port=5000`.
Matplotlib uses `"Agg"` backend (non-interactive, required for server use).

---

## Things an AI Agent MUST NOT Change Without Asking

1. **Scoring weights** in `evaluation/spatial_critic.py` — these are calibrated and affect all pipeline outputs
2. **Data model schemas** in `models.py` — all modules depend on the `to_dict()`/`from_dict()` contract
3. **Room type enum values** in `models.py` — used as keys across frontend JS, CSS, backend, and Gemini prompts
4. **The 8 scoring dimensions** — adding/removing dimensions requires coordinated changes across critic, frontend, and tests
5. **Flask route paths** — the frontend JS hardcodes `/api/pipeline`
6. **Matplotlib backend** — must remain `"Agg"` for server deployment
7. **The fallback behavior** of `LLMRequirementAgent` → `RuleBasedRequirementAgent` — this is intentional resilience

---

## Important Dependencies and Interactions

- `generation/floor_plan_generator.py` imports from `spatial/graph.py` — it builds its own spatial graph internally
- `agents/optimization_agent.py` imports `SpatialCritic` directly — critic is used inside the SA loop
- `visualization/renderer.py` imports from `spatial/graph.py` to render the graph
- `app.py` imports from ALL modules — it is the integration point
- `run_pipeline.py` is the CLI equivalent of `app.py` but saves to files instead of returning JSON

---

## Testing

```bash
# Run all 18 tests
python tests/test_pipeline.py

# Or with pytest
python -m pytest tests/test_pipeline.py -v
```

Tests cover: requirement parsing, plot extraction, room extraction, relationship extraction, entrance auto-addition, JSON serialization, graph construction, graph summary, candidate generation, boundary compliance, overlap detection, scoring, dimension presence, optimization execution, optimization non-regression, room geometry (overlap, edge-sharing, distance).

Tests do **not** cover: Flask API, LLM backend, visualization rendering, frontend behavior.

---

## Running / Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI pipeline
python -X utf8 run_pipeline.py
python -X utf8 run_pipeline.py --input "Design a 3BHK..." --candidates 8 --iterations 1000

# Run web server
python app.py
# Open http://localhost:5000

# Run tests
python tests/test_pipeline.py

# Windows shortcut
run.bat
```

---

## Deployment
No deployment configuration exists. The project runs locally only. No Docker, no CI/CD, no cloud deployment.

---

## Git History
- **Commit 1** (`5ea7bff`, 2026-10-01): Initial model files and pipeline
- **Commit 2** (`c84db07`, 2026-10-01): Added web UI
- **Uncommitted changes**: Gemini LLM integration, API key UI panel, updated requirements.txt, updated README

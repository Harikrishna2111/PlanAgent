# Agentic AI Framework for Constraint-Aware Architectural Design

**50% Milestone — Working Prototype**

## Overview

Multi-agent pipeline that converts natural-language architectural briefs into
optimized 2D floor plans through:

```
User · natural-language requirement
        ↓
1. Requirement Agent (LLM)              → extracted requirements
        ↓
2. Spatial Planning Agent (reasoning)   → spatial graph
        ↓
3. Floor-Plan Generation Model          → candidate layouts
        ↓
4. Spatial Critic Agent (evaluation)    → spatial score
        ↓
5. Optimization Agent (refinement)      → refined layout
        ↓
Optimized floor plan + spatial representation & score
```

Each stage is handled by a specialized model, and the layout is improved
through a closed generate → evaluate → improve → re-evaluate loop rather than
produced in a single pass.

**Base paper:** A. B. Yenew, B. G. Assefa and E. G. Belay, "HouseGanDi: A Hybrid
Approach to Strike a Balance of Sampling Time and Diversity in Floorplan
Generation," *IEEE Access*, vol. 12, pp. 125235–125252, 2024.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the default 2BHK example
python -X utf8 run_pipeline.py

# Custom input
python -X utf8 run_pipeline.py --input "Design a 3BHK house on a 50x70 ft plot with three bedrooms, three bathrooms, kitchen, living room, dining area and study. The kitchen should be near the dining area."

# More candidates and iterations
python -X utf8 run_pipeline.py --candidates 8 --iterations 1000

# Run tests
python tests/test_pipeline.py
```

## Project Structure

```
PlanAgent/
├── models.py                         # Core data models (Room, FloorPlan, Requirements)
├── run_pipeline.py                   # End-to-end orchestrator + CLI
├── run.bat                           # Windows convenience runner
├── requirements.txt                  # Python dependencies
│
├── agents/
│   ├── requirement_agent.py          # NL → structured requirements
│   └── optimization_agent.py         # Greedy expansion + SA optimizer
│
├── spatial/
│   └── graph.py                      # Spatial relationship graph (NetworkX)
│
├── generation/
│   └── floor_plan_generator.py       # Floor-Plan Generation Model
│
├── evaluation/
│   └── spatial_critic.py             # Deterministic 8-dimension scoring
│
├── visualization/
│   └── renderer.py                   # Floor plan + graph + convergence plots
│
├── tests/
│   └── test_pipeline.py              # 18 unit tests
│
└── output/                           # Generated outputs
    ├── requirements.json
    ├── spatial_graph.png
    ├── floor_plan_before.png
    ├── floor_plan_after.png
    ├── comparison.png
    ├── all_candidates.png
    ├── optimization_history.png
    ├── pipeline_results.json
    └── evaluation_details.json
```

## Scoring Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Room Completeness | 0.20 | All required rooms present |
| Room Dimensions | 0.10 | Rooms meet minimum size requirements |
| Overlap Penalty | 0.20 | No room overlaps |
| Boundary Compliance | 0.10 | All rooms inside plot |
| Adjacency | 0.15 | "near" rooms are adjacent |
| Connectivity | 0.10 | "connected_to" rooms share an edge |
| Separation | 0.05 | "away_from" rooms are far apart |
| Space Utilization | 0.10 | 70-90% plot coverage is optimal |

A circulation check (every room reachable from the entrance) is also reported as violations.

## Implementation Status

### ✅ Implemented (50% Milestone)
- Natural language requirement parsing (rule-based + LLM-ready)
- Structured requirement extraction (plot, rooms, relationships)
- Spatial relationship graph
- Constraint-based procedural floor-plan generation
- Multi-candidate generation with diversity
- Deterministic 8-dimension spatial critic
- Two-phase optimization (greedy expansion + simulated annealing)
- 2D floor plan visualization
- Spatial graph visualization
- Before/after comparison visualization
- Optimization convergence plotting
- End-to-end CLI pipeline
- Unit test suite (18 tests)

### 🔶 Partially Implemented
- Room proportion constraints during expansion

### ✅ Recently Added
- Google Gemini LLM integration for intelligent requirement parsing
- Premium web-based UI with glassmorphic design
- Gemini API key read from `.env` (`GEMINI_API_KEY`) — no key input in the UI
- Interactive dashboard with tabbed result views

### 🔲 Future Extensions (not part of the current implementation scope)
- BIM generation — convert the layout to a building information model
- Building-code compliance — automated checking against regulations
- Cost estimation — material and construction cost prediction
- Environmental performance — daylight, ventilation and energy analysis

# Agentic AI Framework for Constraint-Aware Architectural Design

**50% Milestone — Working Prototype**

## Overview

Multi-agent pipeline that converts natural-language architectural briefs into
optimized 2D floor plans through:

```
Natural Language Input
        ↓
Requirement Agent (NL → structured JSON)
        ↓
Spatial Graph (rooms + relationships)
        ↓
Floor-Plan Generator (constraint-based procedural)
        ↓
Spatial Critic (deterministic scoring)
        ↓
Optimization Agent (greedy expansion + simulated annealing)
        ↓
Optimized Floor Plan + Visualizations
```

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
│   └── floor_plan_generator.py       # Constraint-based procedural generator
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
| Space Utilization | 0.10 | 60-85% plot coverage is optimal |

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
- LLM integration (abstraction ready, requires API key)
- Room proportion constraints during expansion

### 🔲 Future Work (Remaining 50%)
- BIM model generation (IFC export)
- Building code compliance checking
- Cost estimation module
- Daylight and ventilation analysis
- Energy performance simulation
- Multi-storey support
- HouseGAN++ integration for learned generation
- Web-based UI

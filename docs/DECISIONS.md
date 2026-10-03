# Architectural & Implementation Decisions

> Only decisions that can be verified from the existing codebase are documented here.

---

## Decision 1: Rule-Based Parser as Default Backend

- **Date**: 2026-10-01 (initial commit)
- **Decision**: Use a deterministic regex-based NL parser (`RuleBasedRequirementAgent`) as the default, with LLM as an optional upgrade.
- **Reason**: The system must run fully offline without requiring API keys. An academic project should be self-contained and reproducible.
- **Alternatives considered**: LLM-only parsing (rejected because it requires API key and internet).
- **Consequences**: The rule-based parser handles common patterns (room counts, plot dimensions, relationship phrases) but cannot understand complex or ambiguous briefs. The LLM backend was later added as an opt-in upgrade.

---

## Decision 2: Google Gemini as the LLM Provider (not OpenAI)

- **Date**: 2026-10-02
- **Decision**: Replace the original OpenAI-based `LLMRequirementAgent` with Google Gemini (`gemini-2.0-flash` via `google-generativeai` SDK).
- **Reason**: The project owner has a Gemini Pro subscription. The `google-generativeai` SDK supports structured JSON output via `response_mime_type="application/json"`, which is more reliable than parsing free-text.
- **Alternatives considered**: OpenAI GPT-4o-mini (was the original implementation, replaced because user prefers Gemini).
- **Consequences**: Requires `google-generativeai>=0.8.0` dependency. API key is read from the `GEMINI_API_KEY` env var (`.env`).

---

## Decision 3: Deterministic Spatial Critic (No LLM in Evaluation)

- **Date**: 2026-10-01 (initial commit)
- **Decision**: The spatial critic uses purely geometric/deterministic calculations — no LLM is used for evaluation.
- **Reason**: Evaluation must be reproducible, fast (called hundreds of times during SA), and not dependent on external APIs. Deterministic scoring enables meaningful optimization convergence.
- **Alternatives considered**: LLM-based evaluation (rejected due to latency, cost, and non-determinism in the SA loop).
- **Consequences**: The critic is limited to 8 predefined geometric dimensions. It cannot evaluate subjective qualities like aesthetics or feng shui.

---

## Decision 4: 8-Dimension Weighted Scoring System

- **Date**: 2026-10-01 (initial commit)
- **Decision**: Score floor plans on 8 dimensions with configurable weights summing to 1.0.
- **Reason**: Provides interpretable, decomposable scores. Each dimension addresses a specific architectural constraint. Weights allow tuning priorities.
- **Alternatives considered**: Single monolithic score (rejected — not interpretable); ML-based scoring (rejected — no training data).
- **Consequences**: The weights (`DEFAULT_WEIGHTS` in `spatial_critic.py`) directly affect which plans are selected and how optimization converges. Changing weights changes results.

---

## Decision 5: Procedural Strip-Packing Generator (not Learned)

- **Date**: 2026-10-01 (initial commit)
- **Decision**: Use a constraint-based procedural generator with strip-packing heuristic and spatial-relationship-aware scoring.
- **Reason**: This is the 50% milestone — a procedural approach is sufficient, implementable without training data, and produces diverse candidates through varied room ordering strategies (largest-first, entrance-first, graph-degree, random).
- **Alternatives considered**: HouseGAN++ (deferred to future work as it requires trained models and GPU).
- **Consequences**: Generated plans are rectangular-grid layouts. Quality depends on ordering heuristics. The generator interface (`generate_floor_plans()`) is modular enough to swap in a learned model later.

---

## Decision 6: Two-Phase Optimization (Greedy + SA)

- **Date**: 2026-10-01 (initial commit)
- **Decision**: Phase 1 greedily expands rooms to fill empty space; Phase 2 uses simulated annealing for spatial-relationship refinement.
- **Reason**: Initial procedural generation often leaves significant empty space. Greedy expansion quickly improves utilization. SA then fine-tunes adjacency/connectivity/separation relationships.
- **Alternatives considered**: SA-only (slower convergence on utilization), genetic algorithms (more complex, less interpretable).
- **Consequences**: Greedy expansion caps rooms at 3× preferred area to prevent unrealistic growth. SA uses 5 mutation operators with hand-tuned weights.

---

## Decision 7: Base64 Image Embedding in API Responses

- **Date**: 2026-10-01 (second commit)
- **Decision**: The `/api/pipeline` endpoint returns all images as base64-encoded PNG strings embedded in the JSON response, rather than saving to disk and returning URLs.
- **Reason**: Simplifies the frontend — no need for image hosting, caching, or cleanup. The single API call returns everything needed to render the complete UI.
- **Alternatives considered**: Save images to `output/` and return URLs (would require file management, cleanup, and concurrent request handling).
- **Consequences**: API responses are large (several MB due to multiple embedded images). Not suitable for bandwidth-constrained clients. The `_fig_to_base64()` helper in `app.py` closes matplotlib figures immediately after encoding.

---

## Decision 8: Dark Glassmorphic UI Design

- **Date**: 2026-10-01 (second commit)
- **Decision**: Use a premium dark-themed UI with glassmorphism, particle backgrounds, and animated transitions.
- **Reason**: User explicitly requested "a neat and clean UI design" with "high effort." The dark theme also makes the matplotlib-generated floor plan images (which have dark backgrounds in the web version) blend seamlessly.
- **Alternatives considered**: Light theme (would require different plot background colors in `app.py`).
- **Consequences**: The `app.py` route manually sets `facecolor="#0f1117"` on all matplotlib figures to match the dark UI. The CSS file is ~2500 lines. Changing to a light theme would require updating both CSS and the matplotlib color overrides in `app.py`.

---

## Decision 9: Vanilla HTML/CSS/JS Frontend (No Framework)

- **Date**: 2026-10-01 (second commit)
- **Decision**: Build the frontend as a single HTML page with vanilla CSS and JavaScript — no React, Vue, Tailwind, or build tools.
- **Reason**: Minimal complexity for an academic project. Flask serves the template directly via Jinja2. No build step needed.
- **Alternatives considered**: React/Vite (would add build complexity for a single-page UI).
- **Consequences**: All frontend state is in global JS variables. No component reuse system. The `style.css` file is large and monolithic. Adding complex interactive features (e.g., drag-and-drop room editing) would be harder without a framework.

---

## Decision 10: API Key Read from `.env` Only

- **Date**: 2026-10-03 (supersedes the 2026-10-02 browser-localStorage approach)
- **Decision**: The Gemini API key is read only on the server from `GEMINI_API_KEY` in `.env`. The UI has no key input and never sends a key.
- **Reason**: Keeps the key out of the browser and the request body, and removes a setup step from the UI.
- **Alternatives considered**: Browser `localStorage` + per-request key (previous approach — exposed the key in dev tools and in plaintext requests).
- **Consequences**: Changing the key requires editing `.env` and restarting the server. `.env` is gitignored.

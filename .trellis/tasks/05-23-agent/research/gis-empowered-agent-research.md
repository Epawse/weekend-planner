# GIS-Empowered Agent: Research & Product Analysis

## Critical Insight: Why Our Current Approach is Wrong

From TravelPlanner benchmark (ICML 2024, 1225 queries):
- **Pure LLM planning: 0.6% constraint satisfaction**
- LLM + ReAct: 4.4%
- **LLM + formal spatial solver: 97% feasibility**

This means: **spatial reasoning MUST be done by code/solvers, NOT by the LLM.** Our current approach lets DeepSeek "guess" venues and routes — it works because the model has training data about Beijing, but it's fundamentally unreliable and doesn't leverage GIS at all.

---

## Academic Research (2025-2026)

### 1. LLM-Geo (Penn State, github.com/gladcolor/LLM-Geo)
- Autonomous GIS agent: LLM generates a DAG (directed acyclic graph) of geoprocessing steps, then produces executable Python code (GeoPandas)
- Key pattern: **LLM plans the workflow, code executes the spatial analysis**
- 80% first-try success rate with GPT-4
- Lesson: The LLM's role is decomposing the task into spatial operations, not performing spatial reasoning itself

### 2. GeoAgentic-RAG (2026, arXiv 2605.10106)
- Hierarchical multi-agent: reasoning agent + insight generation agent
- Combines LLM language reasoning with spatial databases and tools
- Memory-augmented for real-time adaptation

### 3. "Agentic AI for Trip Planning Optimization" (2026, arXiv 2605.00276)
- **77.4% accuracy** vs 30.4% for single-agent baselines
- Architecture: Orchestration agent coordinating specialized POI agents, traffic agents, routing agents
- Key technique: **K-Means spatial clustering on lat/lon** to group POIs into walkable daily clusters
- Each POI agent predicts dwell time, wait time, cost

### 4. TravelPlanner Extensions (2025)
- **ChinaTravel**: Single-city multi-POI, compositional DSL for constraints, neuro-symbolic agents reach 37% satisfaction
- **Flex-TravelPlanner**: Dynamic re-prioritization mid-plan
- **TP-RAG**: Web-extracted tourist trajectories (geotagged POI sequences) injected as context — dramatically improves spatiotemporal coherence

### 5. Spatial Constraint Satisfaction (2025-2026)
- Model as CSP: variables (venue assignments), domains (options), constraints (walk time < 2h, no overlap)
- Solved by systematic search with propagation
- Geospatial walkability clustering: group venues by street-network distance (not Euclidean), filter by walkability index

---

## Products & Tools (2026)

### Mapbox MCP Server
- Exposes geocoding, directions, isochrones, matrix routing via MCP protocol
- AI agents call geospatial tools programmatically
- Supports chaining: geocode → isochrone → directions
- GitHub: mapbox/mcp-server

### OSMnx (Python)
- Download, model, analyze street networks from OpenStreetMap
- `network_type='walk'` for pedestrian graph
- Real walking distances via Dijkstra on street network (not straight-line)
- Distance matrix between multiple POIs
- Travel time estimation (4-5 km/h walking speed)

### Google Gemini Enterprise Agent Platform + CARTO
- Production-ready geospatial agents with live data (BigQuery)
- Handles spatial + temporal optimization at enterprise scale

---

## What a REAL GIS-Empowered Agent Looks Like

### The Paradigm Shift

```
WRONG (current):  User → LLM guesses venues → LLM guesses route → output
RIGHT (target):   User → Spatial Analysis Engine → Constrained Options → LLM selects + narrates
```

The LLM's role changes from "spatial reasoner" to "preference matcher + narrator":
- Spatial engine: handles geometry, distances, clustering, optimization (deterministic, correct)
- LLM: handles natural language understanding, preference inference, explanation generation (creative, flexible)

### Target Architecture

```
User Input
  ↓
[Intent Parser] (LLM) — extracts: who, when, how long, preferences
  ↓
[Spatial Analysis Engine] (Code — deterministic, no LLM)
  ├── Isochrone computation (ORS) → reachable polygon
  ├── POI search within polygon (高德 + GeoPandas sjoin)
  ├── Spatial clustering (K-Means/DBSCAN on coords) → "activity zones"
  ├── Intra-cluster walkability (OSMnx walking distance matrix)
  ├── TSP per cluster (optimal visit order)
  ├── Cross-cluster routing (高德 driving)
  └── Constraint validation (time budget, opening hours, travel feasibility)
  ↓
[Candidate Plans] — 2-3 spatially-valid, time-feasible plan options
  ↓
[Plan Selector + Narrator] (LLM) — picks best fit for scenario, generates natural language
  ↓
[Present to User] → approve → execute
```

### Key Differences from Current Implementation

| Aspect | Current | Target |
|--------|---------|--------|
| Venue selection | LLM picks from training data | Spatial engine filters real POIs within isochrone |
| Route feasibility | LLM guesses "10 min drive" | Actual driving/walking time from API |
| Activity grouping | LLM sequences arbitrarily | K-Means clusters nearby venues into walkable zones |
| Walking between activities | Not considered | OSMnx computes real pedestrian distance |
| Time budget validation | LLM estimates | Code sums: activity_duration + travel_time ≤ budget |
| Plan quality | Depends on model knowledge | Mathematically optimal within constraints |
| Reproducibility | Non-deterministic | Deterministic spatial analysis + LLM creativity |

### Spatial Analysis Engine — Core Operations

```python
class SpatialAnalysisEngine:
    """Deterministic spatial reasoning — no LLM involved."""
    
    def compute_reachable_area(self, home, minutes, mode) -> Polygon:
        """ORS isochrone → GeoJSON polygon"""
        
    def search_and_filter_pois(self, polygon, categories) -> GeoDataFrame:
        """高德 POI search → GeoPandas sjoin with isochrone → filtered results"""
        
    def cluster_venues(self, pois: GeoDataFrame, max_clusters=3) -> list[GeoDataFrame]:
        """K-Means/DBSCAN on coordinates → groups of walkable venues"""
        
    def compute_walking_matrix(self, cluster: GeoDataFrame) -> np.ndarray:
        """OSMnx or ORS matrix → pairwise walking times within cluster"""
        
    def optimize_visit_order(self, cluster: GeoDataFrame, matrix: np.ndarray) -> list:
        """TSP (brute-force for ≤6 points) → optimal sequence"""
        
    def validate_time_budget(self, plan, budget_hours) -> bool:
        """Sum all durations + travel times, check ≤ budget"""
        
    def generate_candidate_plans(self, clusters, constraints) -> list[dict]:
        """Combine: 1 play cluster + 1 eat venue + optional extra → 2-3 valid plans"""
```

### What Makes This "GIS-Empowered" vs "LLM + API Calls"

1. **Spatial filtering is a first-class operation** — not "search nearby" but "search within reachable polygon considering road network"
2. **Clustering reveals spatial structure** — "these 3 venues are all walkable from each other" is a spatial insight, not a text insight
3. **Constraint satisfaction is code, not prompting** — time budget, distance limits, opening hours are validated mathematically
4. **The LLM never sees infeasible options** — it only chooses between plans that are already spatially valid
5. **Route optimization is algorithmic** — TSP, not "the model thinks this order is good"

---

## Implementation Plan

### New module: `backend/app/services/spatial.py`

This is the core differentiator. A pure Python service (no LLM) that:
1. Takes user constraints (home location, time budget, mode of transport)
2. Computes isochrone
3. Searches and spatially filters POIs
4. Clusters into walkable zones
5. Optimizes visit order per zone
6. Validates time feasibility
7. Returns 2-3 candidate plans (structured data, not text)

### Modified graph flow

```
parse_intent (LLM) → spatial_analysis (CODE) → select_and_narrate (LLM) → present → execute
```

The `search_and_analyze` node becomes purely code-driven. The `generate_plan` node becomes "select from candidates and write natural language description."

### Dependencies to add
- `scikit-learn` — K-Means clustering
- `osmnx` — street network walking distances (optional, can use ORS matrix API instead)
- `numpy` — distance matrix operations

### Why This Wins the Hackathon

1. **Technically defensible** — evaluators can ask "how do you know the route is feasible?" and the answer is "we computed it, here's the polygon and the distance matrix"
2. **Visually impressive** — isochrone + clusters + optimized routes on the map
3. **Academically grounded** — references TravelPlanner, LLM-Geo, spatial CSP literature
4. **Practically superior** — plans are guaranteed feasible, not "the model thinks so"
5. **GIS expertise visible** — spatial clustering, network analysis, constraint validation are not things other teams will implement

# Spatial Engine Architecture: How It Should Exist in the Agent

## The Core Question

How should deterministic spatial computation relate to the LLM agent? The answer comes from studying how Claude Code, OpenCode, and Codex handle the split between probabilistic reasoning and deterministic execution.

---

## Lessons from Production Agents

### Claude Code (Anthropic)
- **Harness pre-processing** is the dominant pattern: before any model call, the harness assembles context, runs hooks, scopes tools
- **Programmatic tool calling** (2026): model writes Python code in a sandbox that calls multiple tools, processes results internally, returns only summarized output
- The harness is ~98% of the effective system; the agent loop is thin
- Key insight: **"The model is untrusted; the harness enforces correctness"**

### OpenCode (SST/Anomaly)
- **Deterministic computation = specialized MCP tools or built-in primitives** that run outside the LLM's probabilistic loop
- Skills encode dispatch logic: "run this deterministic recipe if no custom change needed; otherwise use LLM judgment"
- 80-90% of repeatable tasks run deterministically; LLM handles exceptions
- Key insight: **"Deterministic tools guarantee reproducibility; LLM focuses on creative judgment"**

### Codex (OpenAI)
- **Strict separation**: LLM reasoning (probabilistic, creative) vs deterministic tools (sandboxed, verifiable)
- "Separation prevents hallucinations from propagating into live code"
- The model reasons iteratively; tools provide verifiable, repeatable outcomes
- Key insight: **"The LLM decides WHAT to do; deterministic code does it correctly"**

### Anthropic Programmatic Tool Calling (2026)
- Model writes code inside a container that orchestrates multiple tools
- Intermediate results stay in the script; only final output hits the model's context
- Reduces latency, token usage, and round-trips
- Key insight: **"Batch deterministic operations, expose only the decision-relevant summary to the LLM"**

---

## Four Possible Architectures for Spatial Analysis

### Option 1: As Individual Tools (Current — Weak)

```
LLM → calls get_isochrone → gets polygon
LLM → calls search_venues → gets 21 POIs  
LLM → "reasons" about spatial relationships (BADLY)
LLM → outputs plan
```

**Problem**: The LLM is doing spatial reasoning it's not good at. It sees raw coordinates and "guesses" which venues are walkable from each other. TravelPlanner benchmark shows 0.6% success rate for this approach.

### Option 2: As Harness Pre-Processing (Recommended)

```
[Harness/Graph Node: Spatial Engine] — deterministic, no LLM
  ├── compute isochrone
  ├── search + spatial filter POIs
  ├── cluster into walkable zones
  ├── TSP optimize each zone
  ├── validate time budget
  └── output: 2-3 candidate plans (structured data)
       ↓
[LLM Node] — sees ONLY the candidates
  ├── selects best fit for scenario/preferences
  ├── generates natural language description
  └── adds personality/creativity to share text
```

**This is the Claude Code pattern**: the harness does heavy deterministic work BEFORE the model sees anything. The LLM never touches raw spatial data — it only makes preference decisions on pre-validated options.

**Why this is correct**:
- Spatial operations are deterministic → code does them perfectly
- Preference matching is probabilistic → LLM does this well
- The LLM can't hallucinate infeasible plans because it only sees feasible ones
- Matches the "model is untrusted; harness enforces correctness" principle

### Option 3: As a Skill/Workflow (OpenCode Pattern)

```
LLM decides: "I need to plan activities"
  → dispatches "spatial_planning" skill
  → skill runs deterministic pipeline
  → returns structured candidates
LLM continues with candidates
```

**Difference from Option 2**: The LLM decides WHEN to invoke spatial analysis. In Option 2, the graph structure determines it (always runs before planning).

**For our case**: Option 2 is better because spatial analysis ALWAYS runs — there's no decision about whether to do it.

### Option 4: As Programmatic Tool Calling (Anthropic Pattern)

```
LLM writes Python code:
  isochrone = get_isochrone(home, 30)
  pois = search_venues(isochrone)
  clusters = kmeans(pois, 3)
  routes = tsp(clusters)
  return format_candidates(routes)
```

**Problem**: Requires the LLM to write correct spatial analysis code every time. Unreliable. The code should be pre-written and deterministic.

---

## Recommended Architecture: Option 2 (Harness Pre-Processing)

### In LangGraph Terms

The spatial engine is a **graph node** — a pure Python function, no LLM involved:

```python
async def spatial_analysis_node(state: PlannerState) -> dict:
    """Deterministic spatial analysis — NO LLM, NO tool_calling.
    
    This is harness-level computation, not agent reasoning.
    Runs BEFORE the LLM planning node.
    """
    engine = SpatialAnalysisEngine()
    
    # All deterministic operations
    isochrone = await engine.compute_reachable_area(state["home_location"], 30)
    pois = await engine.search_and_filter(isochrone, state["scenario"])
    clusters = engine.cluster_venues(pois)
    optimized = engine.optimize_routes(clusters)
    candidates = engine.generate_candidate_plans(optimized, state["time_budget"])
    
    return {
        "candidate_plans": candidates,  # 2-3 spatially-valid plans
        "isochrone": isochrone,          # for map visualization
        "spatial_context": {             # summary for LLM
            "reachable_area_km2": ...,
            "total_venues_found": ...,
            "clusters_identified": ...,
        }
    }
```

### Modified Graph Topology

```
User Input → [parse_intent] (LLM) 
  → [spatial_analysis] (CODE — deterministic, no LLM)
  → [select_and_narrate] (LLM — picks from candidates, writes description)
  → [present_plan] (interrupt)
  → [execute_steps] (mock booking)
  → [share_card] (LLM — generates share text)
```

### What the LLM Sees (After Spatial Engine)

```
你有3个空间分析验证过的候选方案：

方案A: "公园+商场" 路线
- 活动簇: 望京体育公园(14:00-15:30) → 凯德MALL(步行8分钟) → 西贝(15:45-17:00)
- 总通勤: 23分钟 | 总时长: 3.5小时 | 步行占比: 65%
- 空间特征: 所有活动在500米半径内，全程步行可达

方案B: "游乐场+汤泉" 路线  
- 活动簇: 大望京公园游乐场(14:00-15:30) → 海德汤泉(驾车12分钟) → 含自助晚餐
- 总通勤: 12分钟 | 总时长: 4.5小时 | 驾车占比: 100%
- 空间特征: 两个独立点位，需驾车

方案C: "文化+美食" 路线
- 活动簇: 798艺术区(14:00-16:00) → 望京小腰(驾车15分钟) → 烤串晚餐
- 总通勤: 30分钟 | 总时长: 4小时 | 驾车占比: 100%  
- 空间特征: 跨区域，接近等时圈边界

请根据"家庭场景：孩子5岁，老婆减肥"选择最合适的方案并生成自然语言描述。
```

The LLM's job becomes trivial: pick A (walkable, kid-friendly, healthy options nearby) and write a nice description. It can't pick an infeasible plan because all options are pre-validated.

---

## Why This Matters for the Hackathon

| Dimension | Current (LLM does everything) | Target (Spatial Engine + LLM) |
|-----------|-------------------------------|-------------------------------|
| Correctness | Model might hallucinate distances | Distances are computed, verified |
| Reproducibility | Different output each run | Same spatial analysis, LLM only varies narration |
| Explainability | "The model thought this was close" | "500m walking distance, verified by street network" |
| Demo credibility | "Trust me" | "Here's the isochrone, here's the cluster, here's the TSP solution" |
| GIS expertise visible | Not at all | Clustering, network analysis, constraint validation |
| Academic grounding | None | References TravelPlanner, LLM-Geo, spatial CSP |

---

## What This Is NOT

This is NOT:
- A "tool" the LLM calls (that's Option 1, our current weak approach)
- An MCP server (overkill for a single-project internal service)
- A separate microservice (unnecessary complexity for hackathon)
- A "skill" loaded on demand (it always runs, not conditional)

This IS:
- A **graph node** in LangGraph — deterministic Python code
- **Harness-level pre-processing** — runs before LLM reasoning
- A **spatial constraint solver** — guarantees feasibility
- The **core differentiator** — what makes this a "GIS-empowered agent" vs "LLM + API calls"

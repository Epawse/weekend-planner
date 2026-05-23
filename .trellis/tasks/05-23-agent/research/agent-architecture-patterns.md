# Agent Architecture Patterns — Deep Research from learn-agent & learn-claude-code

## Source Projects

- **learn-agent**: Personal research on agent fundamentals (Transformer → Production), 10-week curriculum covering context engineering, multi-agent, production patterns
- **learn-claude-code**: Harness engineering analysis of Claude Code (the strongest coding agent), 20 progressive lessons dissecting every mechanism

---

## Core Philosophy: Harness Engineering

From learn-claude-code README — the foundational insight:

> "Agency — the capacity to perceive, reason, and act — comes from model training, not from external code orchestration. But a working agent product needs both the model and the harness. The model is the driver. The harness is the vehicle."

**What this means for our project**: We are NOT building intelligence. We are building the world that intelligence inhabits. The quality of that world (tools, context, permissions) directly determines how effectively the model can express itself.

```
Harness = Tools + Knowledge + Observation + Action Interfaces + Permissions

    Tools:          POI search, weather, routing, booking, delivery
    Knowledge:      user preferences, scenario constraints, city data
    Observation:    plan state, execution results, availability status
    Action:         mock API calls, reservation confirmations
    Permissions:    user confirmation before execution
```

**Anti-pattern to avoid**: Don't build a "Rube Goldberg machine" — over-engineered, brittle, procedural rule pipelines with an LLM wedged in as a text-completion node. Don't substitute hand-crafted decision trees for the model's own judgment.

---

## The Agent Loop (Never Changes)

From learn-claude-code s01-s20 — the loop itself is identical across all 20 lessons:

```python
def agent_loop(messages):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM,
            messages=messages, tools=TOOLS,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = TOOL_HANDLERS[block.name](**block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
        messages.append({"role": "user", "content": results})
```

**Key insight**: "The model decides when to call tools and when to stop. The code just executes what the model asks for." Every lesson layers one harness mechanism ON TOP of this loop — the loop itself never changes.

---

## Harness Mechanisms (from s20 Comprehensive Agent)

The complete harness has mechanisms at specific positions around the loop:

| Position | Mechanism | Purpose |
|----------|-----------|---------|
| Before LLM call | Cron/background notifications | Inject async results |
| Before LLM call | Compaction pipeline | Prevent context overflow |
| Before LLM call | System prompt assembly | Dynamic context based on state |
| LLM call wrapper | Error recovery | Retry, escalate, fallback |
| Before tool exec | PreToolUse hooks + permission | Safety boundaries |
| Tool dispatch | assemble_tool_pool | Built-in + MCP tools |
| After tool exec | PostToolUse hooks | Logging, alerts |
| Return to loop | tool_result | Feed results back |

**For our project**: We need a subset of these:
- System prompt assembly (scenario-aware)
- Error recovery (provider fallback)
- Tool dispatch (our 6 mock tools)
- Streaming events to frontend (replaces hooks)

---

## Context Engineering (2026 Paradigm Shift)

From learn-agent/05_context_mgmt — the #1 factor in agent reliability:

> "Most agent failures stem from poor context, not weak models. A model with perfect reasoning will still fail if its context is polluted with noise."

### Core Techniques

1. **Progressive Disclosure**: Don't dump everything upfront. Load details on demand.
   - For us: Don't load all venue data into context. Search → get summaries → load details only for selected venues.

2. **Dynamic Assembly**: System prompt sections composed at runtime based on state.
   - For us: Different prompt sections for family vs friends scenario, different constraints active.

3. **Isolation**: Separate contexts to prevent pollution.
   - For us: If we use subagents for parallel venue search, each gets clean context.

4. **Compression**: Snip old tool results, summarize old turns.
   - For us: After plan is generated, compress the search phase before entering execution phase.

### "Lost in the Middle" Problem
- LLMs attend poorly to information in the middle of long contexts
- Place critical info at start (system prompt) or end (recent turns)
- For us: Put scenario constraints in system prompt (start), put current plan step at end

---

## Error Recovery (Three Paths)

From learn-claude-code s11:

| Mode | Trigger | Recovery |
|------|---------|----------|
| Output truncated | `max_tokens` | Escalate 8K→64K, then continuation prompt |
| Context overflow | `prompt_too_long` | Reactive compact → retry |
| Transient failure | 429/529 | Exponential backoff + jitter, fallback model after 3× 529 |

**Exponential backoff formula**: `min(500 × 2^attempt, 32000) + random(0~25%)`

**For our project**: Multi-provider fallback is our primary error recovery. If Qwen fails → DeepSeek → OpenAI. This maps directly to the "consecutive 529 → switch to FALLBACK_MODEL" pattern.

---

## Planning Pattern (TodoWrite / Observable State)

From learn-agent/03_agent_loop/notes.md:

> "High-reasoning models handle tactical planning internally via thinking tokens. The harness's job shifts from forcing planning to providing observable checkpoints and resumable state. TodoWrite becomes a state reporting mechanism, not a cognitive crutch."

**For our project**: The plan output IS our TodoWrite equivalent. The user sees the plan, confirms it, then execution proceeds step by step. Each step's completion is observable.

---

## Multi-Agent Decision Framework

From learn-agent/06_multi_agent:

| Factor | Single Agent | Multi-Agent |
|--------|-------------|-------------|
| Latency | Lower | Higher (coordination) |
| Token cost | Lower | Higher (multiple contexts) |
| Reliability | Simpler failure modes | More failure points |
| Context quality | Risk of pollution on long tasks | Clean isolation |
| Parallelism | Sequential only | True parallel |

**Decision rule**: "If a single agent can do it cleanly without context overflow, don't add agents. The coordination tax must be less than the benefit."

**For our project**: A 4-6 hour activity plan with ~6 tool calls is well within single-agent capacity. Multi-agent would add complexity without benefit. **Use single agent.**

---

## Tool Design Principles

From learn-agent/02_api_tooluse:

- **Atomic**: one tool does one thing (search venues, not "search and book")
- **Composable**: tools can be combined by the model in sequence
- **Well-described**: description tells WHEN to use it, not just what it does
- **Bounded output**: truncate large results to prevent context explosion (max 5 results per search)

**Tool description quality directly affects tool selection accuracy.** Bad descriptions → wrong tool choices.

---

## Production Patterns

From learn-agent/07_production:

### SSE Streaming (FastAPI)
```python
@app.post("/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        agent_stream(request.message, session_id),
        media_type="text/event-stream",
    )
```

### Observability — Log every LLM call:
```json
{"event": "llm_call", "model": "qwen3.7-max", "input_tokens": 12450, "output_tokens": 834, "latency_ms": 2340}
```

### Cost Control
- Token budgets per session
- Model fallback (expensive for hard tasks, cheap for simple)
- Prompt caching (stable prefix → 90% savings on subsequent turns)

---

## AG-UI Protocol (Agent→Frontend Streaming)

From learn-agent/06_multi_agent/notes.md — 2026 open standard for real-time agent→frontend:

Event types: `TEXT_MESSAGE_CONTENT`, `TOOL_CALL_START/END`, `STATE_DELTA`, `RUN_STARTED/FINISHED`

**For our project**: Our SSE events should follow this pattern:
- `plan_generating` → `plan_ready` → `step_executing` → `step_complete` → `all_complete`

---

## System Prompt Assembly (Runtime, Not Hardcoded)

From learn-claude-code s10:

```python
def assemble_system_prompt(context: dict) -> str:
    sections = []
    sections.append(PROMPT_SECTIONS["identity"])  # always
    sections.append(PROMPT_SECTIONS["tools"])     # always
    
    # Conditional based on REAL STATE, not keyword matching
    if context.get("scenario") == "family":
        sections.append(FAMILY_CONSTRAINTS)
    if context.get("weather_checked"):
        sections.append(WEATHER_CONTEXT)
    
    return "\n\n".join(sections)
```

**Key design**: Section loading is based on real state (files exist, tools registered), not keyword matching in messages.

---

## Key Takeaways for Our Architecture

1. **Don't over-engineer orchestration** — let the model decide. Give it good tools and clear context.
2. **Single agent, single graph** — our task doesn't need multi-agent complexity.
3. **LangGraph adds value** for: observable state (plan confirmation), conditional edges (error → replan), streaming (node transitions → SSE events).
4. **Context engineering matters more than prompt tricks** — progressive disclosure of venue data, dynamic prompt assembly per scenario.
5. **Error recovery = provider fallback** — the primary failure mode is LLM provider issues, not tool failures.
6. **Tools must be atomic and well-described** — the model's tool selection accuracy depends on description quality.
7. **The plan IS the observable state** — user confirms before execution, each step is trackable.

# LangGraph Architecture for Activity Planning Agent

## Why LangGraph (not raw agent loop)

Based on learn-agent patterns, the raw agent loop is sufficient for simple tasks. But our use case has specific requirements that LangGraph handles better:

1. **Observable plan state**: User must see and confirm the plan before execution → LangGraph state is inspectable at any node
2. **Conditional branching**: Plan fails → replan; user rejects → modify → LangGraph conditional edges
3. **Checkpointing**: Long-running planning can be paused/resumed → LangGraph MemorySaver
4. **Streaming**: Each node transition can emit events to frontend → LangGraph streaming API

## Recommended Graph Topology: Plan-and-Execute with Replan

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
User Input → [Parse Intent] → [Generate Plan] → [Present to User]
                                     ↑                    │
                                     │              ┌─────┴─────┐
                                [Replan]      [Approve]    [Modify]
                                     ↑              │         │
                                     │              ▼         │
                                     │        [Execute Step]──┘
                                     │              │
                                     │         ┌────┴────┐
                                     │    [Success]  [Failure]
                                     │         │         │
                                     └─────────┘    [Handle Error]
                                                         │
                                                    [Fallback/Replan]
```

## State Schema (TypedDict)

```python
from typing import TypedDict, Literal
from langgraph.graph import MessagesState

class PlannerState(TypedDict):
    # Input
    user_input: str
    scenario: Literal["family", "friends"]
    constraints: dict  # parsed from user input + scenario defaults
    
    # Planning
    messages: list  # LLM conversation history
    plan: dict | None  # structured plan output
    plan_status: Literal["generating", "presented", "approved", "rejected", "executing", "completed"]
    
    # Execution
    current_step: int
    execution_results: list[dict]  # results of each booking/order
    
    # Error handling
    error: str | None
    retry_count: int
    fallback_options: list[dict]
```

## Node Definitions

| Node | Input State | Output State | LLM Call? |
|------|-------------|--------------|-----------|
| parse_intent | user_input | scenario, constraints | Yes |
| generate_plan | constraints, scenario | plan | Yes |
| present_plan | plan | plan_status="presented" | No (format only) |
| execute_step | plan, current_step | execution_results | Yes (tool selection) |
| handle_error | error | fallback_options OR replan trigger | Yes |
| replan | constraints, error, fallback_options | plan (revised) | Yes |

## Multi-Provider LLM Adapter

Based on learn-agent/07_production model fallback pattern:

```python
class LLMProvider:
    providers = [
        {"name": "qwen", "model": "qwen3.7-max", "priority": 1},
        {"name": "deepseek", "model": "deepseek-v4", "priority": 2},
        {"name": "openai", "model": "gpt-5.4", "priority": 3},
    ]
    
    async def invoke(self, messages, **kwargs):
        for provider in sorted(self.providers, key=lambda p: p["priority"]):
            try:
                return await self._call_provider(provider, messages, **kwargs)
            except ProviderError:
                continue
        raise AllProvidersFailedError()
```

## Tool Contracts (Mock API Interface)

Each tool follows the learn-agent pattern: atomic, composable, bounded output, returns structured result.

```python
@tool
def search_venues(
    query: str,
    category: Literal["restaurant", "attraction", "activity"],
    location: str,
    filters: dict | None = None
) -> dict:
    """Search for venues matching criteria. Returns top 5 results with details."""
    return {"status": "success", "data": [...], "total": int}

@tool
def check_availability(
    venue_id: str,
    date: str,
    time: str,
    party_size: int
) -> dict:
    """Check if venue has availability. Returns wait time and alternatives."""
    return {"status": "success", "available": bool, "wait_minutes": int, "alternatives": [...]}

@tool  
def get_weather(location: str, date: str) -> dict:
    """Get weather forecast. Used to filter outdoor vs indoor activities."""
    return {"status": "success", "condition": str, "temp_c": int, "outdoor_ok": bool}

@tool
def calculate_route(origin: str, destination: str, mode: str = "driving") -> dict:
    """Calculate travel time and distance between two points."""
    return {"status": "success", "duration_minutes": int, "distance_km": float}

@tool
def make_reservation(venue_id: str, date: str, time: str, party_size: int, name: str) -> dict:
    """Book a table/ticket. Returns confirmation number."""
    return {"status": "success", "confirmation": str, "details": dict}

@tool
def order_delivery(item_type: str, destination_venue: str, delivery_time: str, details: dict) -> dict:
    """Order flowers/cake/gift delivery to a venue."""
    return {"status": "success", "order_id": str, "eta": str}
```

## Streaming Strategy

Based on AG-UI protocol concepts from learn-agent/06_multi_agent/notes.md:

```python
# Event types emitted to frontend
EVENT_TYPES = {
    "plan_generating": "Agent is creating the plan",
    "plan_ready": "Plan complete, awaiting user confirmation",
    "step_executing": "Executing step N of plan",
    "step_complete": "Step N completed successfully",
    "step_failed": "Step N failed, triggering fallback",
    "all_complete": "All steps executed, plan complete",
}
```

Use SSE (Server-Sent Events) via FastAPI StreamingResponse — simpler than WebSocket for this unidirectional streaming use case.

## Key Design Decisions

1. **Plan-and-Execute over ReAct**: Matches the competition requirement of "show plan → confirm → execute"
2. **Single graph, not multi-agent**: Our task is sequential (plan → execute), context won't overflow for a 4-6 hour activity plan. Multi-agent adds complexity without benefit here.
3. **LangGraph conditional edges for error handling**: Rather than try/except in nodes, use graph routing to handle failures declaratively.
4. **Mock tools return realistic data**: Tools simulate real Meituan API responses with actual venue names, coordinates, and prices for a specific city.

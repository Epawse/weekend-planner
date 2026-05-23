# Error Handling

> Error patterns for LangGraph agent workflows.

---

## Overview

Agent systems fail differently from CRUD apps. Errors fall into two categories:

1. **Recoverable** (tool call failed, LLM returned bad format) — retry or fallback within the graph
2. **Fatal** (invalid state, config missing) — raise immediately, fail fast

---

## Error Types

```python
class ToolExecutionError(Exception):
    """A tool failed after all retries."""

class PlanningError(Exception):
    """LLM could not produce a valid plan."""

class ProviderUnavailableError(Exception):
    """All LLM providers failed."""

class InvalidStateError(Exception):
    """Agent state is corrupted or missing required fields."""
```

---

## Error Handling Patterns

### Tool Errors — Return structured error, don't raise

```python
@tool
def search_restaurants(query: str, location: str) -> dict:
    try:
        results = mock_api.search(query, location)
        return {"status": "success", "data": results}
    except ExternalAPIError as e:
        return {"status": "error", "message": str(e), "fallback": "suggest_alternatives"}
```

### Agent Node Errors — Route via graph state

```python
def planner_node(state: AgentState) -> AgentState:
    result = llm.invoke(state["messages"])
    if not validate_plan(result):
        return {**state, "error": "invalid_plan", "retry_count": state.get("retry_count", 0) + 1}
    return {**state, "plan": result, "error": None}
```

### Conditional routing on error

```python
def should_retry(state: AgentState) -> str:
    if state.get("error") and state.get("retry_count", 0) < 3:
        return "retry"
    if state.get("error"):
        return "fallback"
    return "continue"
```

---

## API Error Responses

FastAPI endpoints use standard HTTP status codes:

| Code | Meaning |
|------|---------|
| `400` | Invalid user input |
| `422` | Pydantic validation failure |
| `500` | Unexpected internal error |
| `503` | LLM provider unavailable |

---

## Common Mistakes

- Bare `except:` that silently swallows errors
- Letting tool exceptions propagate unhandled (breaks graph execution)
- Retrying infinitely — max 3 retries, then fallback or surface to user
- Not logging the error before returning a fallback response

# Directory Structure

> Python + LangGraph agent backend organization.

---

## Directory Layout

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI entrypoint
│   ├── config.py               # Settings, env vars, model configs
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # Top-level LangGraph graph definition
│   │   ├── planner.py          # Planning agent node
│   │   ├── searcher.py         # POI/data retrieval agent node
│   │   ├── optimizer.py        # Route & schedule optimization node
│   │   └── executor.py         # Booking/ordering execution node
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── poi_search.py       # Restaurant, attraction, activity search
│   │   ├── weather.py          # Weather API tool
│   │   ├── routing.py          # Distance & route calculation
│   │   ├── booking.py          # Reservation & ordering
│   │   ├── delivery.py         # Flower/cake delivery scheduling
│   │   └── availability.py     # Queue & seat availability check
│   ├── models/
│   │   ├── __init__.py
│   │   ├── state.py            # LangGraph state definitions (TypedDict)
│   │   ├── schemas.py          # Pydantic request/response schemas
│   │   └── domain.py           # Domain entities (Plan, Activity, Venue)
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── provider.py         # Multi-provider LLM factory
│   │   ├── prompts.py          # Prompt templates
│   │   └── callbacks.py        # Streaming & token tracking callbacks
│   ├── services/
│   │   ├── __init__.py
│   │   ├── preference.py       # User preference parsing & constraint solving
│   │   └── sharing.py          # Plan card generation & sharing
│   └── api/
│       ├── __init__.py
│       ├── routes.py           # API endpoints
│       └── websocket.py        # Real-time streaming endpoint
├── tests/
│   ├── __init__.py
│   ├── test_agents/
│   ├── test_tools/
│   └── test_api/
├── pyproject.toml
└── .env.example
```

---

## Module Organization

- `agents/`: LangGraph nodes and graph definitions. Each file = one agent node.
- `tools/`: LangGraph tool functions decorated with `@tool`. Each file = one domain of tools.
- `models/`: State schemas (TypedDict for LangGraph), Pydantic models for API, domain entities.
- `llm/`: LLM provider abstraction. All model-specific logic lives here.
- `services/`: Business logic that doesn't fit agents or tools.
- `api/`: FastAPI routes and WebSocket handlers.

---

## Naming Conventions

- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- LangGraph state keys: `snake_case` strings
- Tool functions: verb_noun pattern (e.g., `search_restaurants`, `check_availability`)

---

## Key Patterns

- One graph definition per `orchestrator.py`, composed from node functions in other agent files.
- Tools are pure functions with `@tool` decorator, no class inheritance.
- State flows through LangGraph's `TypedDict`; never use global mutable state.
- All external API calls go through tools, never directly in agent nodes.

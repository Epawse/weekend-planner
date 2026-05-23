# Quality Guidelines

> Python code standards for this project.

---

## Overview

Python 3.11+. All code must pass type checking and linting before commit.

---

## Required Patterns

- All functions must have type annotations (modern `list[str]` syntax, not `List[str]`)
- Pydantic models for all API request/response schemas
- `TypedDict` for LangGraph state definitions
- Environment variables via a central `config.py`, never hardcoded

---

## Forbidden Patterns

- `print()` for debugging — use structlog
- `Any` type unless interfacing with untyped external libraries
- Circular imports between agent modules
- Business logic in API route handlers — delegate to agents/services
- Hardcoded API keys or model names — use config
- Global mutable state — all state flows through LangGraph's TypedDict
- `from module import *`

---

## Code Style

- Formatter: `ruff format`
- Linter: `ruff check`
- Line length: 120
- Import sorting: isort-compatible (handled by ruff)

---

## Testing Requirements

- Framework: `pytest`
- Test tool functions with mock data inputs
- Test agent nodes with fixture states
- Test graph end-to-end with a simple scenario
- Focus on critical paths (planning logic, error routing), not 100% coverage

---

## Dependencies

Pin exact versions in `pyproject.toml`. Core stack:

- `langgraph`, `langchain-core` — agent orchestration
- `fastapi`, `uvicorn` — API server
- `pydantic` — data validation
- `langchain-openai`, `langchain-anthropic`, `dashscope` — multi-provider LLM
- `structlog` — logging
- `pytest`, `ruff` — dev tools

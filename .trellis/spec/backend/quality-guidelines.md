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
- Line length: 120 — **ruff measures display width, so CJK/full-width chars count as 2.**
  A Chinese line ≤120 code points can still trip `E501`. For long prompt strings,
  wrap content-preservingly: adjacent string literals, or a `\` line-continuation
  inside triple-quoted strings (removes the newline, keeps the string identical).
- Import sorting: isort-compatible (handled by ruff)

## Running Checks

Dev tools (`pytest`, `pytest-asyncio`, `ruff`) live in the `dev` optional-dependency
group, not in the base venv. The `.venv/bin` dir has **no `pytest`/`ruff` on PATH**.

- Install dev tools once: `uv sync --extra dev`
- Run tests: `.venv/bin/python -m pytest -q` (asyncio_mode=auto; plain `async def test_*` works)
- Lint/format: `ruff check app tests` / `ruff format --check app tests` (ruff resolves config from `pyproject.toml`)

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

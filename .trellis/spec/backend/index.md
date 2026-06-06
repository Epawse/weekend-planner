# Backend Development Guidelines

> Best practices for backend development in this project.

---

## Overview

This directory contains guidelines for backend development. Fill in each file with your project's specific conventions.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Python + LangGraph agent backend layout | Done |
| [Database Guidelines](./database-guidelines.md) | In-memory + JSON mock data, LangGraph checkpointer | Done |
| [Error Handling](./error-handling.md) | Agent error patterns, graph routing, retries | Done |
| [LLM Provider](./llm-provider.md) | Provider selection/fallback, env wiring, `DEFAULT_LLM_PROVIDER` gotcha | Done |
| [Quality Guidelines](./quality-guidelines.md) | Python 3.11+, ruff, pytest, type hints | Done |
| [Logging Guidelines](./logging-guidelines.md) | structlog, agent execution tracing | Done |
| [Plan Canvas Contract](./plan-canvas-contract.md) | Cross-layer `plan_canvas` API/state contract | Done |
| [Collaborative Room Contract](./collaborative-room-contract.md) | Mock multiplayer room shell around PlanCanvasState | Done |

---

## How to Fill These Guidelines

For each guideline file:

1. Document your project's **actual conventions** (not ideals)
2. Include **code examples** from your codebase
3. List **forbidden patterns** and why
4. Add **common mistakes** your team has made

The goal is to help AI assistants and new team members understand how YOUR project works.

---

**Language**: All documentation should be written in **English**.

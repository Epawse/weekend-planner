# Logging Guidelines

> Structured logging for agent execution tracing.

---

## Overview

Use Python's `logging` module with `structlog` for structured JSON output.

```python
import structlog
logger = structlog.get_logger()
```

---

## Log Levels

| Level | Use For |
|-------|---------|
| `DEBUG` | Tool call inputs/outputs, LLM prompt details, state transitions |
| `INFO` | Agent node entry/exit, plan generation complete, user request received |
| `WARNING` | Tool retry, fallback triggered, slow LLM response (>5s) |
| `ERROR` | Tool failure after retries, LLM provider down, invalid state |

---

## Structured Logging

```python
logger.info("tool_executed", tool="search_restaurants", query="family restaurant", results_count=5, latency_ms=120)
logger.warning("tool_retry", tool="check_availability", attempt=2, reason="timeout")
logger.error("provider_failed", provider="qwen", model="qwen3.7-max", error="rate_limit")
```

---

## What to Log

- Every agent node entry: node name, relevant state keys
- Every tool call: tool name, input params, execution time, success/failure
- LLM calls: provider, model, token count, latency
- User-facing decisions: which plan was selected, why alternatives were rejected
- State transitions in the LangGraph graph

---

## What NOT to Log

- Full LLM prompts in production (use DEBUG level only)
- User PII beyond what's needed for debugging
- API keys or credentials (even partially)
- Mock data contents (static, no value in logging)

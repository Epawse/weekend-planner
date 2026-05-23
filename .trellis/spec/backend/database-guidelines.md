# Database Guidelines

> Lightweight persistence for hackathon scope.

---

## Overview

This project uses in-memory state + optional JSON file persistence. No traditional database or ORM.

---

## Data Storage Strategy

| Data Type | Storage | Rationale |
|-----------|---------|-----------|
| Agent state (mid-execution) | LangGraph checkpointer (`MemorySaver`) | Built-in persistence for graph state |
| User preferences | In-memory dict / JSON file | Hackathon scope, no user auth |
| Mock POI data | Static JSON fixtures in `backend/data/` | Simulates Meituan API responses |
| Generated plans | LangGraph state output | Returned via API, not persisted long-term |

---

## Mock Data Organization

```
backend/data/
├── restaurants.json        # Mock restaurant catalog
├── attractions.json        # Parks, museums, play areas
├── activities.json         # Shows, exhibitions, events
└── user_profiles.json      # Sample user preference profiles
```

---

## Naming Conventions

- Mock data files: `snake_case.json`
- JSON keys: `snake_case`
- IDs: string UUIDs or short slugs (e.g., `"rest_001"`)

---

## Common Mistakes

- Over-engineering persistence for a hackathon demo — keep it simple
- Forgetting to make mock data realistic (use real venue names, plausible prices, actual coordinates)
- Using SQLite/Postgres when LangGraph's MemorySaver is sufficient for demo scope

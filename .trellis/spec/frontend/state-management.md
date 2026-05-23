# State Management

> How state is managed in this project.

---

## Overview

Minimal state management. Most state lives in the backend agent; the frontend is primarily a thin UI layer that streams and displays agent output.

---

## State Categories

| Category | Solution | Examples |
|----------|----------|----------|
| Server state | Fetch + useState | Plan data, venue details |
| Streaming state | Custom useChat hook | Message stream, agent status |
| UI state | Local useState | Input value, modal open, tab selection |
| URL state | Next.js router / params | Plan ID, share links |

---

## When to Use Global State

Almost never in this project. The chat conversation is the only cross-component state, and it lives in the `useChat` hook passed via props or a single context.

If needed: React Context at the `app/layout.tsx` level. No Redux, no Zustand, no Jotai.

---

## Server State

- Backend is the source of truth for plans, venues, and agent state
- Frontend fetches on demand, does not cache aggressively
- Streaming responses update state incrementally via the chat hook

---

## Common Mistakes

- Creating global state for data that only one component needs
- Duplicating server state in client state (fetch it fresh instead)
- Using context for frequently-changing values (causes re-render cascades)
- Over-engineering state management for a demo-scope project

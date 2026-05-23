# Type Safety

> TypeScript conventions for this project.

---

## Overview

Strict TypeScript. All types must be explicit at module boundaries; inference is fine within function bodies.

---

## Type Organization

- Shared types (API responses, domain entities): `lib/types.ts`
- Component props: co-located above the component in the same file
- API request/response types: `lib/types.ts`, mirroring backend Pydantic schemas

```tsx
// lib/types.ts
export interface Plan {
  id: string;
  activities: Activity[];
  totalDuration: number;
  scenario: "family" | "friends";
}

export interface Activity {
  id: string;
  venue: Venue;
  startTime: string;
  duration: number;
  type: "dining" | "entertainment" | "shopping" | "outdoor";
}
```

---

## Validation

- Zod for runtime validation of API responses (optional, only if backend responses are unreliable)
- TypeScript compiler for compile-time safety
- No runtime type checking for internal data flow

---

## Common Patterns

- Discriminated unions for message types:
```tsx
type ChatMessage =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; plan?: Plan }
  | { role: "system"; status: "thinking" | "executing" | "done" };
```

- Utility types where appropriate: `Pick`, `Omit`, `Partial`

---

## Forbidden Patterns

- `any` — use `unknown` and narrow instead
- Type assertions (`as`) — only at API boundaries with validation
- `// @ts-ignore` or `// @ts-expect-error` without a linked issue
- Enum — use union types or `as const` objects instead

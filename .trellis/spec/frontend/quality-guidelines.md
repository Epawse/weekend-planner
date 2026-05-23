# Quality Guidelines

> Frontend code quality standards.

---

## Required Patterns

- Strict TypeScript (`strict: true` in tsconfig)
- All components must be accessible (semantic HTML, ARIA where needed)
- Error boundaries around async content
- Loading states for all data-dependent UI

---

## Forbidden Patterns

- `any` type
- `console.log` in committed code (use a logger or remove)
- Inline styles
- Direct DOM manipulation (`document.querySelector`, etc.)
- `dangerouslySetInnerHTML` without sanitization
- Importing from `node_modules` internals (non-public APIs)

---

## Code Style

- ESLint + Prettier (via Next.js defaults)
- Import order: React → Next.js → external libs → internal (`@/`)
- No barrel files (`index.ts` re-exports) — import directly from source

---

## Testing Requirements

- For hackathon scope: manual testing is primary
- Type checking (`tsc --noEmit`) must pass
- Lint must pass (`next lint`)
- If time permits: Playwright for the critical chat → plan flow

---

## Code Review Checklist

- Types are explicit at boundaries
- No `any` or type assertions without justification
- Accessible (keyboard nav, screen reader basics)
- Loading and error states handled
- No hardcoded strings that should be in config

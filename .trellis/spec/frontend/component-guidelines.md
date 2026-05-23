# Component Guidelines

> React component patterns for this project.

---

## Component Structure

```tsx
interface VenueCardProps {
  venue: Venue;
  onBook: (venueId: string) => void;
  isLoading?: boolean;
}

export function VenueCard({ venue, onBook, isLoading = false }: VenueCardProps) {
  // hooks first
  // derived state
  // handlers
  // render
}
```

- Function components only (no class components)
- Named exports (no default exports)
- Props interface defined above the component, named `{ComponentName}Props`
- Destructure props in the function signature

---

## Props Conventions

- Required props first, optional props after
- Boolean props default to `false`
- Event handlers prefixed with `on` (e.g., `onBook`, `onDismiss`)
- Children prop only when composition is the primary use case
- No prop spreading (`{...props}`) except for UI primitives

---

## Styling Patterns

- Tailwind CSS for all styling
- `cn()` utility (from `lib/utils.ts`) for conditional classes
- No inline styles, no CSS modules, no styled-components
- Shadcn/ui as the component primitive library

```tsx
import { cn } from "@/lib/utils";

<div className={cn("rounded-lg p-4", isActive && "border-primary bg-primary/5")} />
```

---

## Accessibility

- All interactive elements must be keyboard accessible
- Images require `alt` text
- Use semantic HTML (`button` not `div onClick`)
- ARIA labels on icon-only buttons
- Color contrast must meet WCAG AA

---

## Common Mistakes

- Putting fetch logic directly in components instead of hooks
- Using `useEffect` for derived state (compute it inline instead)
- Creating wrapper components that just pass props through
- Mixing layout concerns with business logic in the same component

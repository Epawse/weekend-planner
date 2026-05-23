# Directory Structure

> Next.js App Router frontend for the activity planning agent.

---

## Directory Layout

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout (providers, fonts, metadata)
│   ├── page.tsx                # Landing / chat entry page
│   ├── plan/
│   │   └── [id]/
│   │       └── page.tsx        # Generated plan view (shareable)
│   └── api/
│       └── chat/
│           └── route.ts        # BFF proxy to backend agent API
├── components/
│   ├── chat/
│   │   ├── ChatInput.tsx       # User message input with suggestions
│   │   ├── ChatMessage.tsx     # Single message bubble
│   │   ├── ChatStream.tsx      # Streaming response display
│   │   └── ScenarioSelector.tsx # Family vs Friends scenario picker
│   ├── plan/
│   │   ├── PlanCard.tsx        # Complete plan overview card
│   │   ├── TimelineView.tsx    # Visual timeline of activities
│   │   ├── VenueCard.tsx       # Restaurant/attraction card
│   │   └── ActionButton.tsx    # One-click booking/order button
│   ├── shared/
│   │   ├── LoadingSpinner.tsx
│   │   ├── ErrorBoundary.tsx
│   │   └── ShareButton.tsx     # Generate shareable plan link
│   └── ui/                     # Shadcn/ui primitives (auto-generated)
├── hooks/
│   ├── useChat.ts              # Chat state + streaming
│   ├── usePlan.ts              # Plan data fetching
│   └── useWebSocket.ts         # Real-time agent updates
├── lib/
│   ├── api.ts                  # Backend API client
│   ├── types.ts                # Shared TypeScript types
│   └── utils.ts                # Utility functions (cn, formatTime, etc.)
├── public/
│   └── icons/                  # Activity category icons
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

---

## Module Organization

- `app/`: Next.js App Router pages and API routes only. No business logic.
- `components/`: Grouped by feature domain (`chat/`, `plan/`), shared primitives in `shared/` and `ui/`.
- `hooks/`: One hook per file. Named by domain concern, not by implementation.
- `lib/`: Pure utilities, API client, type definitions. No React imports.

---

## Naming Conventions

- Files: `PascalCase.tsx` for components, `camelCase.ts` for non-component modules
- Directories: `kebab-case` or `camelCase` (follow Next.js conventions for `app/`)
- Components: Named export matching filename (`export function ChatInput`)
- Types: `PascalCase`, suffixed with purpose (`PlanResponse`, `VenueCardProps`)

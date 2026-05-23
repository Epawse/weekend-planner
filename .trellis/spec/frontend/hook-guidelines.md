# Hook Guidelines

> Custom hook patterns for this project.

---

## Custom Hook Patterns

- One hook per file in `hooks/`
- Each hook encapsulates one concern (data fetching, state machine, subscription)
- Return object with named properties, not arrays (except for simple toggle/value pairs)

```tsx
export function useChat() {
  // ...
  return { messages, sendMessage, isStreaming, error };
}
```

---

## Data Fetching

- Use `fetch` + React state for simple cases (hackathon scope)
- For streaming responses: custom `useChat` hook with `EventSource` or `fetch` + `ReadableStream`
- No SWR or React Query unless caching becomes necessary

```tsx
export function usePlan(planId: string) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/plan/${planId}`)
      .then(res => res.json())
      .then(setPlan)
      .finally(() => setIsLoading(false));
  }, [planId]);

  return { plan, isLoading };
}
```

---

## Naming Conventions

- Always prefix with `use`
- Name by domain concern: `useChat`, `usePlan`, `useWebSocket`
- Not by implementation: avoid `useFetchData`, `useStateManager`

---

## Common Mistakes

- Putting UI rendering logic inside hooks (hooks return data, not JSX)
- Creating hooks that are only used in one place and add no abstraction value
- Missing dependency array entries in `useEffect`
- Using `useEffect` to sync state that could be computed inline

# Frontend SSE & Next.js Integration Research

## Next.js App Router — SSE Consumption (2026 Best Practice)

### Architecture

```
Backend (FastAPI)                    Frontend (Next.js)
─────────────────                    ──────────────────
POST /plan/create                    
  → LangGraph astream               BFF Route Handler (optional)
  → yield SSE events          →     app/api/plan/route.ts
                                       → proxy to backend
                                    
                                    Client Component
                                       → useSSE hook (EventSource)
                                       → render streaming updates
```

**Decision**: Skip the BFF proxy. Frontend connects directly to FastAPI backend via EventSource. Simpler for hackathon scope.

### Custom useSSE Hook (Production-Ready)

```tsx
'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

interface UseSSEOptions<T> {
  onMessage?: (data: T) => void;
  onError?: (error: Event) => void;
  reconnectInterval?: number;
}

export function useSSE<T = any>(
  url: string | null,  // null = don't connect yet
  options: UseSSEOptions<T> = {}
) {
  const [data, setData] = useState<T | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Event | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (!url) return;
    if (eventSourceRef.current) eventSourceRef.current.close();

    eventSourceRef.current = new EventSource(url);

    eventSourceRef.current.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    eventSourceRef.current.onmessage = (event) => {
      try {
        const parsedData: T = JSON.parse(event.data);
        setData(parsedData);
        options.onMessage?.(parsedData);
      } catch (e) {
        console.error('SSE parse error', e);
      }
    };

    eventSourceRef.current.onerror = (err) => {
      setIsConnected(false);
      setError(err);
      options.onError?.(err);
      eventSourceRef.current?.close();
      reconnectTimeoutRef.current = setTimeout(connect, options.reconnectInterval ?? 5000);
    };
  }, [url, options]);

  useEffect(() => {
    connect();
    return () => {
      eventSourceRef.current?.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  const disconnect = useCallback(() => {
    eventSourceRef.current?.close();
    setIsConnected(false);
  }, []);

  return { data, isConnected, error, reconnect: connect, disconnect };
}
```

### Named Events (For Different Event Types)

```tsx
// Listen to specific event types from SSE
export function usePlanStream(sessionId: string | null) {
  const [messages, setMessages] = useState<PlanEvent[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [status, setStatus] = useState<'idle' | 'planning' | 'ready' | 'executing' | 'done'>('idle');
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    
    const es = new EventSource(`${API_BASE}/plan/stream?session_id=${sessionId}`);
    eventSourceRef.current = es;

    // Named event listeners
    es.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data);
      setMessages(prev => [...prev, data]);
      setStatus('planning');
    });

    es.addEventListener('plan_ready', (e) => {
      const data = JSON.parse(e.data);
      setPlan(data.plan);
      setStatus('ready');
    });

    es.addEventListener('step_executing', (e) => {
      const data = JSON.parse(e.data);
      setMessages(prev => [...prev, data]);
      setStatus('executing');
    });

    es.addEventListener('done', (e) => {
      setStatus('done');
      es.close();
    });

    es.onerror = () => {
      es.close();
    };

    return () => es.close();
  }, [sessionId]);

  return { messages, plan, status };
}
```

### POST-based SSE (For sending user input)

EventSource only supports GET. For POST (sending user message), use fetch with ReadableStream:

```tsx
export async function* streamPlanCreation(
  message: string,
  scenario: 'family' | 'friends'
): AsyncGenerator<PlanEvent> {
  const response = await fetch(`${API_BASE}/plan/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, scenario }),
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  if (!response.body) throw new Error('No response body');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        yield data;
      }
    }
  }
}

// Usage in component
function ChatComponent() {
  const [events, setEvents] = useState<PlanEvent[]>([]);
  
  async function handleSubmit(message: string) {
    for await (const event of streamPlanCreation(message, 'family')) {
      setEvents(prev => [...prev, event]);
    }
  }
}
```

---

## SSE Event Protocol (Backend → Frontend)

### Event Types

```typescript
type PlanEventType =
  | 'thinking'        // Agent is reasoning
  | 'tool_calling'    // Agent is calling a tool
  | 'tool_result'     // Tool returned result
  | 'plan_generated'  // Complete plan ready for review
  | 'plan_approved'   // User approved, starting execution
  | 'step_start'      // Executing step N
  | 'step_complete'   // Step N completed
  | 'step_failed'     // Step N failed, showing fallback
  | 'all_complete'    // All steps done
  | 'error'           // Unrecoverable error

interface PlanEvent {
  type: PlanEventType;
  timestamp: string;
  data: Record<string, unknown>;
}
```

### Example Event Sequence

```
event: thinking
data: {"type": "thinking", "data": {"message": "分析您的需求..."}}

event: tool_calling
data: {"type": "tool_calling", "data": {"tool": "search_venues", "args": {"query": "亲子乐园", "location": "朝阳区"}}}

event: tool_result
data: {"type": "tool_result", "data": {"tool": "search_venues", "results_count": 5}}

event: plan_generated
data: {"type": "plan_generated", "data": {"plan": {...complete plan object...}}}

// --- User approves via POST /plan/approve ---

event: step_start
data: {"type": "step_start", "data": {"step": 1, "action": "预订蓝色港湾亲子乐园门票", "venue": "蓝色港湾"}}

event: step_complete
data: {"type": "step_complete", "data": {"step": 1, "confirmation": "BK-20260523-001"}}

event: all_complete
data: {"type": "all_complete", "data": {"summary": "所有预订已完成", "share_card": {...}}}
```

---

## Key Frontend Components

### Chat + Plan Flow

```
┌─────────────────────────────────────┐
│  ChatInput (scenario selector)       │
├─────────────────────────────────────┤
│  Message Stream                      │
│  ┌─────────────────────────────┐    │
│  │ User: 今天下午想带老婆孩子出去玩  │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ Agent: [thinking animation]  │    │
│  │ 正在搜索适合的活动...         │    │
│  └─────────────────────────────┘    │
├─────────────────────────────────────┤
│  PlanCard (when plan_generated)      │
│  ┌─────────────────────────────┐    │
│  │ 14:00 蓝色港湾亲子乐园       │    │
│  │ 16:30 绿茶餐厅(低卡套餐)     │    │
│  │ 18:00 朝阳公园散步           │    │
│  │                              │    │
│  │ [确认方案] [修改]            │    │
│  └─────────────────────────────┘    │
├─────────────────────────────────────┤
│  ExecutionProgress (after approve)   │
│  ┌─────────────────────────────┐    │
│  │ ✓ 门票已预订 BK-001         │    │
│  │ ◎ 正在预订餐厅...           │    │
│  │ ○ 待执行: 公园无需预约       │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

---

## Production Tips

- `X-Accel-Buffering: no` header prevents Nginx/proxy buffering
- `Cache-Control: no-cache, no-transform` prevents CDN caching
- Handle client disconnect via `request.signal.addEventListener('abort', ...)`
- For POST-based streaming, use fetch + ReadableStream (not EventSource)
- Auto-reconnect with exponential backoff on connection loss

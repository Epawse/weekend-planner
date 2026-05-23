# Technical Implementation Research — LangGraph + FastAPI + Multi-Provider LLM

## 1. LangGraph v1.2.1 — Core Patterns

### StateGraph with TypedDict

```python
from langgraph.graph import START, END, StateGraph
from typing_extensions import TypedDict

class State(TypedDict):
    text: str

def node_a(state: State) -> dict:
    return {"text": state["text"] + "a"}

graph = StateGraph(State)
graph.add_node("node_a", node_a)
graph.add_edge(START, "node_a")
graph.add_edge("node_a", END)
app = graph.compile()
print(app.invoke({"text": ""}))
```

### Conditional Edges (Routing)

```python
workflow.add_conditional_edges(
    "grade_documents",
    decide_to_generate,  # function that returns a string key
    {
        "web_search": "web_search",
        "generate": "generate",
    },
)
```

### Tool-Calling Agent Pattern (Our Primary Pattern)

```python
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain.tools import tool
from typing import Literal

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

# LLM node
def llm_call(state: MessagesState):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

# Routing function
def should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_node"
    return END

# Build graph
builder = StateGraph(MessagesState)
builder.add_node("llm_call", llm_call)
builder.add_node("tool_node", ToolNode([search]))
builder.add_edge(START, "llm_call")
builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
builder.add_edge("tool_node", "llm_call")
agent = builder.compile()
```

### Human-in-the-Loop (Interrupt for Plan Approval)

This is CRITICAL for our "show plan → user confirms → execute" flow.

```python
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from typing import Literal, Optional, TypedDict

class ApprovalState(TypedDict):
    action_details: str
    status: Optional[Literal["pending", "approved", "rejected"]]

def approval_node(state: ApprovalState) -> Command[Literal["proceed", "cancel"]]:
    # Pause execution — payload surfaces in result["__interrupt__"]
    decision = interrupt({
        "question": "Approve this action?",
        "details": state["action_details"],
    })
    return Command(goto="proceed" if decision else "cancel")

def proceed_node(state): return {"status": "approved"}
def cancel_node(state): return {"status": "rejected"}

builder = StateGraph(ApprovalState)
builder.add_node("approval", approval_node)
builder.add_node("proceed", proceed_node)
builder.add_node("cancel", cancel_node)
builder.add_edge(START, "approval")
builder.add_edge("proceed", END)
builder.add_edge("cancel", END)

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# First invoke — pauses at interrupt
config = {"configurable": {"thread_id": "plan-123"}}
result = graph.invoke({"action_details": "Book restaurant + park", "status": "pending"}, config)
print(result["__interrupt__"])  # Shows plan details to user

# Resume with approval
from langgraph.types import Command
final = graph.invoke(Command(resume=True), config)  # or Command(resume=False) to reject
```

### Streaming with Custom Events (get_stream_writer)

```python
from langgraph.config import get_stream_writer
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    topic: str
    joke: str

def generate_joke(state: State):
    writer = get_stream_writer()
    writer({"status": "thinking of a joke..."})  # Custom event emitted to stream
    return {"joke": f"Why did the {state['topic']} go to school?"}

graph = (
    StateGraph(State)
    .add_node(generate_joke)
    .add_edge(START, "generate_joke")
    .add_edge("generate_joke", END)
    .compile()
)

# Consume stream
for chunk in graph.stream(
    {"topic": "ice cream"},
    stream_mode=["updates", "custom"],
    version="v2",
):
    if chunk["type"] == "updates":
        for node_name, state in chunk["data"].items():
            print(f"Node {node_name} updated: {state}")
    elif chunk["type"] == "custom":
        print(f"Status: {chunk['data']['status']}")
```

### Streaming from Tools

```python
from langchain.tools import tool
from langgraph.config import get_stream_writer

@tool
def search_restaurants(query: str, location: str) -> str:
    """Search for restaurants matching criteria."""
    writer = get_stream_writer()
    writer({"type": "progress", "data": "Searching restaurants..."})
    # ... do search ...
    writer({"type": "progress", "data": f"Found 5 restaurants for '{query}'"})
    return json.dumps(results)
```

---

## 2. FastAPI SSE — Server-Sent Events (2026 Latest)

### Native EventSourceResponse (FastAPI 0.115+)

```python
from collections.abc import AsyncIterable
from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

app = FastAPI()

class PlanEvent(BaseModel):
    type: str  # "plan_generating", "plan_ready", "step_executing", etc.
    data: dict

@app.get("/plan/stream", response_class=EventSourceResponse)
async def stream_plan() -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(comment="plan execution stream")
    # Each event has type, data, id
    yield ServerSentEvent(
        data=PlanEvent(type="plan_generating", data={"step": "searching venues"}),
        event="plan_update",
        id="1",
        retry=5000
    )
```

### StreamingResponse (Alternative, more control)

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

async def plan_stream_generator(user_input: str):
    # Run LangGraph and yield SSE events
    async for chunk in graph.astream(
        {"user_input": user_input},
        stream_mode=["updates", "custom"],
        version="v2",
    ):
        if chunk["type"] == "custom":
            event_data = json.dumps(chunk["data"])
            yield f"data: {event_data}\n\n"
        elif chunk["type"] == "updates":
            for node_name, state in chunk["data"].items():
                event_data = json.dumps({"node": node_name, "state": state})
                yield f"event: node_update\ndata: {event_data}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"

@app.post("/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        plan_stream_generator(request.message),
        media_type="text/event-stream",
    )
```

### Resumable SSE with Last-Event-ID

```python
from typing import Annotated
from fastapi import Header

@app.get("/plan/stream", response_class=EventSourceResponse)
async def stream_plan(
    last_event_id: Annotated[int | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    start = last_event_id + 1 if last_event_id is not None else 0
    # Resume from where client disconnected
    for i, event in enumerate(events):
        if i < start:
            continue
        yield ServerSentEvent(data=event, id=str(i))
```

---

## 3. Multi-Provider LLM — LangChain init_chat_model

### Configurable Model (Runtime Provider Switching)

```python
from langchain.chat_models import init_chat_model

# Create a configurable model — provider selected at runtime
configurable_model = init_chat_model(temperature=0)

# Use with different providers
configurable_model.invoke(
    "what's your name",
    config={"configurable": {"model": "gpt-5-nano"}},  # OpenAI
)
configurable_model.invoke(
    "what's your name",
    config={"configurable": {"model": "claude-sonnet-4-6"}},  # Anthropic
)
```

### Tool Binding with Configurable Model

```python
from pydantic import BaseModel, Field

class GetWeather(BaseModel):
    """Get the current weather in a given location"""
    location: str = Field(description="The city and state")

model = init_chat_model(temperature=0)
model_with_tools = model.bind_tools([GetWeather])

# Works with any provider at runtime
model_with_tools.invoke(
    "what's the weather in Beijing",
    config={"configurable": {"model": "gpt-5.4-mini"}}
).tool_calls
```

### Qwen via DashScope (OpenAI-Compatible Endpoint)

**Recommended approach**: Use `ChatOpenAI` wrapping DashScope's OpenAI-compatible API.

```python
from langchain_openai import ChatOpenAI

# Qwen via DashScope OpenAI-compatible endpoint
qwen_llm = ChatOpenAI(
    model="qwen-plus",  # or qwen-max, qwen3.6-plus, qwen3.7-max
    openai_api_key=os.getenv("DASHSCOPE_API_KEY"),
    openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
    temperature=0.7
)

# Tool calling works identically to OpenAI
qwen_with_tools = qwen_llm.bind_tools([search_restaurants, check_availability])
response = qwen_with_tools.invoke("帮我找附近的亲子餐厅")
print(response.tool_calls)
```

### DeepSeek via OpenAI-Compatible Endpoint

```python
from langchain_openai import ChatOpenAI

deepseek_llm = ChatOpenAI(
    model="deepseek-chat",  # or deepseek-v4
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
    openai_api_base="https://api.deepseek.com/v1",
    temperature=0.7
)
```

### Multi-Provider Factory with Fallback

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

class LLMProviderFactory:
    """Multi-provider LLM with priority-based fallback."""
    
    PROVIDERS = {
        "qwen": {
            "class": ChatOpenAI,
            "kwargs": {
                "model": "qwen3.7-max",
                "openai_api_key_env": "DASHSCOPE_API_KEY",
                "openai_api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
            "priority": 1,
        },
        "deepseek": {
            "class": ChatOpenAI,
            "kwargs": {
                "model": "deepseek-chat",
                "openai_api_key_env": "DEEPSEEK_API_KEY",
                "openai_api_base": "https://api.deepseek.com/v1",
            },
            "priority": 2,
        },
        "anthropic": {
            "class": ChatAnthropic,
            "kwargs": {"model": "claude-sonnet-4-6"},
            "priority": 3,
        },
    }
    
    def get_model(self, provider: str | None = None, tools: list = None):
        """Get model instance, optionally with tools bound."""
        if provider:
            model = self._create_model(provider)
        else:
            model = self._create_model_with_fallback()
        if tools:
            model = model.bind_tools(tools)
        return model
    
    async def invoke_with_fallback(self, messages, tools=None):
        """Try providers in priority order."""
        for name in sorted(self.PROVIDERS, key=lambda k: self.PROVIDERS[k]["priority"]):
            try:
                model = self.get_model(name, tools)
                return await model.ainvoke(messages)
            except Exception as e:
                logger.warning(f"Provider {name} failed: {e}")
                continue
        raise AllProvidersFailedError("All LLM providers failed")
```

---

## 4. LangGraph + FastAPI Integration Pattern

### Async Graph Execution with SSE Streaming

```python
from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

app = FastAPI()
checkpointer = MemorySaver()

# Compile graph with checkpointer for interrupt support
graph = build_planning_graph().compile(checkpointer=checkpointer)

@app.post("/plan/create")
async def create_plan(request: PlanRequest):
    config = {"configurable": {"thread_id": request.session_id}}
    
    async def event_generator():
        async for chunk in graph.astream(
            {"user_input": request.message, "scenario": request.scenario},
            config=config,
            stream_mode=["updates", "custom"],
            version="v2",
        ):
            if chunk["type"] == "custom":
                yield ServerSentEvent(data=chunk["data"], event="progress")
            elif chunk["type"] == "updates":
                for node, state in chunk["data"].items():
                    yield ServerSentEvent(
                        data={"node": node, "state": state},
                        event="node_complete"
                    )
        # Check if interrupted (waiting for user approval)
        snapshot = graph.get_state(config)
        if snapshot.next:  # Graph is paused
            yield ServerSentEvent(
                data={"interrupt": snapshot.values.get("plan")},
                event="plan_ready"
            )
    
    return EventSourceResponse(event_generator())

@app.post("/plan/approve")
async def approve_plan(request: ApproveRequest):
    config = {"configurable": {"thread_id": request.session_id}}
    
    async def event_generator():
        async for chunk in graph.astream(
            Command(resume=request.approved),
            config=config,
            stream_mode=["updates", "custom"],
            version="v2",
        ):
            if chunk["type"] == "custom":
                yield ServerSentEvent(data=chunk["data"], event="execution_progress")
    
    return EventSourceResponse(event_generator())
```

---

## 5. Key Implementation Decisions

### Why LangGraph over raw agent loop

| Feature | Raw Loop (learn-claude-code style) | LangGraph |
|---------|-----------------------------------|-----------|
| State persistence | Manual (messages list) | Built-in checkpointer |
| Interrupt/resume | Not supported | Native `interrupt()` + `Command(resume=)` |
| Streaming progress | Manual SSE formatting | `get_stream_writer()` + stream_mode |
| Conditional routing | if/else in loop | Declarative `add_conditional_edges` |
| Graph visualization | None | `get_graph().draw_mermaid_png()` |

**Verdict**: LangGraph adds value specifically because of interrupt (plan approval) and streaming (progress events). Without these requirements, a raw loop would suffice.

### Why NOT create_react_agent (prebuilt)

The prebuilt `create_react_agent` is a simple tool-calling loop. Our flow is NOT a simple ReAct loop — it's:
1. Parse intent → 2. Generate plan → 3. **Interrupt for approval** → 4. Execute steps → 5. Handle errors

This requires a custom StateGraph with explicit nodes and conditional edges. The prebuilt agent doesn't support the interrupt-in-the-middle pattern we need.

### Qwen Integration Strategy

Use `ChatOpenAI` with DashScope's OpenAI-compatible endpoint. This gives us:
- Standard `bind_tools()` / `.tool_calls` interface
- Same code path as DeepSeek and OpenAI
- No need for `langchain-community` ChatTongyi (less maintained)

All three providers (Qwen, DeepSeek, Claude) expose OpenAI-compatible or native LangChain interfaces, so our multi-provider adapter is straightforward.

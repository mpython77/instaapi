# Memory & Streaming

## Agent Memory

`AgentMemory` persists conversation history across sessions. The agent can recall past interactions.

### Enable Memory

```python
agent = InstaAgent(
    ig=ig,
    provider="gemini",
    api_key="...",
    memory=True,                              # Enable persistence
    memory_dir=".InstaHarvest v2_memory",            # Custom directory (optional)
)

# Conversations auto-save after each ask()
result = agent.ask("Get Cristiano's followers")
# Session saved to .InstaHarvest v2_memory/
```

### Memory API

```python
from instaharvest_v2.agent.memory import AgentMemory

mem = AgentMemory(memory_dir=".InstaHarvest v2_memory")

# Save a session
mem.save_session("session_001", messages, metadata={"topic": "followers"})

# List past sessions
sessions = mem.list_sessions(limit=20)
for s in sessions:
    print(f"{s['session_id']} — {s['summary']} ({s['message_count']} msgs)")

# Load a specific session
data = mem.load_session("session_001")

# Load the most recent session
latest = mem.load_latest()

# Search through past conversations
results = mem.search("cristiano followers", limit=5)
```

### Storage

Sessions are stored as JSON files:

```text
.InstaHarvest v2_memory/
├── index.json              # Session index
├── session_abc123.json     # Session data
├── session_def456.json
└── ...
```

| Setting | Default | Description |
| --- | --- | --- |
| `memory_dir` | `.InstaHarvest v2_memory` | Storage directory |
| `max_sessions` | 50 | Max stored sessions |
| `max_history` | 100 | Max messages per session |

---

## Streaming

`StreamHandler` enables real-time output as the agent thinks and acts.

### Enable Streaming

```python
agent = InstaAgent(
    ig=ig,
    provider="gemini",
    api_key="...",
    streaming=True,      # Enable real-time output
)

# Now ask() will stream progress to terminal
result = agent.ask("Analyze top 10 posts by nike")
```

CLI output:

```text
🤖 
  🔧 run_InstaHarvest v2_code: Getting nike posts...
  ✅ ExecutionResult: 10 posts loaded
  📍 Step 2/15...
  🔧 analyze_data: Computing engagement...
  ✅ Done

✅ Analysis complete (3.2s)
```

### Stream Modes

| Mode | Usage | Description |
| --- | --- | --- |
| `cli` | Terminal apps | Prints to stdout with emojis |
| `web` | FastAPI/SSE | Server-Sent Events format |
| `callback` | Custom | Calls your function |
| `buffer` | Silent | Buffers without output |

### Custom Callback

```python
from instaharvest_v2.agent.streaming import StreamHandler

def my_handler(event_type, data):
    if event_type == "text":
        print(f"[AI] {data}", end="")
    elif event_type == "tool_call":
        print(f"[TOOL] {data}")
    elif event_type == "error":
        print(f"[ERR] {data}")

handler = StreamHandler(callback=my_handler)
```

### Web Streaming (SSE)

```python
from instaharvest_v2.agent.streaming import WebStreamHandler

handler = WebStreamHandler()

# Get events for polling
events = handler.get_events()

# Iterate as SSE format
for sse in handler.iter_events():
    print(sse)  # "event: text\ndata: Hello\n\n"
```

### Events

| Event | When |
| --- | --- |
| `start` | Streaming begins |
| `text` | Each text chunk from LLM |
| `tool_call` | Agent invokes a tool |
| `tool_result` | Tool returns result |
| `step` | Each agent loop iteration |
| `error` | Error occurs |
| `done` | Streaming completes |

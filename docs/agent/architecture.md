# Architecture

## System Overview

```mermaid
graph TB
    User["👤 User"] -->|natural language| Agent["🤖 InstaAgent"]
    Agent -->|prompt| Provider["☁️ AI Provider"]
    Provider -->|tool calls| Agent
    Agent -->|check| Perm["🔒 PermissionManager"]
    Agent -->|execute| Exec["⚡ SafeExecutor"]
    Exec -->|code| IG["📱 Instagram Client"]
    Agent -->|save| Mem["💾 AgentMemory"]
    Agent -->|track| Cost["💰 CostTracker"]
    Agent -->|stream| Stream["📡 StreamHandler"]
    Agent -->|notify| Hook["🔔 WebhookNotifier"]

    subgraph Providers
        Gemini["Gemini"]
        OpenAI["OpenAI"]
        Claude["Claude"]
        DeepSeek["DeepSeek"]
        Ollama["Ollama"]
        More["+ 8 more"]
    end

    Provider --- Providers
```

## Module Map

| Module | Class | Purpose |
| --- | --- | --- |
| `core.py` | `InstaAgent` | Main agent — LLM loop, tool dispatch |
| `coordinator.py` | `AgentCoordinator` | Multi-agent parallel/sequential |
| `executor.py` | `SafeExecutor` | Sandboxed code execution |
| `permissions.py` | `PermissionManager` | 3-level permission control |
| `memory.py` | `AgentMemory` | Session persistence (JSON) |
| `cost_tracker.py` | `CostTracker` | Token usage & cost monitoring |
| `streaming.py` | `StreamHandler` | Real-time output (CLI/Web/callback) |
| `plugins.py` | `PluginManager` | Custom tool registration |
| `vision.py` | `VisionAnalyzer` | Image analysis (multimodal) |
| `webhook.py` | `WebhookNotifier` | Telegram/Discord/Email notifications |
| `scheduler.py` | `AgentScheduler` | Cron-like task scheduling |
| `tools.py` | `TOOL_HANDLERS` | 10 built-in tool implementations |
| `knowledge.py` | `SYSTEM_PROMPT` | Full InstaHarvest v2 knowledge base |
| `providers/` | `BaseProvider` | 14 AI provider adapters |
| `cli.py` | `main()` | Terminal interface |
| `web.py` | `create_app()` | FastAPI web UI |

## Agent Loop

```mermaid
sequenceDiagram
    participant U as User
    participant A as InstaAgent
    participant L as LLM Provider
    participant E as SafeExecutor

    U->>A: agent.ask("Get Cristiano's followers")
    A->>L: System prompt + user message
    L-->>A: tool_call: run_InstaHarvest v2_code
    A->>A: Permission check ✅
    A->>E: Execute code in sandbox
    E-->>A: ExecutionResult (output, variables)
    A->>L: Tool result → next step
    L-->>A: Text response (final answer)
    A-->>U: AgentResult
```

**Max steps**: default 15 iterations. Agent stops when LLM responds without tool calls or limit is reached.

## Security Model

`SafeExecutor` provides sandboxed code execution:

- ✅ **Whitelisted imports only**: `json`, `csv`, `datetime`, `math`, `re`, `collections`, `statistics`, `InstaHarvest v2`
- ❌ **Blocked**: `subprocess`, `os.system`, `eval`, `exec`, `socket`, `ctypes`, `pickle.loads`
- 🔒 **File access**: Read/write only in current directory
- ⏱️ **Timeout**: Configurable (default 30s)
- 🛡️ **Code validation**: Static analysis before execution

```python
# Blocked patterns — auto-rejected
BLOCKED = [
    "subprocess", "os.system", "os.popen",
    "__import__", "eval(", "exec(",
    "open(/",      # absolute paths
    "socket.", "http.server", "ctypes",
    "sys.exit", "quit()", "exit()",
]
```

## Data Flow

```text
User Message
    ↓
InstaAgent.ask()
    ↓
_build_mode_info()     → detect sync/async/anon mode
    ↓
Provider.generate()    → send to LLM
    ↓
_agent_loop()          → iterate until done
    ├── PermissionManager.check()
    ├── SafeExecutor.run()       → sandboxed code
    ├── TOOL_HANDLERS[name]()    → built-in tools
    ├── PluginManager.execute()  → custom tools
    ├── StreamHandler.on_*()     → real-time output
    └── CostTracker.record()     → track usage
    ↓
AgentResult(answer, code, files, steps, tokens, duration)
```

# AI Agent

InstaAPI's built-in AI Agent lets you control Instagram using **natural language**. No code needed — just tell the agent what you want, and it writes, executes, and returns results automatically.

## Why Use the Agent?

| Without Agent | With Agent |
|---|---|
| Write Python code manually | Just say what you want |
| Handle errors yourself | Agent retries automatically |
| Know the API by heart | Agent knows every method |
| Build scripts from scratch | Use pre-built templates |

## Quick Start

```python
from instaapi import Instagram
from instaapi.agent import InstaAgent, Permission

ig = Instagram.from_env(".env")
agent = InstaAgent(
    ig=ig,
    provider="gemini",
    api_key="AIza...",
    permission=Permission.FULL_ACCESS,
)

result = agent.ask("Get Cristiano's last 5 posts and save to posts.csv")
print(result.answer)
```

## Three Modes

=== "Login Mode (Full API)"

    ```python
    ig = Instagram.from_env(".env")
    agent = InstaAgent(ig=ig, provider="gemini", api_key="...")
    # Access: ALL methods — follow, like, DM, upload, scrape...
    ```

=== "Anonymous Mode (No Login)"

    ```python
    agent = InstaAgent(provider="gemini", api_key="...")
    # Access: ig.public.* only — profiles, posts, public data
    ```

=== "Async Mode"

    ```python
    ig = AsyncInstagram.from_env(".env")
    agent = InstaAgent(ig=ig, provider="gemini", api_key="...")
    # Agent auto-detects and generates async/await code
    ```

## Supported AI Providers

| Provider | Default Model | API Key Env Var |
|---|---|---|
| **Google Gemini** | gemini-2.5-flash | `GEMINI_API_KEY` |
| **OpenAI** | gpt-4.1-mini | `OPENAI_API_KEY` |
| **Anthropic Claude** | claude-sonnet-4 | `ANTHROPIC_API_KEY` |
| **DeepSeek** | deepseek-chat | `DEEPSEEK_API_KEY` |
| **Qwen** | qwen3-32b | `DASHSCOPE_API_KEY` |
| **Groq** | llama-3.3-70b | `GROQ_API_KEY` |
| **Together AI** | llama-3.3-70b | `TOGETHER_API_KEY` |
| **Mistral** | mistral-large | `MISTRAL_API_KEY` |
| **Ollama** (local) | llama3.2 | _none_ |
| **OpenRouter** | auto | `OPENROUTER_API_KEY` |
| **Fireworks AI** | llama-v3p3-70b | `FIREWORKS_API_KEY` |
| **Perplexity** | sonar-pro | `PERPLEXITY_API_KEY` |
| **xAI (Grok)** | grok-3 | `XAI_API_KEY` |

!!! tip "Latest Models"
    Each provider supports many models beyond the default. Pass `model="model-name"` to override:

    - **Gemini**: `gemini-3.1-pro`, `gemini-3-pro`, `gemini-3-flash`, `gemini-2.5-pro`
    - **OpenAI**: `gpt-5.2`, `gpt-5`, `gpt-4.1`, `o3`, `o4-mini`
    - **Claude**: `claude-opus-4.6`, `claude-sonnet-4.6`, `claude-haiku-4.5`
    - **DeepSeek**: `deepseek-reasoner` (thinking mode)
    - **xAI**: `grok-4-latest`, `grok-3-latest`

## Permission Levels

```python
from instaapi.agent import Permission

# Ask before every action (safest)
agent = InstaAgent(ig=ig, permission=Permission.ASK_EVERY, ...)

# Ask once per action type
agent = InstaAgent(ig=ig, permission=Permission.ASK_ONCE, ...)

# No prompts (max speed, for automation)
agent = InstaAgent(ig=ig, permission=Permission.FULL_ACCESS, ...)
```

## Built-in Tools (10)

The agent has 10 tools it can use to complete tasks:

| # | Tool | Description |
|---|---|---|
| 1 | `run_instaapi_code` | Execute Python code in a secure sandbox |
| 2 | `save_to_file` | Save results to CSV/JSON/TXT files |
| 3 | `ask_user` | Ask the user for clarification |
| 4 | `read_file` | Read existing files (CSV, JSON, TXT) |
| 5 | `list_files` | List directory contents |
| 6 | `download_media` | Download Instagram photos/videos |
| 7 | `analyze_data` | Data analysis (stats, top N, trends) |
| 8 | `http_request` | HTTP GET/POST to external APIs |
| 9 | `create_chart` | Create charts (bar, line, pie) |
| 10 | `search_web` | Search the internet (DuckDuckGo) |

## Constructor Parameters

```python
InstaAgent(
    ig=None,                           # Instagram instance (None = anonymous)
    provider="gemini",                 # AI provider name
    api_key=None,                      # API key (auto-detect from env)
    model=None,                        # Model override
    permission=Permission.ASK_EVERY,   # Permission level
    permission_callback=None,          # Custom permission handler
    max_steps=15,                      # Max agent loop iterations
    timeout=30,                        # Code execution timeout (seconds)
    verbose=True,                      # Show step-by-step progress
    memory=False,                      # Enable conversation memory
    memory_dir=None,                   # Custom memory directory
    cost_tracking=True,                # Track token costs
    retry_count=2,                     # Auto-retry on failures
    streaming=False,                   # Real-time output
)
```

## Cross-Platform Support

InstaAPI Agent works on **Windows**, **Linux**, and **macOS**:

- **Paths**: Automatically uses OS-appropriate directories (`%APPDATA%` on Windows, `~/.local/share` on Linux, `~/Library` on macOS)
- **Console**: Unicode/emoji auto-detection with ASCII fallback for legacy terminals
- **Encoding**: UTF-8 everywhere with graceful error handling
- **File I/O**: Atomic writes prevent data corruption
- **No OS-specific dependencies**: Pure Python, no `signal.alarm` or Unix-only APIs

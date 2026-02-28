# Tools & Plugins

## Built-in Tools (10)

The agent automatically selects the right tool for each task:

### 1. `run_InstaHarvest v2_code`

Execute Python code in a secure sandbox with access to `ig` (Instagram client).

```text
Agent decides to run:
    user = ig.users.get_by_username("cristiano")
    print(f"Followers: {user.followers:,}")
```

### 2. `save_to_file`

Save content to CSV, JSON, or TXT files.

| Param | Type | Description |
| --- | --- | --- |
| `filename` | `str` | Output file name |
| `content` | `str` | File content |
| `format` | `str` | `csv`, `json`, or `txt` |

### 3. `ask_user`

Ask the user a clarifying question before proceeding.

### 4. `read_file`

Read file contents from current directory (CSV, JSON, TXT).

| Param | Type | Description |
| --- | --- | --- |
| `filename` | `str` | File path (relative only) |
| `max_lines` | `int` | Max lines to read (default: 100) |

### 5. `list_files`

List files in a directory with size and modification time.

### 6. `download_media`

Download Instagram photos/videos via instaharvest_v2.

| Param | Type | Description |
| --- | --- | --- |
| `url` | `str` | Instagram post/story URL |
| `output_dir` | `str` | Save directory (default: `.`) |

### 7. `analyze_data`

Statistical analysis on data from files or raw input.

| Param | Type | Description |
| --- | --- | --- |
| `source` | `str` | File path or raw JSON |
| `analysis_type` | `str` | `summary`, `top_n`, `distribution`, `compare`, `trend` |
| `field` | `str` | Field to analyze |
| `top_n` | `int` | Top N count (default: 10) |

### 8. `http_request`

Make HTTP requests to external APIs.

| Param | Type | Description |
| --- | --- | --- |
| `url` | `str` | Request URL |
| `method` | `str` | `GET` or `POST` |
| `headers` | `dict` | Request headers |
| `body` | `str` | Request body |

### 9. `create_chart`

Create ASCII charts (no matplotlib dependency).

| Param | Type | Description |
| --- | --- | --- |
| `chart_type` | `str` | `bar`, `line`, `pie` |
| `labels` | `list` | Label array `["A", "B", "C"]` |
| `values` | `list` | Value array `[10, 20, 30]` |
| `title` | `str` | Chart title |
| `filename` | `str` | Output file (default: `chart.txt`) |

### 10. `search_web`

Search the internet via DuckDuckGo Lite.

| Param | Type | Description |
| --- | --- | --- |
| `query` | `str` | Search query |
| `max_results` | `int` | Max results (default: 5) |

---

## Custom Plugins

Register your own functions as agent tools using `PluginManager`:

```python
from instaharvest_v2.agent import InstaAgent

agent = InstaAgent(ig=ig, provider="gemini", api_key="...")

# Register a custom tool
def translate(args):
    text = args.get("text", "")
    target = args.get("target_language", "en")
    # Your translation logic here
    return f"Translated: {text}"

agent.register_tool(
    name="translate",
    handler=translate,
    description="Translate text between languages",
    schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to translate"},
            "target_language": {"type": "string", "description": "Target language code"},
        },
    },
)

# Now the agent can use your tool!
result = agent.ask("Translate 'Hello World' to Spanish")
```

### Auto-Schema

If you don't provide a schema, `PluginManager` auto-generates one from your function signature:

```python
def sentiment(text: str, detailed: bool = False):
    """Analyze text sentiment."""
    return {"score": 0.8, "label": "positive"}

# Schema auto-generated from type hints
agent.register_tool("sentiment", sentiment, "Analyze sentiment")
```

### Plugin Management

```python
# List registered plugins
plugins = agent.plugins.list_plugins()

# Check if plugin exists
agent.plugins.has("translate")  # True

# Remove a plugin
agent.plugins.unregister("translate")

# Plugin count
agent.plugins.count  # 0
```

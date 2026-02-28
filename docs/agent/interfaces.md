# CLI & Web UI

## CLI (Terminal)

Interactive and one-shot command-line interface.

### One-Shot Question

```bash
python -m instaharvest_v2.agent.cli "Get Cristiano's follower count"
```

### Interactive Chat

```bash
python -m instaharvest_v2.agent.cli --interactive
```

```text
🤖 InstaHarvest v2 Agent (Gemini)
Type 'exit' to quit.

You: Get Cristiano's followers
Agent: Cristiano Ronaldo (@cristiano) has 650,000,000 followers.

You: Compare with Messi
Agent: ...

You: exit
```

### CLI Options

```bash
python -m instaharvest_v2.agent.cli [OPTIONS] [QUESTION]
```

| Option | Default | Description |
| --- | --- | --- |
| `QUESTION` | — | One-shot question |
| `-i`, `--interactive` | — | Interactive chat mode |
| `--provider` | `gemini` | AI provider |
| `--model` | auto | Model override |
| `--api-key` | env | API key |
| `--env` | `.env` | Path to .env file |
| `--permission` | `ask_once` | `ask_every`, `ask_once`, `full_access` |
| `--full-access` | — | Skip all permission checks |
| `--parallel TASK...` | — | Run tasks in parallel |
| `--max-steps` | `15` | Max agent loop steps |
| `--timeout` | `30` | Code execution timeout (sec) |
| `--quiet` | — | Show only result |

### Examples

```bash
# Use OpenAI
python -m instaharvest_v2.agent.cli --provider openai "Analyze nike engagement"

# Use local Ollama
python -m instaharvest_v2.agent.cli --provider ollama --model llama3.2 "Get my followers"

# Full access (no prompts)
python -m instaharvest_v2.agent.cli --full-access "Like all posts in my feed"

# Parallel tasks
python -m instaharvest_v2.agent.cli --parallel \
    "Get Cristiano followers" \
    "Get Messi followers" \
    "Get Neymar followers"
```

---

## Web UI (Browser)

Browser-based chat interface powered by FastAPI.

### Start

```bash
python -m instaharvest_v2.agent.web
# Opens http://localhost:8899
```

### Web Options

```bash
python -m instaharvest_v2.agent.web [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--port` | `8899` | Server port |
| `--host` | `127.0.0.1` | Server host |
| `--provider` | `gemini` | AI provider |
| `--model` | auto | Model override |
| `--api-key` | env | API key |
| `--env` | `.env` | Path to .env file |
| `--permission` | `ask_once` | Permission level |

### API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Chat UI (HTML page) |
| `POST` | `/api/ask` | Send a question |
| `POST` | `/api/parallel` | Run parallel tasks |
| `GET` | `/api/history` | Get conversation history |
| `POST` | `/api/reset` | Reset conversation |

### API Examples

```bash
# Ask a question
curl -X POST http://localhost:8899/api/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "Get Cristiano followers"}'

# Response:
{
  "success": true,
  "answer": "Cristiano has 650M followers",
  "code": "user = ig.users.get_by_username(...)",
  "steps": 2,
  "tokens": 1200,
  "duration": 3.5
}
```

```bash
# Parallel tasks
curl -X POST http://localhost:8899/api/parallel \
  -H "Content-Type: application/json" \
  -d '{"tasks": ["Get Cristiano followers", "Get Messi followers"]}'
```

### Programmatic Usage

```python
from instaharvest_v2.agent.web import create_app

app = create_app(
    env_path=".env",
    provider="gemini",
    api_key="AIza...",
    permission_level="full_access",
)

# Run with uvicorn
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8899)
```

### Requirements

```bash
pip install fastapi uvicorn
```

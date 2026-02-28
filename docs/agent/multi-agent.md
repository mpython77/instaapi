# Multi-Agent Coordinator

`AgentCoordinator` — multiple agents working in **parallel** or **sequential** mode with shared state.

## Quick Example

```python
from instaharvest_v2 import Instagram
from instaharvest_v2.agent import InstaAgent, AgentCoordinator, Permission

ig = Instagram.from_env(".env")

coordinator = AgentCoordinator(
    ig=ig,
    provider="gemini",
    api_key="AIza...",
    max_workers=3,
)

# Parallel — each task runs in its own thread
results = coordinator.run_parallel([
    "Get Cristiano's follower count",
    "Get Messi's follower count",
    "Get Neymar's follower count",
])

for answer in results.all_answers:
    print(answer)

print(f"Total: {results.total_duration:.1f}s | {results.total_tokens} tokens")
```

## Parallel Execution

Each task gets its own `InstaAgent` instance, running in `ThreadPoolExecutor`:

```python
results = coordinator.run_parallel([
    "Download nike's profile picture",
    "Export adidas followers to CSV",
    "Analyze engagement rate for puma",
])

# Check results
print(results.success)          # True if all succeeded
print(results.total_duration)   # Wall clock time
print(results.total_tokens)     # Combined token usage
print(results.total_steps)      # Combined agent steps
```

## Sequential Execution

Tasks run in order. Each task sees previous results as context:

```python
results = coordinator.run_sequential([
    "Get Cristiano's profile info",
    "Analyze his last 10 posts engagement",
    "Save the results to report.csv",
])
```

The coordinator automatically injects previous task results into each subsequent prompt.

## Constructor

```python
AgentCoordinator(
    ig,                                    # Instagram instance
    provider="gemini",                     # AI provider
    api_key=None,                          # API key
    model=None,                            # Model override
    permission=Permission.FULL_ACCESS,     # Permission level
    max_workers=3,                         # Max parallel threads
    verbose=True,                          # Show progress
)
```

## CoordinatorResult

| Property | Type | Description |
| --- | --- | --- |
| `results` | `List[AgentResult]` | Individual task results |
| `success` | `bool` | `True` if all tasks succeeded |
| `all_answers` | `List[str]` | List of answer strings |
| `total_duration` | `float` | Total wall time (seconds) |
| `total_tokens` | `int` | Combined token usage |
| `total_steps` | `int` | Combined agent steps |

## CLI Parallel Mode

```bash
python -m instaharvest_v2.agent.cli --parallel \
    "Get Cristiano followers" \
    "Get Messi followers" \
    "Get Neymar followers"
```

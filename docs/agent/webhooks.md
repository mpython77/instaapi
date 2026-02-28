# Webhooks & Scheduler

## WebhookNotifier

Send agent results to external services — Telegram, Discord, Email, or custom HTTP endpoints.

### Setup

```python
from instaharvest_v2.agent.webhook import WebhookNotifier

notifier = WebhookNotifier()

# Add Telegram
notifier.add_telegram(
    bot_token="123456:ABC-xyz",
    chat_id="987654321",
)

# Add Discord
notifier.add_discord(
    webhook_url="https://discord.com/api/webhooks/...",
)

# Add Email
notifier.add_email(
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    username="you@gmail.com",
    password="app-password",
    to_email="recipient@example.com",
)

# Add custom HTTP webhook
notifier.add_custom(
    url="https://my-api.com/webhook",
    headers={"Authorization": "Bearer token123"},
)
```

### Send Notifications

```python
# Simple message
notifier.notify("Task completed successfully!")

# With title and data
notifier.notify(
    message="Follower analysis done for @cristiano",
    title="InstaAPI Report",
    data={
        "followers": 650_000_000,
        "engagement_rate": 2.5,
        "top_post_likes": 15_000_000,
    },
)
```

### Channel Management

```python
notifier.channel_count   # Number of registered channels
notifier.clear()         # Remove all channels
```

### Supported Channels

| Channel | Method | Requires |
| --- | --- | --- |
| Telegram | `add_telegram()` | Bot token + Chat ID |
| Discord | `add_discord()` | Webhook URL |
| Email | `add_email()` | SMTP credentials |
| Custom | `add_custom()` | Any HTTP endpoint |

---

## AgentScheduler

Schedule agent tasks to run at intervals — cron-like automation.

### Basic Usage

```python
from instaharvest_v2.agent import InstaAgent
from instaharvest_v2.agent.scheduler import AgentScheduler

agent = InstaAgent(ig=ig, provider="gemini", api_key="...")
scheduler = AgentScheduler(agent)

# Every hour — check follower count
scheduler.add(
    task_id="follower_check",
    prompt="Get my current follower count and save to followers_log.csv",
    interval="1h",
)

# Every day — engagement report
scheduler.add(
    task_id="daily_report",
    prompt="Generate engagement report for my last 20 posts",
    interval="24h",
)

# Every 30 minutes, max 10 runs
scheduler.add(
    task_id="like_feed",
    prompt="Like the top 5 posts in my feed",
    interval="30m",
    max_runs=10,
)

# Start scheduler (runs in background thread)
scheduler.start()
```

### Interval Format

| Format | Example | Duration |
| --- | --- | --- |
| `Ns` | `30s` | 30 seconds |
| `Nm` | `15m` | 15 minutes |
| `Nh` | `2h` | 2 hours |
| `Nd` | `7d` | 7 days |

### Task Management

```python
# List all tasks
tasks = scheduler.list_tasks()
for t in tasks:
    print(f"{t['task_id']}: {t['interval']} (runs: {t['run_count']})")

# Disable/enable
scheduler.disable("follower_check")
scheduler.enable("follower_check")

# Remove
scheduler.remove("daily_report")

# Stop scheduler
scheduler.stop()

# Check status
scheduler.is_running   # bool
scheduler.task_count   # int
```

### Persistence

Schedule is automatically saved to `.instaapi_schedule.json` and restored on restart:

```python
scheduler = AgentScheduler(
    agent,
    persist_path=".instaapi_schedule.json",  # Custom path
)
```

### Callback

Get notified when tasks complete:

```python
def on_task_done(task_id, result):
    print(f"Task {task_id}: {result.answer[:100]}")
    # Optional: send webhook notification
    notifier.notify(f"Task {task_id} done: {result.answer}")

scheduler.start(callback=on_task_done)
```

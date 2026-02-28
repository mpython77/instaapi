# Multi-Account

For automation tools, running campaigns from a single account is risky. `MultiAccount` is a robust daemon-like structure that spins up parallel headless workers, assigning specific jobs to specific accounts.

## Quick Example

```python
from instaharvest_v2.multi_account import MultiAccountManager

# Setup 3 worker accounts
manager = MultiAccountManager()
manager.load_sessions([
    "session_bot1.json",
    "session_bot2.json",
    "session_bot3.json"
])

# Tell Bot 1 and Bot 2 to scrape profile followers
manager.assign_task(
    accounts=["session_bot1", "session_bot2"],
    action="scrape_followers",
    target="cristiano"
)

# Tell Bot 3 to like a specific post
manager.assign_task(
    accounts=["session_bot3"],
    action="like_media",
    target="1234567890"
)

# Start all workers concurrently
manager.start_workers()
```

## MultiAccount vs SmartRotation

Both handle multiple accounts, but serve different purposes:

| Feature | SmartRotation | MultiAccountManager |
|---|---|---|
| **Goal** | Distribute read operations to prevent rate-limits. | Run specific complex actions from specific profiles. |
| **Logic** | Returns the "healthiest" client for the next request. | Runs background threads permanently attached to one profile. |
| **Use Case** | Mass Profile Scraping, Data Harvesting. | Auto-DMs, Engagement Pods, Mass Follow scripts. |

## Creating Custom Actions

The MultiAccount Manager works on string-based actions mapped to functional callbacks:

```python
def my_custom_like_loop(ig_client, task_data):
    """
    ig_client is the dedicated Instagram() object for this worker.
    task_data is the target payload.
    """
    media_id = task_data.get("target")
    ig_client.media.like(media_id)
    print(f"[{ig_client.username}] Liked {media_id}!")

# Register action
manager.register_action("like_loop", my_custom_like_loop)

# Trigger Action
manager.assign_task(accounts=["bot1"], action="like_loop", target="ABC123XYZ")
```

For extremely complex interactions, MultiAccount integrates cleanly with the builtin `SchedulerAPI`.

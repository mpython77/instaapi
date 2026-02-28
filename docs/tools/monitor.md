# MonitorAPI

> `ig.monitor` — Real-time account monitoring with callbacks for follower changes, new posts, bio updates, and more.

## Quick Example

```python
ig = Instagram.from_env()

watcher = ig.monitor.watch("cristiano")
watcher.on_new_post(lambda data: print(f"New post: {data}"))
watcher.on_follower_change(lambda old, new: print(f"Followers: {old:,} → {new:,}"))
watcher.on_bio_change(lambda old, new: print(f"Bio: '{old}' → '{new}'"))

ig.monitor.start(interval=300)  # Check every 5 minutes
```

---

## Methods

### watch(username)

Start watching an account. Returns an `AccountWatcher` instance.

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Account to monitor |

**Returns:** `AccountWatcher`

---

### AccountWatcher Callbacks

```python
watcher = ig.monitor.watch("nike")
watcher.on_new_post(callback)          # New post detected
watcher.on_follower_change(callback)   # Follower count changed
watcher.on_bio_change(callback)        # Biography changed
watcher.on_story_update(callback)      # New story
```

All callbacks support chaining:

```python
watcher.on_new_post(notify).on_follower_change(log).on_bio_change(alert)
```

---

### start(interval=60)

Start the monitoring background thread.

| Param | Type | Default | Description |
|---|---|---|---|
| `interval` | `int` | 60 | Seconds between checks |

### stop()

Stop monitoring.

### unwatch(username)

Remove an account from monitoring.

### get_stats()

Get monitoring statistics.

```python
stats = ig.monitor.get_stats()
# {"watched_accounts": 5, "is_running": True, "total_checks": 142}
```

---

## Async Version

```python
from instaapi import AsyncInstagram

async with AsyncInstagram.from_env() as ig:
    watcher = ig.monitor.watch("cristiano")
    watcher.on_new_post(lambda d: print("New post!"))
    await ig.monitor.start(interval=300)
```

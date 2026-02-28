# SchedulerAPI

> `ig.scheduler` — Schedule posts, stories, and reels with background worker. Jobs persist to JSON and survive restarts.

## Quick Example

```python
ig = Instagram.from_env()

# Schedule a photo post
ig.scheduler.post_at(
    "2024-03-01 10:00",
    photo="photo.jpg",
    caption="Morning vibes ☀️",
)

# Schedule a reel
ig.scheduler.reel_at(
    "2024-03-01 18:00",
    video="reel.mp4",
    caption="Check this out! 🎬",
)

# Start background worker
ig.scheduler.start()
```

---

## Methods

### post_at(scheduled_time, photo, caption="", location_id=None)

Schedule a photo post.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `scheduled_time` | `str` | ✅ | — | When to post (`"2024-03-01 10:00"` or ISO) |
| `photo` | `str` | ✅ | — | Path to image file |
| `caption` | `str` | ❌ | `""` | Post caption |
| `location_id` | `int` | ❌ | `None` | Optional location |

**Returns:** `dict` with `{id, job_type, scheduled_at, status}`

---

### story_at(scheduled_time, photo=None, video=None)

Schedule a story.

| Param | Type | Required | Description |
|---|---|---|---|
| `scheduled_time` | `str` | ✅ | When to post |
| `photo` | `str` | ❌ | Path to image (mutually exclusive with video) |
| `video` | `str` | ❌ | Path to video |

**Returns:** `dict` — Job info

---

### reel_at(scheduled_time, video, caption="", cover_photo=None)

Schedule a reel.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `scheduled_time` | `str` | ✅ | — | When to post |
| `video` | `str` | ✅ | — | Path to video file |
| `caption` | `str` | ❌ | `""` | Reel caption |
| `cover_photo` | `str` | ❌ | `None` | Cover image path |

**Returns:** `dict` — Job info

---

### schedule_action(scheduled_time, action, action_name="custom", **kwargs)

Schedule any custom action.

| Param | Type | Required | Description |
|---|---|---|---|
| `scheduled_time` | `str` | ✅ | When to execute |
| `action` | `callable` | ✅ | Function to execute |
| `action_name` | `str` | ❌ | Human-readable name |
| `**kwargs` | | ❌ | Arguments for the action |

```python
ig.scheduler.schedule_action(
    "2024-03-01 03:00",
    action=ig.growth.unfollow_non_followers,
    action_name="cleanup_unfollowers",
    max_count=50,
)
```

---

### list_jobs(include_done=False)

List all scheduled jobs.

**Returns:** `list[dict]`

---

### cancel(job_id)

Cancel a pending job by ID.

---

### clear_done()

Remove completed/failed/cancelled jobs from the list.

---

### start() / stop()

Start or stop the background worker thread that checks for due jobs every 30 seconds.

```python
ig.scheduler.start()   # Start background worker
# ... scheduler runs in background ...
ig.scheduler.stop()    # Stop worker
```

---

## Job Persistence

Jobs are automatically saved to `scheduler_jobs.json` and restored on restart. The file is updated every time a job is added, executed, or cancelled.

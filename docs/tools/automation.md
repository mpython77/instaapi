# AutomationAPI

> `ig.automation` — Bot framework for auto-DM, auto-comment, auto-like with templates, safety limits, and human-like behavior.

## Quick Example

```python
ig = Instagram.from_env()

# Welcome DM to new followers
ig.automation.dm_new_followers(
    templates=[
        "Hey {username}! Thanks for following! 🙌",
        "Welcome {name}! Check out our latest collection 🔥",
    ],
    max_count=10,
)
```

---

## Methods

### dm_new_followers(templates, max_count=10, limits=None, on_progress=None)

Send welcome DM to new followers.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `templates` | `str\|list[str]` | ✅ | — | Message template(s) |
| `max_count` | `int` | ❌ | 10 | Max DMs to send |
| `limits` | `AutomationLimits` | ❌ | `None` | Safety limits |
| `on_progress` | `callable` | ❌ | `None` | Callback `(count, username)` |

**Template variables:** `{username}`, `{name}`, `{random}` (random emoji/word)

**Returns:** `dict` with `{sent, errors, duration_seconds}`

---

### comment_on_hashtag(tag, templates, count=10, limits=None, on_progress=None)

Auto-comment on hashtag posts.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `tag` | `str` | ✅ | — | Hashtag (without #) |
| `templates` | `list[str]` | ✅ | — | Comment templates (random pick) |
| `count` | `int` | ❌ | 10 | Posts to comment on |
| `limits` | `AutomationLimits` | ❌ | `None` | Safety limits |
| `on_progress` | `callable` | ❌ | `None` | Progress callback |

**Returns:** `dict` with `{commented, errors, duration_seconds}`

---

### auto_like_feed(count=20, limits=None, on_progress=None)

Auto-like posts from your timeline feed.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `count` | `int` | ❌ | 20 | Posts to like |
| `limits` | `AutomationLimits` | ❌ | `None` | Safety limits |
| `on_progress` | `callable` | ❌ | `None` | Callback `(liked_count, shortcode)` |

**Returns:** `dict` with `{liked, errors, duration_seconds}`

---

### auto_like_hashtag(tag, count=20, limits=None, on_progress=None)

Auto-like posts from a hashtag.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `tag` | `str` | ✅ | — | Hashtag (without #) |
| `count` | `int` | ❌ | 20 | Posts to like |
| `limits` | `AutomationLimits` | ❌ | `None` | Safety limits |
| `on_progress` | `callable` | ❌ | `None` | Progress callback |

**Returns:** `dict` with `{liked, errors, hashtag, duration_seconds}`

---

### watch_stories(username, limits=None)

Watch all stories of a user.

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Target username |
| `limits` | `AutomationLimits` | ❌ | Safety limits |

**Returns:** `dict` with `{watched, username}`

---

## AutomationLimits

```python
from instaharvest_v2.api.automation import AutomationLimits

limits = AutomationLimits(
    max_per_hour=30,
    min_delay=15.0,
    max_delay=60.0,
    stop_on_challenge=True,
    stop_on_rate_limit=True,
)
```

| Param | Type | Default | Description |
|---|---|---|---|
| `max_per_hour` | `int` | 30 | Max actions per hour |
| `min_delay` | `float` | 15.0 | Min delay (seconds) |
| `max_delay` | `float` | 60.0 | Max delay (seconds) |
| `stop_on_challenge` | `bool` | `True` | Stop on challenge |
| `stop_on_rate_limit` | `bool` | `True` | Stop on 429 |

---

## TemplateEngine

Templates support variables and randomization:

```python
from instaharvest_v2.api.automation import TemplateEngine

# Render a template
msg = TemplateEngine.render(
    "Hello {username}! Welcome 🙌",
    context={"username": "john_doe", "name": "John"},
)

# Pick random template and render
msg = TemplateEngine.pick_and_render(
    ["Great post! 🔥", "Love this! ❤️", "Amazing {username}!"],
    context={"username": "nike"},
)
```

**Variables:** `{username}`, `{name}`, `{random}`

# GrowthAPI

> `ig.growth` — Smart follow/unfollow system with safety limits, anti-ban delays, whitelist/blacklist, and progress tracking.

## Quick Example

```python
from instaharvest_v2 import Instagram
from instaharvest_v2.api.growth import GrowthFilters, GrowthLimits

ig = Instagram.from_env()

# Follow followers of a competitor
ig.growth.follow_users_of(
    "nike",
    count=20,
    filters=GrowthFilters(min_followers=100, has_bio=True),
    limits=GrowthLimits(max_per_hour=15, min_delay=30),
)
```

---

## Methods

### follow_users_of(username, count=20, filters=None, limits=None, on_progress=None)

Follow followers of a target user (competitor).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Target user whose followers to follow |
| `count` | `int` | ❌ | 20 | How many to follow |
| `filters` | `GrowthFilters\|dict` | ❌ | `None` | User filters |
| `limits` | `GrowthLimits` | ❌ | `None` | Safety limits |
| `on_progress` | `callable` | ❌ | `None` | Callback `(followed, total, username)` |

**Returns:** `dict` with `{followed, skipped, errors, duration_seconds}`

---

### follow_hashtag_users(tag, count=20, filters=None, limits=None, on_progress=None)

Follow users who posted with a hashtag.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `tag` | `str` | ✅ | — | Hashtag (without #) |
| `count` | `int` | ❌ | 20 | How many to follow |
| `filters` | `GrowthFilters\|dict` | ❌ | `None` | User filters |
| `limits` | `GrowthLimits` | ❌ | `None` | Safety limits |
| `on_progress` | `callable` | ❌ | `None` | Progress callback |

**Returns:** `dict` with `{followed, skipped, errors, duration_seconds}`

---

### unfollow_non_followers(max_count=50, whitelist=None, limits=None, on_progress=None)

Unfollow users who don't follow you back.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `max_count` | `int` | ❌ | 50 | Max users to unfollow |
| `whitelist` | `list[str]` | ❌ | `None` | Usernames to never unfollow |
| `limits` | `GrowthLimits` | ❌ | `None` | Safety limits |
| `on_progress` | `callable` | ❌ | `None` | Progress callback |

**Returns:** `dict` with `{unfollowed, skipped, duration_seconds}`

---

### unfollow_all(keep_list=None, max_count=100, limits=None)

Mass unfollow — keep specified users.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `keep_list` | `list[str]` | ❌ | `None` | Usernames to keep following |
| `max_count` | `int` | ❌ | 100 | Max to unfollow |
| `limits` | `GrowthLimits` | ❌ | `None` | Safety limits |

**Returns:** `dict` with `{unfollowed, skipped, duration_seconds}`

---

### get_non_followers()

Get users you follow but who don't follow you back.

**Returns:** `list[dict]`

---

### get_fans()

Get fans — followers you don't follow back.

**Returns:** `list[dict]`

---

### add_whitelist(usernames) / add_blacklist(usernames)

Add usernames to whitelist (never unfollow) or blacklist (never follow).

```python
ig.growth.add_whitelist(["best_friend", "partner"])
ig.growth.add_blacklist(["spam_account"])
```

---

## GrowthFilters

```python
from instaharvest_v2.api.growth import GrowthFilters

filters = GrowthFilters(
    min_followers=50,
    max_followers=10000,
    min_posts=5,
    is_private=False,
    has_bio=True,
    bio_keywords=["fashion", "style"],
    exclude_keywords=["spam"],
)
```

| Param | Type | Default | Description |
|---|---|---|---|
| `min_followers` | `int` | 0 | Minimum follower count |
| `max_followers` | `int` | 0 | Maximum (0 = no limit) |
| `min_posts` | `int` | 0 | Minimum post count |
| `is_private` | `bool\|None` | `None` | Filter by privacy |
| `is_verified` | `bool\|None` | `None` | Filter by verified |
| `has_bio` | `bool\|None` | `None` | Must have bio text |
| `bio_keywords` | `list[str]` | `None` | Bio must contain any |
| `exclude_keywords` | `list[str]` | `None` | Exclude if bio contains |

## GrowthLimits

```python
from instaharvest_v2.api.growth import GrowthLimits

limits = GrowthLimits(
    max_per_hour=20,
    max_per_day=150,
    min_delay=25.0,
    max_delay=90.0,
    stop_on_challenge=True,
    stop_on_rate_limit=True,
)
```

| Param | Type | Default | Description |
|---|---|---|---|
| `max_per_hour` | `int` | 20 | Max actions per hour |
| `max_per_day` | `int` | 150 | Max actions per day |
| `min_delay` | `float` | 25.0 | Minimum delay (seconds) |
| `max_delay` | `float` | 90.0 | Maximum delay (seconds) |
| `stop_on_challenge` | `bool` | `True` | Stop on challenge |
| `stop_on_rate_limit` | `bool` | `True` | Stop on 429 |

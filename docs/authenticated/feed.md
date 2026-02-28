# FeedAPI

> `ig.feed` — Fetch user feeds, timeline, liked/saved posts, hashtag and location feeds.

## Quick Example

```python
from instaapi import Instagram

ig = Instagram.from_env()

# Get the latest feed of a user
feed = ig.feed.get_user_feed(173560420)

for item in feed.get("items", []):
    print(item.get("code"), item.get("like_count"))
    
# Check for next page
if feed.get("more_available"):
    print("Next cursor:", feed.get("next_max_id"))
```

## Methods

### get_user_feed(user_id, count=12, max_id=None)

Get the main post feed for any user.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `user_id` | `int\|str` | ✅ | — | User PK |
| `count` | `int` | ❌ | 12 | Posts per page |
| `max_id` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict` — raw API response with `items`, `more_available`, `next_max_id`

```python
feed = ig.feed.get_user_feed(173560420)

# Pagination
if feed.get("more_available"):
    page2 = ig.feed.get_user_feed(173560420, max_id=feed["next_max_id"])
```

---

### get_all_posts(user_id, max_posts=100, count_per_page=12)

Get all posts with automatic pagination.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `user_id` | `int\|str` | ✅ | — | User PK |
| `max_posts` | `int` | ❌ | 100 | Maximum total posts |
| `count_per_page` | `int` | ❌ | 12 | Posts per API call |

**Returns:** `list[Media]` — parsed Media models

```python
all_posts = ig.feed.get_all_posts(173560420, max_posts=50)
print(f"Got {len(all_posts)} posts")
```

---

### get_timeline(max_id=None)

Get your home timeline feed (posts from people you follow).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `max_id` | `str` | ❌ | `None` | Pagination token |

**Returns:** `dict`

```python
timeline = ig.feed.get_timeline()
```

---

### get_liked(max_id=None)

Get posts you have liked (via GraphQL).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `max_id` | `str` | ❌ | `None` | Pagination token |

**Returns:** `dict`

---

### get_saved(max_id=None)

Get your saved/bookmarked posts (via GraphQL).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `max_id` | `str` | ❌ | `None` | Pagination token |

**Returns:** `dict`

---

### get_tag_feed(hashtag, max_id=None)

Get posts by hashtag.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `hashtag` | `str` | ✅ | — | Hashtag name (without #) |
| `max_id` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict` with `items`, `more_available`, `next_max_id`

```python
feed = ig.feed.get_tag_feed("fashion")
```

---

### get_location_feed(location_id, max_id=None)

Get posts by location.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `location_id` | `int\|str` | ✅ | — | Location PK |
| `max_id` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict` with `items`, `more_available`, `next_max_id`

---

### get_reels_feed(max_id=None)

Get trending reels (Explore reels tab).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `max_id` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict`

---

## Pagination Example

All feed methods support cursor-based pagination:

```python
all_posts = []
cursor = None

for _ in range(3):  # Grab 3 pages
    res = ig.feed.get_user_feed(TARGET_PK, max_id=cursor)
    all_posts.extend(res.get("items", []))
    
    if not res.get("more_available"):
        break
    cursor = res.get("next_max_id")

print(f"Total: {len(all_posts)} posts")
```

# SearchAPI

> `ig.search` — Search users, hashtags, places, and explore Instagram content.

## Quick Example

```python
from instaharvest_v2 import Instagram

ig = Instagram.from_env()

# Unified search (users + hashtags + places)
results = ig.search.top_search("fashion")
for user in results.get("users", []):
    print(f"@{user.get('username')}")
```

## Methods

### top_search(query, context="blended")

Unified search across users, hashtags, and places.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `str` | ✅ | — | Search query |
| `context` | `str` | ❌ | `"blended"` | `"blended"`, `"user"`, `"hashtag"`, `"place"` |

**Returns:** `dict` with `users`, `hashtags`, `places` lists

---

### search_users(query)

Search users only (returns parsed `UserShort` models).

| Param | Type | Required | Description |
|---|---|---|---|
| `query` | `str` | ✅ | Username or name |

**Returns:** `list[UserShort]`

```python
users = ig.search.search_users("crist")
for u in users:
    print(f"@{u.username} — {u.full_name}")
```

---

### search_hashtags(query)

Search hashtags.

| Param | Type | Required | Description |
|---|---|---|---|
| `query` | `str` | ✅ | Hashtag name (without #) |

**Returns:** `list[dict]` — matching hashtags with media counts

---

### search_places(query, lat=None, lng=None)

Search locations/places.

| Param | Type | Required | Description |
|---|---|---|---|
| `query` | `str` | ✅ | Place name |
| `lat` | `float` | ❌ | Latitude hint |
| `lng` | `float` | ❌ | Longitude hint |

**Returns:** `dict` with venues list

---

### hashtag_search(hashtag, max_pages=1, next_max_id=None, rank_token=None, delay=2.0)

Search posts by hashtag with full pagination support. Returns structured results with parsed `Media` and `UserShort` models.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `hashtag` | `str` | ✅ | — | Hashtag name |
| `max_pages` | `int` | ❌ | 1 | Pages to fetch |
| `next_max_id` | `str` | ❌ | `None` | Continue from cursor |
| `rank_token` | `str` | ❌ | `None` | From previous result |
| `delay` | `float` | ❌ | 2.0 | Seconds between pages |

**Returns:** `HashtagSearchResult` with `posts`, `users`, `has_more`, `next_max_id`, `rank_token`

```python
result = ig.search.hashtag_search("#fashion", max_pages=3)
for post in result.posts:
    print(f"@{post.user.username}: {post.like_count} likes")

# Continue pagination
if result.has_more:
    more = ig.search.hashtag_search(
        "#fashion",
        next_max_id=result.next_max_id,
        rank_token=result.rank_token,
    )
```

---

### web_search(query, enable_metadata=True)

Raw web SERP search via `/fbsearch/web/top_serp/`.

**Returns:** `dict` — raw API response

---

### web_search_posts(hashtag)

Get top posts by hashtag (parsed flat dicts).

**Returns:** `list[dict]`

---

### explore()

Get explore page content.

**Returns:** `dict` — explore posts and clusters

```python
explore = ig.search.explore()
```

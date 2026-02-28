# HashtagsAPI

> `ig.hashtags` — Hashtag info, posts, follow/unfollow, search with pagination, related tags.

## Quick Example

```python
from instaharvest_v2 import Instagram

ig = Instagram.from_env()

# Get hashtag info
info = ig.hashtags.get_info("fashion")
print(f"#{info.get('name')}: {info.get('media_count'):,} posts")

# Search with pagination
result = ig.hashtags.search_posts("#fashion", max_pages=3)
for post in result.posts:
    print(f"@{post.user.username}: {post.like_count} likes")
```

## Methods

### get_info(hashtag)

Get hashtag metadata (post count, follower count).

| Param | Type | Required | Description |
|---|---|---|---|
| `hashtag` | `str` | ✅ | Hashtag name (without #) |

**Returns:** `dict` — name, media_count, follow_status, etc.

---

### get_posts(hashtag)

Get top + recent posts (raw sections format).

| Param | Type | Required | Description |
|---|---|---|---|
| `hashtag` | `str` | ✅ | Hashtag name |

**Returns:** `dict` — sections data

---

### search_posts(hashtag, max_pages=1, next_max_id=None, rank_token=None, delay=2.0)

Search posts by hashtag with **full pagination** support. This is the most powerful hashtag search method — returns parsed `Media` and `UserShort` models.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `hashtag` | `str` | ✅ | — | Hashtag name (#fashion or fashion) |
| `max_pages` | `int` | ❌ | 1 | Pages to load |
| `next_max_id` | `str` | ❌ | `None` | Continue from cursor |
| `rank_token` | `str` | ❌ | `None` | From previous result |
| `delay` | `float` | ❌ | 2.0 | Wait between pages |

**Returns:** `HashtagSearchResult` with `posts`, `users`, `has_more`, `next_max_id`, `rank_token`

```python
result = ig.hashtags.search_posts("#programming", max_pages=5)

for post in result.posts:
    print(f"@{post.user.username}: ❤️{post.like_count}")

# Paginate
if result.has_more:
    more = ig.hashtags.search_posts(
        "#programming",
        next_max_id=result.next_max_id,
        rank_token=result.rank_token,
    )
    result = result.merge(more)  # Combine results
```

---

### follow(hashtag)

Follow a hashtag.

---

### unfollow(hashtag)

Unfollow a hashtag.

---

### get_related(hashtag)

Get related/similar hashtags.

| Param | Type | Required | Description |
|---|---|---|---|
| `hashtag` | `str` | ✅ | Hashtag name |

**Returns:** `list[dict]` — similar hashtags

```python
related = ig.hashtags.get_related("fashion")
for tag in related:
    print(f"#{tag.get('name')}: {tag.get('media_count'):,} posts")
```

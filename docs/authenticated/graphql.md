# GraphQLAPI

> `ig.graphql` — Direct access to Instagram's GraphQL endpoint for advanced queries with full pagination.

GraphQL supports two transport modes:

- **Legacy** `query_hash` (GET) — still works for some queries
- **Modern** `doc_id` (POST) — required for newer endpoints, richer data

## Quick Example

```python
from instaapi import Instagram

ig = Instagram.from_env()

# Get followers with pagination
data = ig.graphql.get_followers(173560420, count=50)
for user in data["users"]:
    print(f"@{user['username']}")

if data["has_next"]:
    page2 = ig.graphql.get_followers(173560420, after=data["end_cursor"])
```

## Followers & Following

### get_followers(user_id, count=50, after=None)

Get followers with pagination.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `user_id` | `int\|str` | ✅ | — | User PK |
| `count` | `int` | ❌ | 50 | Per page (max ~50) |
| `after` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict` with `count`, `users`, `has_next`, `end_cursor`

---

### get_all_followers(user_id, max_count=5000)

Get ALL followers with auto-pagination.

**Returns:** `list[dict]` — all followers

---

### get_following(user_id, count=50, after=None)

Get following list with pagination.

**Returns:** `dict` with `count`, `users`, `has_next`, `end_cursor`

---

### get_all_following(user_id, max_count=5000)

Get ALL following with auto-pagination.

**Returns:** `list[dict]`

---

## Posts

### get_user_posts(user_id, count=12, after=None)

Get user posts via legacy `query_hash` (GET).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `user_id` | `int\|str` | ✅ | — | User PK |
| `count` | `int` | ❌ | 12 | Per page (max ~50) |
| `after` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict` with `count`, `posts`, `has_next`, `end_cursor`

---

### get_user_posts_v2(username, count=12, after=None)

Get posts via modern `doc_id` (richer data).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Username (not user_id!) |
| `count` | `int` | ❌ | 12 | Per page |
| `after` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict` with `count`, `posts`, `has_next`, `end_cursor`

---

### get_all_user_posts_v2(username, max_count=100)

Get ALL posts via doc_id with auto-pagination.

**Returns:** `list[dict]` — all posts with full metadata

```python
all_posts = ig.graphql.get_all_user_posts_v2("nike", max_count=200)
print(f"Got {len(all_posts)} posts")
```

---

### get_tagged_posts(user_id, count=12, after=None)

Get posts where the user is tagged ("Photos of You").

**Returns:** `dict` with `count`, `posts`, `has_next`, `end_cursor`

---

## Media Details

### get_media_detail(shortcode)

Get full media info via doc_id POST.

| Param | Type | Required | Description |
|---|---|---|---|
| `shortcode` | `str` | ✅ | Post shortcode from URL |

**Returns:** `dict` — complete media data

---

### get_comments_v2(media_id, count=20, after=None)

Get threaded comments via doc_id POST.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `media_id` | `int\|str` | ✅ | — | Media PK |
| `count` | `int` | ❌ | 20 | Per page |
| `after` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict` with `comments`, `has_next`, `end_cursor`, `count`

---

### get_likers_v2(shortcode, count=50, after=None)

Get post likers via doc_id POST.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `shortcode` | `str` | ✅ | — | Post shortcode |
| `count` | `int` | ❌ | 50 | Per page |
| `after` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict` with `users`, `count`, `has_next`, `end_cursor`

---

## Raw Queries

### raw_query(query_hash, variables)

Send any custom GraphQL query via legacy GET transport.

| Param | Type | Required | Description |
|---|---|---|---|
| `query_hash` | `str` | ✅ | GraphQL query hash |
| `variables` | `dict` | ✅ | Query variables |

---

### raw_doc_query(doc_id, variables, friendly_name="")

Send any custom GraphQL query via modern doc_id POST.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `doc_id` | `str` | ✅ | — | Document ID |
| `variables` | `dict` | ✅ | — | Query variables |
| `friendly_name` | `str` | ❌ | `""` | API request name |

```python
# Custom query example
result = ig.graphql.raw_doc_query(
    doc_id="9496468463735694",
    variables={"username": "nike"},
    friendly_name="ProfileInfoQuery",
)
```

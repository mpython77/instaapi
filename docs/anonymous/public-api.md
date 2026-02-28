# PublicAPI

High-level synchronous interface for anonymous Instagram data access.

```python
from instaharvest_v2 import Instagram

ig = Instagram.anonymous()
# or with unlimited speed:
ig = Instagram.anonymous(unlimited=True)
```

---

## get_profile(username)

Get public profile data.

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Instagram username (without @) |

**Returns:** `dict` or `None`

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `user_id` | `str` | Unique user ID |
| `username` | `str` | Username |
| `full_name` | `str` | Display name |
| `biography` | `str` | Bio text |
| `followers` | `int` | Follower count |
| `following` | `int` | Following count |
| `posts_count` | `int` | Total posts |
| `is_private` | `bool` | Private account |
| `is_verified` | `bool` | Verified badge |
| `is_business` | `bool` | Business account |
| `category` | `str` | Business category |
| `profile_pic_url` | `str` | Profile picture |
| `profile_pic_url_hd` | `str` | HD picture |
| `external_url` | `str` | Website |
| `bio_links` | `list` | Links in bio |
| `recent_posts` | `list` | Latest posts |

```python
profile = ig.public.get_profile("cristiano")
if profile:
    print(f"@{profile['username']}: {profile['followers']:,}")
```

---

## get_user_id(username)

Get user ID from username.

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Instagram username |

**Returns:** `int` or `None`

```python
user_id = ig.public.get_user_id("cristiano")
# 173560420
```

---

## get_profile_pic_url(username)

Get HD profile picture URL.

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Instagram username |

**Returns:** `str` or `None`

```python
url = ig.public.get_profile_pic_url("cristiano")
print(url)
```

---

## get_posts(username, max_count=12)

Get user's latest public posts.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Instagram username |
| `max_count` | `int` | ❌ | 12 | Maximum posts to return |

**Returns:** `list[dict]`

**Post fields:**

| Field | Type | Description |
|---|---|---|
| `pk` | `str` | Post ID |
| `shortcode` | `str` | URL shortcode |
| `media_type` | `str` | `GraphImage`, `GraphVideo`, `GraphSidecar` |
| `display_url` | `str` | Main image URL |
| `is_video` | `bool` | Is video post |
| `likes` | `int` | Like count |
| `comments` | `int` | Comment count |
| `caption` | `str` | Caption text |
| `taken_at` | `int` | Unix timestamp |
| `video_url` | `str` | Video URL (if video) |
| `video_views` | `int` | Video view count |
| `carousel_media` | `list` | Carousel child items |

```python
posts = ig.public.get_posts("cristiano", max_count=5)
for post in posts:
    print(f"[{post['shortcode']}] ❤️{post['likes']:,}")
```

---

## get_post_by_url(url)

Get post data from Instagram URL.

| Param | Type | Required | Description |
|---|---|---|---|
| `url` | `str` | ✅ | Full Instagram URL |

**Returns:** `dict` or `None`

```python
post = ig.public.get_post_by_url("https://instagram.com/p/ABC123/")
post = ig.public.get_post_by_url("https://instagram.com/reel/XYZ789/")
```

---

## get_post_by_shortcode(shortcode)

Get post by shortcode.

| Param | Type | Required | Description |
|---|---|---|---|
| `shortcode` | `str` | ✅ | Post shortcode |

**Returns:** `dict` or `None`

```python
post = ig.public.get_post_by_shortcode("ABC123")
```

---

## search(query, context="blended")

Search Instagram users, hashtags, and places.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `str` | ✅ | — | Search query |
| `context` | `str` | ❌ | `"blended"` | `"blended"`, `"user"`, `"hashtag"`, or `"place"` |

**Returns:** `dict` with keys `users`, `hashtags`, `places`

```python
results = ig.public.search("fashion")

for user in results["users"]:
    print(f"@{user['username']} — {user['follower_count']:,}")

for tag in results["hashtags"]:
    print(f"#{tag['name']} — {tag['media_count']:,} posts")
```

---

## get_feed(user_id, max_count=12, max_id=None)

Get user feed via mobile API with rich data.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `user_id` | `int\|str` | ✅ | — | User PK |
| `max_count` | `int` | ❌ | 12 | Max items |
| `max_id` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict` with `items`, `more_available`, `next_max_id`

```python
feed = ig.public.get_feed(173560420)  # cristiano's PK
for item in feed["items"]:
    print(f"❤️{item['likes']:,}  {item['caption'][:50]}")

# Pagination
if feed["more_available"]:
    page2 = ig.public.get_feed(173560420, max_id=feed["next_max_id"])
```

---

## get_all_posts(username, max_count=50)

Get maximum posts using combined strategies (Web API + mobile feed pagination).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Instagram username |
| `max_count` | `int` | ❌ | 50 | Maximum posts |

**Returns:** `list[dict]`

```python
posts = ig.public.get_all_posts("nike", max_count=50)
print(f"Got {len(posts)} posts")
```

---

## get_media(media_id)

Get single media details via mobile API.

| Param | Type | Required | Description |
|---|---|---|---|
| `media_id` | `int\|str` | ✅ | Media PK |

**Returns:** `dict` or `None`

```python
media = ig.public.get_media(3823732431648645952)
print(f"❤️{media['likes']:,}  💬{media['comments']}")
```

---

## get_reels(username, max_count=12)

Get user's reels.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Username |
| `max_count` | `int` | ❌ | 12 | Max reels |

**Returns:** `list[dict]`

```python
reels = ig.public.get_reels("nike")
for reel in reels:
    print(f"🎬 {reel['play_count']:,} views")
```

---

## get_comments(shortcode, max_count=24)

Get post comments.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `shortcode` | `str` | ✅ | — | Post shortcode |
| `max_count` | `int` | ❌ | 24 | Max comments |

**Returns:** `list[dict]`

```python
comments = ig.public.get_comments("ABC123")
for c in comments:
    print(f"@{c['username']}: {c['text'][:50]}")
```

---

## get_media_urls(shortcode)

Get all media URLs (images + videos) for a post. Supports carousels.

| Param | Type | Required | Description |
|---|---|---|---|
| `shortcode` | `str` | ✅ | Post shortcode |

**Returns:** `list[dict]` with `url`, `type`, `width`, `height`

```python
urls = ig.public.get_media_urls("ABC123")
for item in urls:
    print(f"{item['type']}: {item['url']}")
```

---

## get_hashtag_posts(hashtag, max_count=12)

Get posts by hashtag (GraphQL).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `hashtag` | `str` | ✅ | — | Hashtag (with or without #) |
| `max_count` | `int` | ❌ | 12 | Max posts |

**Returns:** `list[dict]`

```python
posts = ig.public.get_hashtag_posts("fashion", max_count=20)
```

---

## get_hashtag_posts_v2(hashtag, tab="recent", max_count=30)

Get hashtag posts via sections API (richer data).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `hashtag` | `str` | ✅ | — | Hashtag name |
| `tab` | `str` | ❌ | `"recent"` | `"recent"` or `"top"` |
| `max_count` | `int` | ❌ | 30 | Max posts |

**Returns:** `dict` with `tag_name`, `posts`, `media_count`, `more_available`

```python
result = ig.public.get_hashtag_posts_v2("fashion")
print(f"#{result['tag_name']}: {result['media_count']:,} total")
```

---

## get_location_posts(location_id, tab="recent", max_count=30)

Get posts from a location.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `location_id` | `int\|str` | ✅ | — | Location PK |
| `tab` | `str` | ❌ | `"recent"` | `"recent"` or `"ranked"` |
| `max_count` | `int` | ❌ | 30 | Max posts |

**Returns:** `dict` with `location`, `posts`, `media_count`, `more_available`

```python
result = ig.public.get_location_posts(213385402)
print(f"{result['location']['name']}: {len(result['posts'])} posts")
```

---

## get_similar_accounts(username)

Get similar/recommended accounts.

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Instagram username |

**Returns:** `list[dict]`

```python
similar = ig.public.get_similar_accounts("nike")
for acc in similar:
    print(f"@{acc['username']} — {acc['follower_count']:,}")
```

---

## get_highlights(username)

Get highlight tray (titles, covers, counts).

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Instagram username |

**Returns:** `list[dict]`

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Highlight ID |
| `title` | `str` | Highlight title |
| `media_count` | `int` | Number of items |
| `cover_url` | `str` | Cover image URL |

```python
highlights = ig.public.get_highlights("nike")
for h in highlights:
    print(f"📌 {h['title']} ({h['media_count']} items)")
```

---

## is_public(username)

Check if account is public.

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Instagram username |

**Returns:** `True` = public, `False` = private, `None` = not found

```python
if ig.public.is_public("nike"):
    print("Public account!")
```

---

## exists(username)

Check if username exists.

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Instagram username |

**Returns:** `bool`

```python
if ig.public.exists("cristiano"):
    print("Account exists!")
```

---

## request_count

Property — total anonymous requests made.

```python
print(f"Made {ig.public.request_count} requests so far")
```

---

## bulk_profiles(usernames, workers=10, callback=None)

Get multiple profiles in parallel (thread pool).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `usernames` | `list[str]` | ✅ | — | List of usernames |
| `workers` | `int` | ❌ | 10 | Thread pool size |
| `callback` | `callable` | ❌ | `None` | Progress callback `(username, profile)` |

**Returns:** `dict[str, dict]` — username → profile

```python
profiles = ig.public.bulk_profiles(["nike", "adidas", "puma"])
for username, profile in profiles.items():
    if profile:
        print(f"@{username}: {profile['followers']:,}")
```

---

## bulk_feeds(user_ids, max_count=12, workers=10, callback=None)

Get multiple feeds in parallel.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `user_ids` | `list[int\|str]` | ✅ | — | List of user PKs |
| `max_count` | `int` | ❌ | 12 | Posts per user |
| `workers` | `int` | ❌ | 10 | Thread pool size |
| `callback` | `callable` | ❌ | `None` | Progress callback |

**Returns:** `dict[int, dict]` — user_id → feed data

```python
feeds = ig.public.bulk_feeds([123, 456, 789])
for uid, feed in feeds.items():
    print(uid, len(feed.get("items", [])))
```

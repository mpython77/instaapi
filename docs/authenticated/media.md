# MediaAPI

> `ig.media` — Full media operations: get info, like, unlike, comment, save, get likers, manage comments.

## Quick Example

```python
from instaharvest_v2 import Instagram

ig = Instagram.from_env()

# Get details
media = ig.media.get_info(3124567890123)
print(f"Likes: {media.like_count}, Comments: {media.comment_count}")

# Like a post
ig.media.like(media.pk)
```

## Retrieving Media

### get_info(media_id)

Get basic media info (returns parsed `Media` model).

| Param | Type | Required | Description |
|---|---|---|---|
| `media_id` | `int\|str` | ✅ | Media PK (numeric) |

**Returns:** `Media` model

---

### get_full_info(media_id)

Get full structured post info with additional fields (plays, views, shares, music, top likers).

**Returns:** `dict`

---

### get_info_v2(media_id)

Most complete media info via REST v1 endpoint. Returns ALL available data including `has_liked`, `has_saved`, `comments_disabled`, coauthors, music, location.

**Returns:** `dict`

---

### get_info_v2_raw(media_id)

Raw API response from `/api/v1/media/{id}/info/` without parsing.

**Returns:** `dict`

---

### get_by_shortcode(shortcode)

Get media by URL shortcode (e.g. `"ABC123"` from `instagram.com/p/ABC123/`).

| Param | Type | Required | Description |
|---|---|---|---|
| `shortcode` | `str` | ✅ | URL shortcode |

**Returns:** `Media` model

```python
media = ig.media.get_by_shortcode("C-abcdefgh")
```

---

### get_by_url_v2(url)

Get full media info from an Instagram URL.

| Param | Type | Required | Description |
|---|---|---|---|
| `url` | `str` | ✅ | Instagram post/reel/tv URL |

**Returns:** `dict` (same as `get_info_v2`)

```python
info = ig.media.get_by_url_v2("https://www.instagram.com/p/ABC123/")
```

---

## Interactions

### like(media_id)

Like a media item.

**Returns:** API response `dict`

---

### unlike(media_id)

Remove a like.

---

### save(media_id)

Save/bookmark media.

---

### unsave(media_id)

Remove from bookmarks.

---

### web_like(media_id) / web_unlike(media_id)

Like/unlike via web endpoint (alternative method).

---

### web_save(media_id) / web_unsave(media_id)

Save/unsave via web endpoint.

---

## Comments

### comment(media_id, text)

Post a comment.

| Param | Type | Required | Description |
|---|---|---|---|
| `media_id` | `int\|str` | ✅ | Media PK |
| `text` | `str` | ✅ | Comment content |

**Returns:** `dict` with `id`, `from`, `text`, `created_time`, `status`

```python
result = ig.media.comment(3124567890123, "Great photo! 🔥")
print("Comment ID:", result["id"])
```

---

### web_comment(media_id, text)

Post comment via web endpoint (alternative, uses jazoest token).

---

### reply_to_comment(media_id, comment_id, text)

Reply to a specific comment.

| Param | Type | Required | Description |
|---|---|---|---|
| `media_id` | `int\|str` | ✅ | Media PK |
| `comment_id` | `int\|str` | ✅ | Parent comment PK |
| `text` | `str` | ✅ | Reply text |

---

### delete_comment(media_id, comment_id)

Delete a comment.

---

### like_comment(comment_id)

Like a comment.

---

### unlike_comment(comment_id)

Unlike a comment.

---

### pin_comment(media_id, comment_id)

Pin a comment to the top.

---

### unpin_comment(media_id, comment_id)

Unpin a comment.

---

### get_comments(media_id, can_support_threading=True, min_id=None)

Get post comments (raw API response with threading support).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `media_id` | `int\|str` | ✅ | — | Media PK |
| `can_support_threading` | `bool` | ❌ | `True` | Include threaded replies |
| `min_id` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict`

---

### get_comments_parsed(media_id, min_id=None)

Get structured comments with `Comment` models.

**Returns:** `dict` with `total_count`, `comments` (list of `Comment` models), `has_more`, `next_cursor`

---

### get_all_comments(media_id, max_pages=10, parsed=False)

Get all comments with automatic pagination.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `media_id` | `int\|str` | ✅ | — | Media PK |
| `max_pages` | `int` | ❌ | 10 | Maximum pages to fetch |
| `parsed` | `bool` | ❌ | `False` | Return `Comment` models if True |

**Returns:** `list` — all comments

---

### get_comment_replies(media_id, comment_id, min_id=None)

Get replies to a specific comment.

---

## Likers

### get_likers(media_id)

Get users who liked a post.

**Returns:** `list[UserShort]`

```python
likers = ig.media.get_likers(3124567890123)
for u in likers:
    print(f"@{u.username}")
```

---

## Post Management

### edit_caption(media_id, caption)

Edit a post's caption.

---

### disable_comments(media_id) / enable_comments(media_id)

Toggle comments on a post.

---

### report(media_id, reason=1)

Report a post (1=spam, 2=inappropriate).

---

## Models

### Media Model Reference

| Field | Type | Description |
|---|---|---|
| `pk` | `int` | Media PK |
| `shortcode` | `str` | Post shortcode |
| `media_type` | `int` | 1=Photo, 2=Video, 8=Carousel |
| `like_count` | `int` | Likes |
| `comment_count` | `int` | Comments |
| `caption` | `Caption` | Caption object containing `.text` |
| `taken_at` | `datetime` | Post datetime |
| `image_versions` | `list` | Image resolution candidates |
| `video_url` | `str` | URL to video mp4 |
| `carousel_media` | `list` | Child models if sidecar (carousel) |
| `usertags` | `list` | Tagged users |
| `location` | `Location` | Geotag |

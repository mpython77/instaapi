# StoriesAPI

> `ig.stories` — View, interact, and manage Instagram Stories and Highlights.

## Quick Example

```python
from instaapi import Instagram

ig = Instagram.from_env()

# Story tray (who has stories)
tray = ig.stories.get_tray_parsed()
for user in tray:
    print(f"@{user['username']} — {user['stories_count']} stories")

# Get user's stories (parsed)
stories = ig.stories.get_stories_parsed(173560420)
for item in stories["items"]:
    print(f"[{item['type']}] {item['taken_at']}")
```

## Viewing Stories

### get_reels_tray()

Get the story ring — list of users who currently have active stories.

**Returns:** `dict` with `tray` list and `story_ranking_token`

---

### get_tray_parsed()

Get story tray in structured format showing who has stories and how many.

**Returns:** `list[dict]` — each has `username`, `pk`, `full_name`, `is_verified`, `stories_count`, `has_besties_media`, `latest_reel_media`

```python
tray = ig.stories.get_tray_parsed()
for user in tray:
    print(f"@{user['username']} has {user['stories_count']} stories")
```

---

### get_user_stories(user_id)

Get all current stories for a specific user (raw API response).

| Param | Type | Required | Description |
|---|---|---|---|
| `user_id` | `int\|str` | ✅ | User PK |

**Returns:** `dict` with `reel` containing `user` and `items` list

---

### get_stories_parsed(user_id)

Get user stories fully parsed — stickers, tags, locations, hashtags, music all extracted.

| Param | Type | Required | Description |
|---|---|---|---|
| `user_id` | `int\|str` | ✅ | User PK |

**Returns:** `dict` with:

| Field | Type | Description |
|---|---|---|
| `user` | `dict` | `username`, `pk`, `full_name`, `is_verified` |
| `items` | `list` | Each item has: `pk`, `type` (photo/video), `taken_at`, `expiring_at`, `url`, `video_url`, `mentions`, `hashtags`, `locations`, `links`, `polls`, `questions`, `quizzes`, `sliders`, `countdowns`, `music`, `repost`, `viewer_count` |

```python
stories = ig.stories.get_stories_parsed(173560420)
for item in stories["items"]:
    if item["mentions"]:
        print(f"Mentions: {item['mentions']}")
    if item["music"]:
        print(f"Music: {item['music']['title']} by {item['music']['artist']}")
```

---

## Story Interactions

### mark_seen(items)

Mark stories as viewed.

| Param | Type | Required | Description |
|---|---|---|---|
| `items` | `list[dict]` | ✅ | Each: `{"media_id", "taken_at", "user_id"}` |

---

### get_viewers(story_id)

Get list of who viewed your story.

| Param | Type | Required | Description |
|---|---|---|---|
| `story_id` | `int\|str` | ✅ | Story media PK |

**Returns:** `list` — viewer users

---

### vote_poll(story_id, poll_id, vote=0)

Vote on a poll sticker.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `story_id` | `int\|str` | ✅ | — | Story PK |
| `poll_id` | `int\|str` | ✅ | — | Poll sticker ID |
| `vote` | `int` | ❌ | 0 | 0 or 1 |

---

### answer_question(story_id, question_id, answer)

Reply to a question sticker.

| Param | Type | Required | Description |
|---|---|---|---|
| `story_id` | `int\|str` | ✅ | Story PK |
| `question_id` | `int\|str` | ✅ | Question sticker ID |
| `answer` | `str` | ✅ | Reply text |

---

### vote_slider(story_id, slider_id, vote)

Vote on an emoji slider sticker.

| Param | Type | Required | Description |
|---|---|---|---|
| `story_id` | `int\|str` | ✅ | Story PK |
| `slider_id` | `int\|str` | ✅ | Slider sticker ID |
| `vote` | `float` | ✅ | Value between 0.0 and 1.0 |

---

### answer_quiz(story_id, quiz_id, answer)

Answer a quiz sticker.

| Param | Type | Required | Description |
|---|---|---|---|
| `story_id` | `int\|str` | ✅ | Story PK |
| `quiz_id` | `int\|str` | ✅ | Quiz sticker ID |
| `answer` | `int` | ✅ | Answer index (0, 1, 2, ...) |

---

## Highlights

### get_highlights_tray(user_id)

Get raw highlight tray for a user.

**Returns:** `dict` with `tray` list (id, title, media_count, cover_media)

---

### get_highlights_parsed(user_id)

Get structured highlights list.

**Returns:** `list[dict]` — each has `id`, `title`, `media_count`, `cover_url`, `created_at`, `updated_at`, `is_pinned`

```python
highlights = ig.stories.get_highlights_parsed(173560420)
for h in highlights:
    print(f"📌 {h['title']} ({h['media_count']} items)")
```

---

### get_highlight_items(highlight_id)

Get all items inside a specific highlight.

| Param | Type | Required | Description |
|---|---|---|---|
| `highlight_id` | `str` | ✅ | e.g. `"highlight:17889448593291353"` |

**Returns:** `dict` — reel data with items

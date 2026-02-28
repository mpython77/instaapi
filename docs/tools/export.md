# ExportAPI

> `ig.export` — Export followers, following, hashtag users, post likers/commenters to CSV/JSON with powerful filtering.

## Quick Example

```python
ig = Instagram.from_env()

# Export followers to CSV
ig.export.followers_to_csv("nike", "nike_followers.csv", max_count=500)

# Export with filters
from instaharvest_v2.api.export import ExportFilter

filters = ExportFilter(min_followers=100, is_business=True)
ig.export.followers_to_csv("nike", "filtered.csv", filters=filters)
```

---

## Methods

### followers_to_csv(username, output_path, max_count=0, filters=None, enrich=False, on_progress=None)

Export followers to CSV.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Target username |
| `output_path` | `str` | ✅ | — | CSV file path |
| `max_count` | `int` | ❌ | 0 | Max followers (0 = all) |
| `filters` | `ExportFilter` | ❌ | `None` | User filters |
| `enrich` | `bool` | ❌ | `False` | Fetch full profile for each user |
| `on_progress` | `callable` | ❌ | `None` | Callback `(exported, total)` |

**Returns:** `dict` with `{exported, filtered_out, total_fetched, file}`

---

### following_to_csv(username, output_path, max_count=0, filters=None, enrich=False, on_progress=None)

Export following to CSV. Same parameters as `followers_to_csv`.

---

### hashtag_users(tag, output_path, count=100, section="recent", filters=None, on_progress=None)

Export users who posted with a hashtag.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `tag` | `str` | ✅ | — | Hashtag (without #) |
| `output_path` | `str` | ✅ | — | CSV output path |
| `count` | `int` | ❌ | 100 | Max users to collect |
| `section` | `str` | ❌ | `"recent"` | `"recent"` or `"top"` |
| `filters` | `ExportFilter` | ❌ | `None` | User filters |
| `on_progress` | `callable` | ❌ | `None` | Progress callback |

**Returns:** `dict` with `{exported, filtered_out, total_fetched, file}`

---

### post_likers(media_id, output_path, filters=None)

Export post likers to CSV.

| Param | Type | Required | Description |
|---|---|---|---|
| `media_id` | `int\|str` | ✅ | Media PK |
| `output_path` | `str` | ✅ | CSV output path |
| `filters` | `ExportFilter` | ❌ | User filters |

**Returns:** `dict` with `{exported, filtered_out, total_fetched, file}`

---

### post_commenters(media_id, output_path, max_pages=10, filters=None)

Export post commenters to CSV.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `media_id` | `int\|str` | ✅ | — | Media PK |
| `output_path` | `str` | ✅ | — | CSV output path |
| `max_pages` | `int` | ❌ | 10 | Max comment pages |
| `filters` | `ExportFilter` | ❌ | `None` | User filters |

**Returns:** `dict` with `{exported, filtered_out, total_fetched, file}`

---

### to_json(username, output_path, include_posts=True, include_followers_sample=0)

Export full profile data to JSON.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Instagram username |
| `output_path` | `str` | ✅ | — | JSON output path |
| `include_posts` | `bool` | ❌ | `True` | Include recent posts |
| `include_followers_sample` | `int` | ❌ | 0 | Followers to include (0 = none) |

**Returns:** `dict` with `{file, sections}`

---

## ExportFilter

Filter users during export.

```python
from instaharvest_v2.api.export import ExportFilter

filters = ExportFilter(
    min_followers=100,
    max_followers=50000,
    is_business=True,
    bio_keywords=["fashion", "style"],
    exclude_keywords=["spam"],
)

ig.export.followers_to_csv("nike", "filtered.csv", filters=filters)
```

| Param | Type | Default | Description |
|---|---|---|---|
| `min_followers` | `int` | 0 | Minimum follower count |
| `max_followers` | `int` | 0 | Maximum follower count (0 = no limit) |
| `min_following` | `int` | 0 | Minimum following count |
| `max_following` | `int` | 0 | Maximum following count |
| `min_posts` | `int` | 0 | Minimum post count |
| `is_private` | `bool\|None` | `None` | Filter by private status |
| `is_business` | `bool\|None` | `None` | Filter by business account |
| `is_verified` | `bool\|None` | `None` | Filter by verified badge |
| `has_profile_pic` | `bool\|None` | `None` | Filter by profile picture |
| `bio_keywords` | `list[str]` | `None` | Bio must contain any of these |
| `exclude_keywords` | `list[str]` | `None` | Exclude if bio contains any |
| `custom_filter` | `callable` | `None` | Custom `(user_dict) -> bool` |

## CSV Columns

Exported CSV files include these columns:

`username`, `full_name`, `user_id`, `followers`, `following`, `posts_count`, `is_private`, `is_verified`, `is_business`, `biography`, `external_url`, `profile_pic_url`

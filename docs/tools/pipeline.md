# PipelineAPI

> `ig.pipeline` — Stream Instagram data into SQLite databases or JSONL files with incremental updates and deduplication.

## Quick Example

```python
ig = Instagram.from_env()

# Export to SQLite
result = ig.pipeline.to_sqlite("cristiano", "data.db",
    include_posts=True,
    include_followers=True
)
print(f"Rows: {result['total_rows']}")
```

---

## Methods

### to_sqlite(username, db_path, include_posts=True, include_followers=False, include_following=False)

Stream profile data into a SQLite database.

| Param | Type | Default | Description |
|---|---|---|---|
| `username` | `str` | — | Target account |
| `db_path` | `str` | — | SQLite file path |
| `include_posts` | `bool` | True | Include posts |
| `include_followers` | `bool` | False | Include followers |
| `include_following` | `bool` | False | Include following |

**Tables created:**

| Table | Columns |
|-------|---------|
| `profiles` | pk, username, full_name, followers, following, media_count, bio, ... |
| `posts` | pk, shortcode, media_type, like_count, comment_count, caption, timestamp |
| `followers` | pk, username, full_name, is_private, is_verified |
| `following` | pk, username, full_name, is_private, is_verified |

---

### to_jsonl(username, file_path, include_posts=True, include_followers=False, max_posts=0)

Export data as JSONL (one JSON object per line).

```python
result = ig.pipeline.to_jsonl("nike", "nike_data.jsonl", max_posts=100)
# {"_type": "profile", "username": "nike", ...}
# {"_type": "post", "pk": "123", "like_count": 50000, ...}
```

**Returns:**

```python
{"lines_written": 101, "file_path": "nike_data.jsonl"}
```

---

## Incremental Updates

Running the pipeline again on the same database will update existing records and add new ones:

```python
# First run
ig.pipeline.to_sqlite("nike", "nike.db")

# Next day — only new posts added, profile updated
ig.pipeline.to_sqlite("nike", "nike.db")
```

---

## Async Version

```python
async with AsyncInstagram.from_env() as ig:
    await ig.pipeline.to_sqlite("cristiano", "data.db")
    await ig.pipeline.to_jsonl("nike", "nike.jsonl")
```

# BulkDownloadAPI

> `ig.bulk_download` — Download all posts, stories, and highlights from any account in organized folders.

## Quick Example

```python
ig = Instagram.from_env()

# Download everything
result = ig.bulk_download.everything("cristiano", output_dir="./downloads")
print(f"Downloaded: {result['downloaded']} files")
```

---

## Methods

### all_posts(username, output_dir, max_posts=0)

Download all posts (photos + videos).

| Param | Type | Default | Description |
|---|---|---|---|
| `username` | `str` | — | Target account |
| `output_dir` | `str` | — | Save directory |
| `max_posts` | `int` | 0 | Limit (0 = all) |

**Output structure:**

```
downloads/cristiano/
├── posts/
│   ├── 2026-02-27_ABC123.jpg
│   ├── 2026-02-26_DEF456.mp4
│   └── ...
```

---

### all_stories(username, output_dir)

Download current active stories.

### everything(username, output_dir)

Download posts + stories + highlights — everything.

**Returns:**

```python
{
    "username": "cristiano",
    "downloaded": 150,
    "skipped": 3,
    "failed": 0,
    "total_size_mb": 1240.5
}
```

---

## Resume Support

If a download is interrupted, re-running the same command will skip already downloaded files:

```python
# First run — downloads 100 files then interrupted
ig.bulk_download.all_posts("nike", "./downloads")

# Second run — skips existing, downloads only new
ig.bulk_download.all_posts("nike", "./downloads")
```

---

## Async Version

```python
async with AsyncInstagram.from_env(mode="fast") as ig:
    result = await ig.bulk_download.all_posts("cristiano", "./downloads")
```

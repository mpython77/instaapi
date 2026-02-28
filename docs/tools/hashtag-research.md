# HashtagResearchAPI

> `ig.hashtag_research` — Analyze hashtag difficulty, competition, related tags, and get smart suggestions for optimal reach.

## Quick Example

```python
ig = Instagram.from_env()

# Full hashtag analysis
analysis = ig.hashtag_research.analyze("python")
print(f"Difficulty: {analysis['difficulty']}")
print(f"Competition: {analysis['competition_score']}")
print(f"Media count: {analysis['media_count']:,}")
```

---

## Methods

### analyze(tag)

Full analysis of a single hashtag — difficulty, competition, engagement, and related tags.

| Param | Type | Required | Description |
|---|---|---|---|
| `tag` | `str` | ✅ | Hashtag to analyze |

**Returns:**

```python
{
    "tag": "python",
    "media_count": 12500000,
    "difficulty": "hard",          # very_easy/easy/medium/hard/very_hard
    "competition_score": 0.85,     # 0.0 — 1.0
    "audience_size": "500K-1M",
    "engagement": {"avg_likes": 450, "avg_comments": 12, "score": 7.2},
    "related_tags": [{"name": "coding", "count": 3}, ...],
    "top_posts": [...]
}
```

---

### suggest(seed_tag, count=20, mix="balanced")

Smart hashtag suggestions based on a seed tag.

| Param | Type | Default | Description |
|---|---|---|---|
| `seed_tag` | `str` | — | Starting hashtag |
| `count` | `int` | 20 | Number of suggestions |
| `mix` | `str` | "balanced" | Strategy: "popular", "niche", "balanced" |

```python
suggestions = ig.hashtag_research.suggest("travel", count=15, mix="balanced")
for tag in suggestions:
    print(f"#{tag['name']} — {tag['difficulty']}")
```

---

### related(tag, count=30)

Find related hashtags from top posts.

### compare(tags)

Compare multiple hashtags side by side.

```python
result = ig.hashtag_research.compare(["python", "javascript", "rust"])
for tag in result["tags"]:
    print(f"#{tag['name']}: {tag['media_count']:,} posts, {tag['difficulty']}")
```

---

## Async Version

```python
async with AsyncInstagram.from_env() as ig:
    analysis = await ig.hashtag_research.analyze("python")
    suggestions = await ig.hashtag_research.suggest("coding", count=20)
```

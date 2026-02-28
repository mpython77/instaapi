# AnalyticsAPI

> `ig.analytics` — Generate engagement reports, find best posting times, analyze content performance, and compare accounts.

## Quick Example

```python
ig = Instagram.from_env()

# Engagement rate analysis
report = ig.analytics.engagement_rate("cristiano", post_count=20)

print(f"Engagement Rate: {report['engagement_rate']:.2f}%")
print(f"Average Likes: {report['avg_likes']:,.0f}")
print(f"Rating: {report['rating']}")
```

---

## Methods

### engagement_rate(username, post_count=12)

Calculate engagement rate from recent posts.

**Formula:** `(avg_likes + avg_comments) / followers × 100`

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Target username |
| `post_count` | `int` | ❌ | 12 | Posts to analyze |

**Returns:** `dict`

```python
{
    "username": "cristiano",
    "followers": 600000000,
    "posts_analyzed": 12,
    "total_likes": 120000000,
    "total_comments": 500000,
    "avg_likes": 10000000.0,
    "avg_comments": 41666.6,
    "engagement_rate": 1.67,
    "rating": "good"  # excellent/good/average/low
}
```

---

### best_posting_times(username, post_count=30)

Analyze post timestamps to find optimal posting times.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Target username |
| `post_count` | `int` | ❌ | 30 | Posts to analyze |

**Returns:** `dict` with `best_hours`, `best_days`, `daily_breakdown`

```python
times = ig.analytics.best_posting_times("nike", post_count=30)
print("Best hours:", times["best_hours"])
print("Best days:", times["best_days"])
```

---

### content_analysis(username, post_count=20)

Analyze content performance by type, hashtags, and caption length.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Target username |
| `post_count` | `int` | ❌ | 20 | Posts to analyze |

**Returns:** `dict` with `by_type`, `caption_length_impact`, `top_hashtags`, `posting_frequency`

```python
analysis = ig.analytics.content_analysis("nike")
for media_type, stats in analysis["by_type"].items():
    print(f"{media_type}: avg {stats['avg_likes']:,.0f} likes")
```

---

### profile_summary(username, post_count=12)

Complete profile analytics summary — combines engagement, timing, and content analysis.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Target username |
| `post_count` | `int` | ❌ | 12 | Posts to analyze |

**Returns:** `dict` — combined engagement, timing, content, and profile data

```python
summary = ig.analytics.profile_summary("cristiano")
print(summary["engagement"]["engagement_rate"])
print(summary["timing"]["best_hours"])
```

---

### compare(usernames, post_count=12)

Compare multiple accounts side by side.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `usernames` | `list[str]` | ✅ | — | Accounts to compare |
| `post_count` | `int` | ❌ | 12 | Posts per account |

**Returns:** `dict` with `accounts`, `rankings`, `winner`

```python
result = ig.analytics.compare(["nike", "adidas", "puma"])
print(f"Winner: @{result['winner']}")
for acc in result["accounts"]:
    print(f"  @{acc['username']}: {acc['engagement_rate']:.2f}%")
```

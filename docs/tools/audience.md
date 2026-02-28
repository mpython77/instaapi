# AudienceAPI

> `ig.audience` — Find lookalike audiences, analyze audience overlap, and get audience insights.

## Quick Example

```python
ig = Instagram.from_env()

# Find users similar to a competitor's audience
lookalike = ig.audience.find_lookalike("competitor", count=50)
for user in lookalike:
    print(f"@{user['username']} — score: {user['relevance_score']}")
```

---

## Methods

### find_lookalike(source_username, count=50)

Find users similar to a source account's audience.

| Param | Type | Default | Description |
|---|---|---|---|
| `source_username` | `str` | — | Source account |
| `count` | `int` | 50 | Number of results |

**Returns:** `list[dict]` — sorted by relevance score

```python
[
    {"username": "user1", "relevance_score": 0.92, "followers": 5000, "is_verified": False},
    {"username": "user2", "relevance_score": 0.87, "followers": 12000, "is_verified": True},
    ...
]
```

---

### overlap(account_a, account_b)

Analyze audience overlap between two accounts.

```python
result = ig.audience.overlap("nike", "adidas")
print(f"Overlap: {result['overlap_percentage']:.1f}%")
print(f"Shared followers: {result['shared_count']:,}")
```

---

### insights(username)

Get detailed audience insights for an account.

```python
insights = ig.audience.insights("my_account")
print(f"Quality: {insights['quality_score']}")
print(f"Bot ratio: {insights['bot_ratio']:.1%}")
print(f"Active ratio: {insights['active_ratio']:.1%}")
```

---

## Async Version

```python
async with AsyncInstagram.from_env() as ig:
    lookalike = await ig.audience.find_lookalike("competitor", count=100)
    overlap = await ig.audience.overlap("nike", "adidas")
```

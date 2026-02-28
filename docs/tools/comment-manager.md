# CommentManagerAPI

> `ig.comment_manager` — Filter comments, auto-reply, delete spam, and analyze sentiment.

## Quick Example

```python
ig = Instagram.from_env()

# Get and analyze comments
comments = ig.comment_manager.get_comments(media_pk, sort="top")
sentiment = ig.comment_manager.sentiment(media_pk)
print(f"Positive: {sentiment['positive']}%, Negative: {sentiment['negative']}%")
```

---

## Methods

### get_comments(media_pk, sort="top", filter_spam=True)

Get filtered comments for a post.

| Param | Type | Default | Description |
|---|---|---|---|
| `media_pk` | `str/int` | — | Post media PK |
| `sort` | `str` | "top" | Sort: "top", "recent" |
| `filter_spam` | `bool` | True | Auto-filter spam |

---

### auto_reply(media_pk, keyword, reply)

Auto-reply to comments containing a keyword.

```python
ig.comment_manager.auto_reply(
    media_pk,
    keyword="price?",
    reply="Check our bio for pricing! 💰"
)
```

---

### delete_spam(media_pk)

Detect and delete spam comments.

```python
result = ig.comment_manager.delete_spam(media_pk)
print(f"Deleted {result['deleted']} spam comments")
```

**Spam detection includes:**

- "follow for follow" / "f4f" patterns
- Excessive emojis
- URL spam
- Money/promotion spam
- Repeated characters

---

### sentiment(media_pk)

Analyze comment sentiment distribution.

```python
result = ig.comment_manager.sentiment(media_pk)
# {
#     "total": 150,
#     "positive": 65,    # percentage
#     "negative": 10,
#     "neutral": 25,
#     "top_positive": [...],
#     "top_negative": [...]
# }
```

---

## Async Version

```python
async with AsyncInstagram.from_env() as ig:
    comments = await ig.comment_manager.get_comments(media_pk)
    sentiment = await ig.comment_manager.sentiment(media_pk)
    await ig.comment_manager.delete_spam(media_pk)
```

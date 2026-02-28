# ABTestAPI

> `ig.ab_test` — A/B test different captions, hashtags, and posting strategies to find what works best.

## Quick Example

```python
ig = Instagram.from_env()

# Create an A/B test
test = ig.ab_test.create("Caption Test", variants={
    "A": {"caption": "Short and sweet ✨"},
    "B": {"caption": "Detailed caption with storytelling and hashtags #test #content"},
})

# Record results after posts go live
ig.ab_test.record(test["id"], "A", likes=100, comments=20, saves=15)
ig.ab_test.record(test["id"], "B", likes=150, comments=30, saves=25)

# Get winner
result = ig.ab_test.results(test["id"])
print(f"Winner: Variant {result['winner']}")
print(f"Improvement: {result['improvement_pct']}%")
```

---

## Methods

### create(name, variants, metric="engagement")

Create a new A/B test.

| Param | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | — | Test name |
| `variants` | `dict` | — | Variant definitions |
| `metric` | `str` | "engagement" | "engagement", "likes", or "comments" |

---

### record(test_id, variant_name, media_id=None, likes=0, comments=0, reach=0, saves=0)

Record results for a variant.

---

### collect(test_id)

Auto-collect live engagement data from Instagram for all variants with recorded media IDs.

```python
ig.ab_test.collect(test["id"])  # Fetches current like/comment counts
```

---

### results(test_id)

Analyze results and determine the winner.

**Returns:**

```python
{
    "winner": "B",
    "scores": {"A": 120, "B": 180},
    "improvement_pct": 50.0,
    "metric": "engagement"
}
```

---

### list_tests(status="")

List all tests, optionally filtered by status.

### delete_test(test_id)

Delete a test permanently.

---

## Async Version

```python
async with AsyncInstagram.from_env() as ig:
    test = await ig.ab_test.create("Test", variants={"A": {}, "B": {}})
    await ig.ab_test.record(test["id"], "A", likes=100)
    result = await ig.ab_test.results(test["id"])
```

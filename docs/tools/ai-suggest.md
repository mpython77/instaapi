# AISuggestAPI

> `ig.ai_suggest` — AI-powered hashtag and caption suggester using built-in niche detection, keyword analysis, and trend awareness. No external API required.

## Quick Example

```python
ig = Instagram.from_env()

# Suggest hashtags from caption text
result = ig.ai_suggest.hashtags_from_caption(
    "Beautiful sunset at the beach 🌅",
    count=30,
)
print(f"Niche: {result['niche']} ({result['confidence']:.0%})")
print("Hashtags:", result["hashtags"])
```

---

## Methods

### hashtags_from_caption(caption, count=30, include_trending=True)

Suggest hashtags based on caption text. Analyzes keywords, detects niche, and creates an optimal mix.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `caption` | `str` | ✅ | — | Your post caption text |
| `count` | `int` | ❌ | 30 | Number of hashtags |
| `include_trending` | `bool` | ❌ | `True` | Include trending tags |

**Returns:** `dict` with `{hashtags, niche, confidence, breakdown}`

```python
result = ig.ai_suggest.hashtags_from_caption("Morning workout 💪")
# {
#     "hashtags": ["#fitness", "#workout", "#gym", ...],
#     "niche": "fitness",
#     "confidence": 0.85,
#     "breakdown": {"niche": 10, "universal": 5, "longtail": 15}
# }
```

---

### hashtags_for_profile(username, count=30)

Suggest hashtags based on a user's profile and content. Analyzes bio, recent posts, and existing hashtag usage.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `username` | `str` | ✅ | — | Target username |
| `count` | `int` | ❌ | 30 | Hashtags to suggest |

**Returns:** `dict` with `{hashtags, niche, already_using, new_suggestions}`

```python
result = ig.ai_suggest.hashtags_for_profile("nike")
print("Niche:", result["niche"])
print("Already using:", result["already_using"])
print("New suggestions:", result["new_suggestions"])
```

---

### caption_ideas(topic, style="casual", count=5)

Generate caption ideas from built-in templates.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `topic` | `str` | ✅ | — | Topic or keyword |
| `style` | `str` | ❌ | `"casual"` | Style: `inspirational`, `casual`, `professional`, `poetic`, `funny` |
| `count` | `int` | ❌ | 5 | Number of ideas |

**Returns:** `list[str]`

```python
ideas = ig.ai_suggest.caption_ideas("fitness", style="inspirational", count=3)
for idea in ideas:
    print(idea)
```

---

### optimal_set(topic, count=30)

Create an optimal hashtag set with balanced difficulty.

**Mix:** 30% easy + 40% medium + 20% hard + 10% very popular.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `topic` | `str` | ✅ | — | Topic or niche name |
| `count` | `int` | ❌ | 30 | Total hashtags |

**Returns:** `dict` with `{hashtags, difficulty_mix, topic}`

---

## Supported Niches

Built-in keyword databases cover these niches:

| Niche | Keywords |
|---|---|
| `fitness` | gym, workout, bodybuilding, yoga, running, ... |
| `travel` | wanderlust, explore, adventure, vacation, ... |
| `food` | foodie, recipe, cooking, chef, restaurant, ... |
| `fashion` | style, outfit, designer, streetwear, ... |
| `beauty` | makeup, skincare, cosmetics, glam, ... |
| `tech` | programming, coding, AI, startup, ... |
| `business` | entrepreneur, hustle, success, marketing, ... |
| `photography` | photo, camera, portrait, landscape, ... |
| `sports` | athlete, training, game, champion, ... |
| `pets` | dog, cat, puppy, kitten, animals, ... |
| `education` | learning, study, student, teacher, ... |

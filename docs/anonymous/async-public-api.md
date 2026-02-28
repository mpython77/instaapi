# AsyncPublicAPI

Async version of PublicAPI — same methods, true async I/O with `asyncio.gather` for parallel operations.

```python
import asyncio
from instaapi import AsyncInstagram

async def main():
    async with AsyncInstagram.anonymous(unlimited=True) as ig:
        profile = await ig.public.get_profile("cristiano")
        print(f"{profile['followers']:,}")

asyncio.run(main())
```

---

## All Methods

AsyncPublicAPI has **identical methods** to [PublicAPI](public-api.md), but all are `async` — use `await`.

| Method | Signature |
|---|---|
| `get_profile` | `await ig.public.get_profile(username)` |
| `get_user_id` | `await ig.public.get_user_id(username)` |
| `get_profile_pic_url` | `await ig.public.get_profile_pic_url(username)` |
| `get_posts` | `await ig.public.get_posts(username, max_count=12)` |
| `get_post_by_url` | `await ig.public.get_post_by_url(url)` |
| `get_post_by_shortcode` | `await ig.public.get_post_by_shortcode(shortcode)` |
| `get_media_urls` | `await ig.public.get_media_urls(shortcode)` |
| `get_comments` | `await ig.public.get_comments(shortcode)` |
| `get_hashtag_posts` | `await ig.public.get_hashtag_posts(hashtag)` |
| `search` | `await ig.public.search(query, context="blended")` |
| `get_feed` | `await ig.public.get_feed(user_id)` |
| `get_all_posts` | `await ig.public.get_all_posts(username)` |
| `get_media` | `await ig.public.get_media(media_id)` |
| `get_reels` | `await ig.public.get_reels(username)` |
| `get_hashtag_posts_v2` | `await ig.public.get_hashtag_posts_v2(hashtag, tab="recent")` |
| `get_location_posts` | `await ig.public.get_location_posts(location_id, tab="recent")` |
| `get_similar_accounts` | `await ig.public.get_similar_accounts(username)` |
| `get_highlights` | `await ig.public.get_highlights(username)` |
| `is_public` | `await ig.public.is_public(username)` |
| `exists` | `await ig.public.exists(username)` |
| `bulk_profiles` | `await ig.public.bulk_profiles(usernames, workers=10)` |
| `bulk_feeds` | `await ig.public.bulk_feeds(user_ids, workers=10)` |

---

## Parallel Operations

The real power of async — scrape many profiles simultaneously:

```python
async with AsyncInstagram.anonymous(unlimited=True) as ig:
    usernames = ["nike", "adidas", "puma", "gucci", "zara",
                 "hm", "uniqlo", "levis", "gap", "supreme"]

    # 10 profiles in parallel — ~3 seconds!
    tasks = [ig.public.get_profile(u) for u in usernames]
    profiles = await asyncio.gather(*tasks)

    for p in profiles:
        if p:
            print(f"@{p['username']}: {p['followers']:,}")
```

### Performance Comparison

| Method | 100 profiles |
|---|---|
| Sync (sequential) | ~300 seconds |
| Async (`gather`) | ~15 seconds |
| Async unlimited | **~10 seconds** |

---

## Bulk Profiles (Async)

```python
# Uses asyncio.gather internally
profiles = await ig.public.bulk_profiles(
    ["nike", "adidas", "puma", "gucci"],
    workers=10,
)

for username, profile in profiles.items():
    print(f"@{username}: {profile['followers']:,}")
```

---

## Context Manager

Always use `async with` for proper cleanup:

```python
# ✅ Good — auto-closes session
async with AsyncInstagram.anonymous() as ig:
    profile = await ig.public.get_profile("nike")

# ❌ Bad — session leak
ig = AsyncInstagram.anonymous()
profile = await ig.public.get_profile("nike")
# Forgot await ig.close()!
```

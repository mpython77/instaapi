# Bulk Operations

Scrape hundreds of profiles or feeds efficiently.

## Sync — ThreadPoolExecutor

```python
ig = Instagram.anonymous(unlimited=True)

profiles = ig.public.bulk_profiles(
    ["nike", "adidas", "puma", "gucci", "zara"],
    workers=5,
)

for username, profile in profiles.items():
    if profile:
        print(f"@{username}: {profile['followers']:,}")
    else:
        print(f"@{username}: not found")
```

## Async — asyncio.gather (Recommended)

```python
import asyncio
from instaapi import AsyncInstagram

async def scrape_profiles(usernames):
    async with AsyncInstagram.anonymous(unlimited=True) as ig:
        profiles = await ig.public.bulk_profiles(
            usernames,
            workers=20,
        )
        return profiles

# 200 profiles in ~15 seconds
usernames = open("usernames.txt").read().splitlines()
profiles = asyncio.run(scrape_profiles(usernames))
```

## Custom Parallel Pattern

```python
async def scrape_everything(username):
    """Get profile + posts + reels in one go."""
    async with AsyncInstagram.anonymous(unlimited=True) as ig:
        profile = await ig.public.get_profile(username)
        if not profile:
            return None

        user_id = profile.get("user_id")
        posts_task = ig.public.get_posts(username)
        reels_task = ig.public.get_reels(username)

        posts, reels = await asyncio.gather(posts_task, reels_task)

        return {
            "profile": profile,
            "posts": posts,
            "reels": reels,
        }
```

## Performance Tips

| Tip | Impact |
|---|---|
| Use `unlimited=True` | 20x faster (no delays) |
| Use `asyncio.gather` | Parallel instead of sequential |
| Add proxies | Avoid IP-based blocking |
| Limit `max_concurrent` | Prevent connection exhaustion |

!!! warning "Proxy recommended"
    When scraping 100+ profiles, add proxies to avoid IP blocks. Without proxies, Instagram may temporarily block your IP.

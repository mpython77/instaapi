# Async Guide

InstaAPI is built ground-up to support **True Python Async I/O** via the `curl_cffi` event loop integration. The async pattern makes large-scale scraping 50x to 100x faster than traditional synchronous models.

## Async vs Sync Comparison

```python
# Sync: Takes ~300 seconds (5 mins)
from instaharvest_v2 import Instagram

ig = Instagram.anonymous(unlimited=True)
for i in range(100):
   profile = ig.public.get_profile(f"user_{i}")
   print(profile)
```

**Versus True Async:**

```python
# Async: Takes ~10 seconds!
import asyncio
from instaharvest_v2 import AsyncInstagram

async def main():
    async with AsyncInstagram.anonymous(unlimited=True) as ig:
        # Create 100 parallel tasks
        tasks = [ig.public.get_profile(f"user_{i}") for i in range(100)]
        
        # Run them all concurrently
        profiles = await asyncio.gather(*tasks)
        
        for p in profiles:
            print(p)

asyncio.run(main())
```

## Setup Async Client

You must initiate the Async client inside an async context manager (`async with`) to properly handle connections, TLS contexts, and session loops.

```python
from instaharvest_v2 import AsyncInstagram

async def runner():
    # Regular safe speed mode
    async with AsyncInstagram.from_env() as ig:
        user = await ig.users.get_by_username("nasa")
        print(user.followers)
```

## Speed Modes in Async

You must pass the speed modes when instantiating the Async client. `AsyncRateLimiter` guarantees these limits automatically during `asyncio.gather()`.

```python
# Turbo Mode (Requires Proxies)
async with AsyncInstagram.from_env(mode="turbo") as ig:
    ig.add_proxies(["http://proxy1:80", "http://proxy2:80"])
    
    tasks = [ig.users.get_by_username(user) for user in HUGE_LIST]
    results = await asyncio.gather(*tasks)
```

See [Speed Modes](../core/speed-modes.md) for deeper details on parallel execution limits.

## Awaiting Endpoints

All endpoints that exist on `Instagram` exist on `AsyncInstagram` but require an `await`:

| Sync | Async |
|---|---|
| `ig.users.get_by_id(pk)` | `await ig.users.get_by_id(pk)` |
| `ig.media.like(pk)` | `await ig.media.like(pk)` |
| `ig.feed.user(pk)` | `await ig.feed.user(pk)` |
| `ig.public.search("query")` | `await ig.public.search("query")` |

## When NOT to use Async

While Async is magical for bulk reading (scraping, public data, fetching details), you should avoid huge concurrent write operations to prevent instant bans:

- Do not concurrently `like()` 100 pictures in 1 second.
- Do not concurrently `follow()` 50 users at once.

Async is designed to fetch gigabytes of data rapidly. Use it for read-heavy operations!

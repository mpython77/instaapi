# Speed Modes

InstaAPI provides 4 speed modes that control concurrency, delays, and rate limiting.

## Overview

| Mode | Concurrency | Delay | Rate/min | Burst | Use Case |
|---|---|---|---|---|---|
| 🐢 `safe` | 5 | 0.8-2.0s | 30 | 3 | Personal account, ban-proof |
| ⚡ `fast` | 15 | 0.2-0.8s | 60 | 8 | Moderate scraping |
| 🚀 `turbo` | 50 | 0.05-0.3s | 120 | 20 | Heavy scraping + proxies |
| ♾️ `unlimited` | 1000 | 0s | ∞ | 1000 | Anonymous bulk scraping |

## Usage

!!! note "Speed modes are async-only"
    The `mode` parameter is available only on `AsyncInstagram`. Sync `Instagram` always uses safe mode internally.

```python
import asyncio
from instaapi import AsyncInstagram

async def main():
    # Safe — default, ban-proof
    async with AsyncInstagram.from_env(mode="safe") as ig:
        user = await ig.users.get_by_username("nike")

    # Fast — 3x faster
    async with AsyncInstagram.from_env(mode="fast") as ig:
        user = await ig.users.get_by_username("nike")

    # Turbo — 10x faster with proxies
    async with AsyncInstagram.from_env(mode="turbo") as ig:
        ig.add_proxies(["http://p1:8080", "http://p2:8080"])
        user = await ig.users.get_by_username("nike")

    # Unlimited — anonymous, no limits
    async with AsyncInstagram.anonymous(unlimited=True) as ig:
        profile = await ig.public.get_profile("nike")

asyncio.run(main())
```

## SpeedMode Parameters

```python
from instaapi.speed_modes import SpeedMode

# Each mode is a frozen dataclass:
SpeedMode(
    name="safe",
    max_concurrency=5,          # Max parallel requests
    delay_range=(0.8, 2.0),     # Random delay between requests
    rate_per_minute=30,         # Token bucket rate limit
    burst_size=3,               # Fast requests before delay
    proxy_multiplier=3.0,       # +N concurrency per proxy
    error_backoff=2.0,          # Delay multiplier on errors
)
```

## Proxy Scaling

When proxies are added, concurrency scales automatically:

```
Effective concurrency = base + (proxy_count × multiplier)
```

| Mode | No proxy | 2 proxies | 5 proxies | 10 proxies |
|---|---|---|---|---|
| `safe` | 5 | 11 | 20 | 35 |
| `fast` | 15 | 25 | 40 | 65 |
| `turbo` | 50 | 70 | 100 | 150 |
| `unlimited` | 1000 | 1000 | 1000 | 1000 |

!!! note "Hard cap"
    Proxy-based scaling has a hard cap of 200 concurrent requests (except `unlimited`).

## Error Escalation

Speed modes include automatic error handling:

- **Rate limit (429)** → Escalation level +2
- **Challenge/Checkpoint** → Escalation level +3  
- **Other errors** → Escalation level +1
- **Success (30s streak)** → Escalation level -1

Each escalation level increases delays by 30%.

## Custom Mode

```python
from instaapi.speed_modes import SpeedMode

custom = SpeedMode(
    name="custom",
    max_concurrency=25,
    delay_range=(0.3, 1.0),
    rate_per_minute=45,
    burst_size=5,
    proxy_multiplier=4.0,
    error_backoff=1.8,
)
```

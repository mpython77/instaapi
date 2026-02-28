# Proxy Management

Built-in proxy rotation, health checking, and BrightData integration.

## Quick Setup

```python
from instaharvest_v2 import Instagram

ig = Instagram.from_env()

# Add single proxy
ig.add_proxy("http://user:pass@proxy.com:8080")

# Add multiple — enables rotation
ig.add_proxies([
    "http://user:pass@us1.proxy.com:8080",
    "http://user:pass@us2.proxy.com:8080",
    "http://user:pass@eu1.proxy.com:8080",
])
```

## Supported Formats

```python
# HTTP/HTTPS
"http://user:pass@proxy.com:8080"
"https://user:pass@proxy.com:8443"

# SOCKS5
"socks5://user:pass@proxy.com:1080"

# No auth
"http://proxy.com:8080"

# BrightData residential
"http://user:pass@brd.superproxy.io:22225"
```

## Rotation Strategies

```python
from instaharvest_v2.proxy_manager import ProxyManager, RotationStrategy

pm = ProxyManager(strategy=RotationStrategy.ROUND_ROBIN)
# or
pm = ProxyManager(strategy=RotationStrategy.RANDOM)
# or
pm = ProxyManager(strategy=RotationStrategy.WEIGHTED)
```

| Strategy | Description |
|---|---|
| `ROUND_ROBIN` | Sequential rotation through proxy list |
| `RANDOM` | Random proxy selection per request |
| `WEIGHTED` | Prioritize proxies with best success rate (default) |

## Health Checking

```python
# Start background health checker
ig.start_proxy_health(interval=300)  # Every 5 minutes

# Health checker will:
# - Test each proxy against Instagram
# - Remove proxies with >3 consecutive failures
# - Track response times and success rates
# - Auto-replace bad proxies

# Stop health checker
ig.stop_proxy_health()
```

### Config

| Setting | Default | Description |
|---|---|---|
| `PROXY_HEALTH_CHECK_INTERVAL` | 300s | Check frequency |
| `PROXY_MAX_FAILURES` | 3 | Remove after N failures |
| `PROXY_MIN_SCORE` | 0.3 | Replace below this score |

## Anonymous Scraping with Proxies

```python
from instaharvest_v2 import Instagram

ig = Instagram.anonymous(unlimited=True)
ig.add_proxies([
    "http://user:pass@proxy1.com:8080",
    "http://user:pass@proxy2.com:8080",
])

# Each request uses a different proxy + different TLS fingerprint
profile = ig.public.get_profile("cristiano")
```

## Async with Proxies

```python
from instaharvest_v2 import AsyncInstagram

async with AsyncInstagram.from_env(mode="turbo") as ig:
    ig.add_proxies(proxy_list)
    # Turbo + 5 proxies = 50 + (5 × 10) = 100 concurrent!
    
    tasks = [ig.public.get_profile(u) for u in usernames]
    results = await asyncio.gather(*tasks)
```

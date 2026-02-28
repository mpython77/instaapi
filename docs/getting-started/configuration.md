# Configuration

## Environment Variables (.env)

Create a `.env` file in your project root:

```env
# Required for authenticated access
SESSION_ID=61234567890%3AaBcDeFgHiJkLmN%3A12%3AAYf...
CSRF_TOKEN=abcdef1234567890
DS_USER_ID=12345678

# Optional — improve session stability
MID=YnR5AAE...
IG_DID=A1B2C3D4-E5F6-...
DATR=XyZ123...
USER_AGENT=Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)...
```

### How to get cookies

1. Open Instagram in Chrome
2. Press `F12` → **Application** → **Cookies** → `https://www.instagram.com`
3. Copy these values:

| Cookie Name | Maps to |
|---|---|
| `sessionid` | `SESSION_ID` |
| `csrftoken` | `CSRF_TOKEN` |
| `ds_user_id` | `DS_USER_ID` |
| `mid` | `MID` |
| `ig_did` | `IG_DID` |
| `datr` | `DATR` |

---

## Proxy Configuration

### Add proxies

```python
ig = Instagram.from_env()

# Single proxy
ig.add_proxy("http://user:pass@proxy.com:8080")

# Multiple proxies — enables rotation
ig.add_proxies([
    "http://user:pass@proxy1.com:8080",
    "http://user:pass@proxy2.com:8080",
    "http://user:pass@proxy3.com:8080",
])
```

### BrightData integration

```python
ig.add_proxy("http://user:pass@brd.superproxy.io:22225")
```

### Proxy health monitoring

```python
# Start background health checker (every 5 minutes)
ig.start_proxy_health(interval=300)

# Stop when done
ig.stop_proxy_health()
```

---

## Speed Modes (Async only)

```python
from instaharvest_v2 import AsyncInstagram

# Safe — default, ban-proof
ig = AsyncInstagram.from_env(mode="safe")

# Fast — balanced speed
ig = AsyncInstagram.from_env(mode="fast")

# Turbo — maximum speed, proxy required
ig = AsyncInstagram.from_env(mode="turbo")

# Unlimited — anonymous, no limits
ig = AsyncInstagram.anonymous(unlimited=True)
```

| Mode | Concurrency | Delay | Rate/min | Best for |
|---|---|---|---|---|
| `safe` | 5 | 0.8-2.0s | 30 | Personal account |
| `fast` | 15 | 0.2-0.8s | 60 | Moderate scraping |
| `turbo` | 50 | 0.05-0.3s | 120 | Heavy scraping + proxies |
| `unlimited` | 1000 | 0s | ∞ | Anonymous bulk scraping |

See [Speed Modes](../core/speed-modes.md) for details.

---

## Debug Mode

```python
# Enable verbose logging
ig = Instagram.from_env(debug=True)

# Log to file
ig = Instagram.from_env(debug=True, debug_log_file="debug.log")
```

---

## Retry Configuration

```python
from instaharvest_v2 import Instagram
from instaharvest_v2.retry import RetryConfig

ig = Instagram.from_env(
    retry=RetryConfig(
        max_retries=5,
        backoff_factor=2.0,
        backoff_max=120.0,
        jitter=True,
    )
)
```

| Param | Default | Description |
|---|---|---|
| `max_retries` | 3 | Maximum retry attempts |
| `backoff_factor` | 2.0 | Exponential backoff base |
| `backoff_max` | 60.0 | Maximum delay ceiling (seconds) |
| `jitter` | `True` | Add random ±30% jitter to delays |
| `retry_on` | `{RateLimitError, NetworkError, ChallengeRequired, CheckpointRequired}` | Exception types to retry on |

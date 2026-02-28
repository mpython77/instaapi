# Event System

InstaHarvest v2 includes a robust synchronous `EventEmitter` natively built into the `HttpClient`. Every major action, request, error, and proxy shift broadcasts a standardized event string that any plugin or script can hook into.

## Quick Example

```python
from instaharvest_v2 import Instagram
from instaharvest_v2.events import EventType

def on_request(data):
    print(f"📡 Making Request: {data.get('url')}")
    
def on_challenge(data):
    print(f"🚨 CHALLENGE ISSUED for session!")

ig = Instagram.from_env()

# Hook into events
ig.on("api_request", on_request)
ig.on(EventType.CHALLENGE_REQUIRED, on_challenge)
```

## Available Event Types

The `instaharvest_v2.events.EventType` ENUM defines all supported hooks:

| Event Type String | Fired When | Data Payload |
|---|---|---|
| `api_request` | Right before firing a curl_cffi HTTP request | `{"url", "method", "proxy"}` |
| `api_response` | Received raw response | `{"url", "status_code", "time_ms"}` |
| `api_error` | Critical network/parsing crash | `{"url", "error_msg"}` |
| `rate_limited` | Encounters 429 Too Many Requests | `{"url", "time_waited"}` |
| `challenge_required`| Account flagged for verification | `{"challenge_url", "type"}` |
| `proxy_rotated` | RateLimiter / health check skips a proxy | `{"old_proxy", "new_proxy"}` |
| `session_expired` | Auth session requires refresh (401/302) | `{"session_id"}` |
| `login_success` | Re-auth auto callback passed | `{"user_id"}` |

## Using the EventEmitter

You can listen (`.on`) and unregister (`.off`) anywhere on the main `ig` wrapper.

### Monitor Scraping Speed

```python
import time

class SpeedMonitor:
    def __init__(self, ig):
        self.count = 0
        self.start = time.time()
        ig.on(EventType.API_RESPONSE, self.tick)
        
    def tick(self, data):
        self.count += 1
        if self.count % 100 == 0:
            elapsed = time.time() - self.start
            print(f"Scraped 100 reqs in {elapsed:.2f}s")
            self.start = time.time()

ig = Instagram.anonymous(unlimited=True)
monitor = SpeedMonitor(ig)
```

### Removing Hooks

To safely disconnect an active event hook:

```python
ig.off(EventType.API_RESPONSE, monitor.tick)
```

# Smart Rotation

When doing heavy authenticated scraping, using a single account/IP will get you banned quickly. InstaAPI provides a `SmartRotation` system that automatically juggles multiple sessions and proxies to distribute load.

## Quick Example

```python
from instaapi import Instagram
from instaapi.smart_rotation import SmartRotation

# Initialize router
router = SmartRotation()

# Add multiple accounts / sessions
router.add_session("session1.json")
router.add_session("session2.json")
router.add_session("session3.json")

# Add your proxy pool
router.add_proxies([
    "http://px1.com",
    "http://px2.com",
    "http://px3.com"
])

# Use the router to transparently assign operations to the healthiest session
ig = router.get_next_client()
print(ig.users.get_by_username("nike").followers)

# In a loop, get_next_client() will constantly rotate sessions
for i in range(10):
    client = router.get_next_client()
    print(f"Using session: {client.session_id}")
    client.public.get_profile("adidas")
```

## How It Works

The `SmartRotation` manager implements a weighted Round-Robin algorithm.

1. It tracks the "health score" of every session (1.0 = perfect, 0.0 = banned/challenged).
2. It assigns requests to the session with the lowest recent usage and highest health.
3. If a session hits a `RateLimitError` or `ChallengeRequired`, its score is slashed, and the router will avoid giving it traffic until it recovers or you resolve the challenge.

## Combining with BatchAPI

The Smart Rotator handles multiple `Instagram` objects. If you want to use the high-performance `BatchAPI` or `bulk_profiles`, you should run them through individual clients:

```python
# Create 5 workers, each using a different rotated session
clients = [router.get_next_client() for _ in range(5)]

# Thread 1 uses clients[0], Thread 2 uses clients[1]...
```

## Auto-Recovery

If a session triggers a Challenge, the `SmartRotation` manager will flag it as `STATUS_CHALLENGED`.

If you configured a Challenge Handler (e.g. Email Auto-Resolver) when generating the clients, the router will automatically attempt to unlock the session in the background while keeping the main script running using the remaining healthy accounts.

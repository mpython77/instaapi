# Exception Reference

The `instaharvest_v2.exceptions` module structures all possible faults into a clean hierarchy. Catching specific exceptions provides insight into why your automation/scraper failed.

## Base Class

### InstagramError

The root exception. Catching this guarantees trapping any internal library error seamlessly.

```python
class InstagramError(Exception):
    def __init__(self, message: str = "", status_code: int = 0, response: dict = None): ...
```

Properties attached to all exceptions:

- `message`: Descriptive error string
- `status_code`: The HTTP Status (e.g., 429, 400). `0` if it's a local breakdown (like JSON decode error).
- `response`: The dict object holding exactly what Instagram responded with.

---

## Auth & Account Lifecycle

### LoginRequired

**Trigger:** Session cookie expired, wiped, or you never logged in. Replaces the typical HTTP 401 or HTTP 302 location trap.
**Fix:** Run `ig.login()` again.

### ChallengeRequired

**Trigger:** Instagram determined the session isn't suspicious enough for a ban, but requires verify (Email or Text).
**Features:** Retains `challenge_url` property pointing to the target endpoint.
**Fix:** Implement an auto-resolver payload.

### CheckpointRequired

**Trigger:** Account is temporarily locked or faces a visual checkpoint.
**Fix:** Open the official Instagram app to clear it.

### ConsentRequired

**Trigger:** Required to accept updated Terms of Service.
**Fix:** Usually auto-resolved by InstaHarvest v2 natively.

---

## Rate Limits

### RateLimitError

**Trigger:** You hit HTTP 429 (Too Many Requests).
**Fix:** Catch it, back off. If using `SpeedModes` effectively, InstaHarvest v2 handles this backing-off delay transparently without crashing your script.

---

## Resource Errors

### NotFoundError

**Trigger:** The requested data doesn't exist (HTTP 404).

### PrivateAccountError

**Trigger:** Tried to pull followers or posts from a locked account without following it first (HTTP 403).

### UserNotFound / MediaNotFound

These inherit from `NotFoundError`.

---

## Internal

### NetworkError

**Trigger:** `curl_cffi` failed entirely mapping a network failure (timeout, DNS resolution error, proxy dead).

### ProxyError

**Trigger:** The proxy configuration provided rejected the connection.

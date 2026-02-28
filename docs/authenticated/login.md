# Login & Sessions

Authenticated requests require a valid Instagram session. InstaAPI provides multiple ways to manage sessions and handle login challenges.

## Loading from .env (Recommended)

The safest way is to extract cookies from a browser where you're already logged in. This avoids new login alerts and challenges.

1. Open Instagram in your browser and log in
2. Open DevTools (F12) → Application → Cookies
3. Create a `.env` file:

```env
SESSION_ID=your_sessionid_cookie
CSRF_TOKEN=your_csrftoken_cookie
DS_USER_ID=your_ds_user_id_cookie

# Optional but recommended (increases stability)
MID=your_mid_cookie
IG_DID=your_ig_did_cookie
DATR=your_datr_cookie
USER_AGENT=your_user_agent_string
```

```python
from instaapi import Instagram

# Auto-loads from .env
ig = Instagram.from_env()
```

## Login with Credentials

```python
from instaapi import Instagram
from instaapi.exceptions import ChallengeRequired, LoginRequired

ig = Instagram()

try:
    ig.login("username", "password")
    
    # Save session for future use!
    ig.save_session("session.json")
    print("Login successful!")
    
except ChallengeRequired as e:
    print(f"Action required! Visit: {e.challenge_url}")
except LoginRequired as e:
    print(f"Login failed: {e.message}")
```

## Saving and Loading Sessions

Always save your session after logging in. Logging in repeatedly increases the chance of bans.

```python
# 1. First-time login
ig = Instagram()
ig.login("user", "pass")
ig.save_session("my_session.json")

# 2. Next time: load saved session
ig = Instagram.from_session_file("my_session.json")
```

## Session Expiration and Auto-Login

Cookies expire. If a configured session is no longer valid, you'll receive a `LoginRequired` exception (HTTP 401 or 302 redirect to login screen).

If you started with `from_session_file`, InstaAPI will attempt to transparently reload it or re-auth if possible (using the built-in `_build_refresh_callback`).

## Challenge Handling

When logging in from a new IP, Instagram often asks for email or SMS verification. InstaAPI includes the `ChallengeHandler` class to resolve these:

```python
from instaapi import Instagram, ChallengeHandler
from instaapi.exceptions import ChallengeRequired

ig = Instagram()

try:
    ig.login("user", "pass")
except ChallengeRequired as e:
    print(f"Challenge URL: {e.challenge_url}")
    print(f"Challenge type: {e.challenge_type}")
    
    # Use the ChallengeHandler to resolve
    handler = ChallengeHandler(ig._client)
    result = handler.resolve(e.response)
    print(f"Result: {result}")
```

For headless auto-resolution using Gmail, see [Challenge Resolver](../advanced/challenge-resolver.md).

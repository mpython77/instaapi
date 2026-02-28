# Batch Operations

> `ig.batch` — Optimized loops and bulk fetching methods.

!!! info "Different from Anonymous Bulk"
    `BatchAPI` is specifically for **Authenticated** contexts. For scraping hundreds of public profiles without login, refer to `AsyncPublicAPI` and Anonymous `bulk_operations`.

## Quick Example

```python
ig = Instagram.from_env()

# Quickly verify a list of usernames
results = ig.batch.check_profiles(["nike", "adidas", "fake_user_123"])

for username, data in results.items():
    if data:
        print(f"@{username} exists! (PK: {data.pk})")
    else:
        print(f"@{username} does not exist.")
```

## Why BatchAPI?

When dealing with authenticated endpoints (like `users.get_by_username()`), doing a standard Python `for` loop over 500 users will trigger Rate Limits quickly:

```python
# Bad - Will get 429 Rate Limited
for user in huge_list:
    ig.users.get_by_username(user)
```

`BatchAPI` wrappers automatically enforce optimal pacing, jittered delays, and chunking:

```python
# Good - Automatically paces and chunks
users = ig.batch.get_users(huge_list)
```

## Supported Operations

Currently, the authenticated Batch extensions support bulk reads:

* `check_profiles(usernames: list[str]) -> dict`: Returns `{username: UserShort}`. Extremely fast for cleaning target lists.
* `get_users(usernames: list[str]) -> list[User]`: Resolves full `User` models safely.
* `fetch_medias(media_ids: list[str]) -> list[Media]`: Resolves full `Media` models.

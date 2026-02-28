# FriendshipsAPI

> `ig.friendships` — Manage follower relationships: follow, unfollow, block, mute, restrict, close friends, and query friendship status.

## Quick Example

```python
from instaapi import Instagram

ig = Instagram.from_env()

user = ig.users.get_by_username("nasa")
ig.friendships.follow(user.pk)
print("Followed NASA!")
```

## Follow / Unfollow

### follow(user_id)

Follow an Instagram user. Automatically becomes a pending request if account is private.

| Param | Type | Required | Description |
|---|---|---|---|
| `user_id` | `int\|str` | ✅ | Account PK |

---

### unfollow(user_id)

Unfollow a user.

---

### remove_follower(user_id)

Force-remove a user from your followers list.

---

## Block / Restrict

### block(user_id)

Block a user.

---

### unblock(user_id)

Unblock a user.

---

### restrict(user_id)

Restrict a user (hide DMs, comments without blocking).

---

### unrestrict(user_id)

Remove restriction.

---

### mute(user_id, mute_posts=True, mute_stories=True)

Mute a user's posts and/or stories.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `user_id` | `int\|str` | ✅ | — | User PK |
| `mute_posts` | `bool` | ❌ | `True` | Hide posts from feed |
| `mute_stories` | `bool` | ❌ | `True` | Hide stories |

---

### unmute(user_id, unmute_posts=True, unmute_stories=True)

Unmute a user.

---

## Followers & Following Lists

### get_followers(user_id, count=50, after=None)

Fetch followers of a user.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `user_id` | `int\|str` | ✅ | — | Target account PK |
| `count` | `int` | ❌ | 50 | Items per page |
| `after` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict` with `users` list and pagination

```python
data = ig.friendships.get_followers(173560420)
for u in data.get("users", []):
    print(f"@{u.get('username')}")
```

---

### get_all_followers(user_id, max_count=1000, count_per_page=50)

Get all followers with automatic pagination.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `user_id` | `int\|str` | ✅ | — | Target PK |
| `max_count` | `int` | ❌ | 1000 | Maximum total |
| `count_per_page` | `int` | ❌ | 50 | Per API call |

**Returns:** `list[UserShort]`

```python
followers = ig.friendships.get_all_followers(173560420, max_count=200)
print(f"Got {len(followers)} followers")
```

---

### get_following(user_id, count=50, after=None)

Fetch accounts that a user is following.

**Returns:** `dict` with `users` list and pagination

---

### get_all_following(user_id, max_count=1000, count_per_page=50)

Get all following with automatic pagination.

**Returns:** `list[UserShort]`

---

## Friendship Status

### show(user_id)

Check relationship between you and a user (following, followed_by, blocking, muting, etc.).

| Param | Type | Required | Description |
|---|---|---|---|
| `user_id` | `int\|str` | ✅ | User PK |

**Returns:** `dict` — friendship state

```python
status = ig.friendships.show(173560420)
print("Following:", status.get("following"))
print("Followed by:", status.get("followed_by"))
print("Blocking:", status.get("blocking"))
```

---

## Follow Requests (Private Accounts)

### get_pending_requests()

List incoming follow requests (for private accounts).

**Returns:** `dict` with `users` list

---

### approve_request(user_id)

Approve an incoming follow request.

---

### reject_request(user_id)

Reject/ignore a follow request.

---

## Close Friends

### get_close_friends()

Get your Close Friends list.

**Returns:** `dict` with `users` list

---

### add_close_friend(user_id)

Add a user to Close Friends.

---

### set_close_friends(add_user_ids=None, remove_user_ids=None)

Bulk add/remove Close Friends.

| Param | Type | Required | Description |
|---|---|---|---|
| `add_user_ids` | `list[int\|str]` | ❌ | PKs to add |
| `remove_user_ids` | `list[int\|str]` | ❌ | PKs to remove |

---

### is_close_friend(user_id)

Check if a user is in your Close Friends list.

**Returns:** `bool`

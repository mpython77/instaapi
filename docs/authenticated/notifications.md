# NotificationsAPI

> `ig.notifications` — Activity feed, notification inbox, follow/like alerts, notification counters.

## Quick Example

```python
from instaharvest_v2 import Instagram

ig = Instagram.from_env()

# Parsed inbox
inbox = ig.notifications.get_inbox_parsed()
print(f"Unread: {inbox.counts.total}")

for n in inbox.follows:
    print(f"👤 {n.follower_username} followed you ({n.time_ago})")

for n in inbox.likes:
    print(f"❤️ {n.profile_name} liked — {n.media_shortcode}")
```

## Raw Methods

### get_activity()

Get full notifications inbox (raw API response).

**Returns:** `dict` with `counts`, `new_stories`, `old_stories`, `continuation_token`

---

### get_activity_counts()

Get only notification counters.

**Returns:** `dict` — `likes`, `comments`, `relationships`, etc.

---

### get_new_notifications()

Get unread notifications (raw dict list).

**Returns:** `list[dict]`

---

### get_all_notifications()

Get all notifications (raw, new + old combined).

**Returns:** `list[dict]`

---

### mark_inbox_seen()

Mark all notifications as read.

**Returns:** `dict` with `status: "ok"`

---

### get_timeline()

Get main feed timeline.

**Returns:** `dict`

---

## Parsed Methods (Pydantic Models)

### get_inbox_parsed()

Get full inbox with all notifications parsed into Pydantic models.

**Returns:** `NotifInbox` with:

| Field | Type | Description |
|---|---|---|
| `counts` | `NotifCounts` | Category counters |
| `new_notifications` | `list[Notification]` | Unread items |
| `old_notifications` | `list[Notification]` | Read items |
| `all_notifications` | `list[Notification]` | Combined |
| `follows` | `list[Notification]` | Follow-only |
| `likes` | `list[Notification]` | Like-only |

```python
inbox = ig.notifications.get_inbox_parsed()
print(f"Total unread: {inbox.counts.total}")
print(f"New followers: {len(inbox.follows)}")
print(f"New likes: {len(inbox.likes)}")
```

---

### get_counts_parsed()

Get notification counters as a Pydantic model.

**Returns:** `NotifCounts`

| Field | Type | Description |
|---|---|---|
| `likes` | `int` | Like notifications |
| `comments` | `int` | Comment notifications |
| `relationships` | `int` | Follow notifications |
| `total` | `int` | Grand total |

```python
counts = ig.notifications.get_counts_parsed()
print(f"Likes: {counts.likes}")
print(f"Followers: {counts.relationships}")
print(f"Total: {counts.total}")
```

---

### get_all_parsed()

All notifications as parsed list.

**Returns:** `list[Notification]`

```python
for n in ig.notifications.get_all_parsed():
    print(f"[{n.notif_name}] {n.text} ({n.time_ago})")
```

---

### get_new_parsed()

Only unread notifications (parsed).

**Returns:** `list[Notification]`

---

### get_follow_notifications()

Only follow notifications (parsed) with rich user info.

**Returns:** `list[Notification]` — each has:

| Field | Type | Description |
|---|---|---|
| `follower_username` | `str` | Who followed |
| `follower_info` | `NotifUserInfo` | Full user info (avatar, verified, private) |
| `is_following_back` | `bool` | Mutual follow status |
| `time_ago` | `str` | Relative time |

```python
for n in ig.notifications.get_follow_notifications():
    user = n.follower_info
    print(f"@{user.username} ({user.full_name})")
    print(f"  Verified: {user.is_verified} | Private: {user.is_private}")
    print(f"  Following back: {n.is_following_back}")
```

---

### get_like_notifications()

Only like notifications (parsed).

**Returns:** `list[Notification]` — each has:

| Field | Type | Description |
|---|---|---|
| `profile_name` | `str` | Who liked |
| `media_shortcode` | `str` | Which post |
| `media_image` | `str` | Post preview URL |
| `text` | `str` | Notification text |

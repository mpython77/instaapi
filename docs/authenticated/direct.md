# DirectAPI

> `ig.direct` — Direct Messages: inbox, threads, send text/media/links/profiles, reactions.

## Quick Example

```python
from instaapi import Instagram

ig = Instagram.from_env()

# Read inbox
inbox = ig.direct.get_inbox()
for thread in inbox.get("inbox", {}).get("threads", []):
    print(f"{thread['thread_title']}: {thread['last_permanent_item']['text']}")

# Send message
ig.direct.send_text("340282366841710300949128", "Hey! 👋")
```

## Inbox

### get_inbox(cursor=None, limit=20)

Get all conversations (inbox).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `cursor` | `str` | ❌ | `None` | Pagination cursor |
| `limit` | `int` | ❌ | 20 | Threads per page |

**Returns:** `dict` — inbox with threads, pending count

---

### get_pending_inbox()

Get pending message requests (from non-followers).

**Returns:** `dict`

---

### get_thread(thread_id, cursor=None)

Get full message history of a single conversation.

| Param | Type | Required | Description |
|---|---|---|---|
| `thread_id` | `str` | ✅ | Thread ID |
| `cursor` | `str` | ❌ | Pagination cursor for older messages |

**Returns:** `dict` — thread with messages

---

## Sending Messages

### send_text(thread_id, text)

Send a text message.

| Param | Type | Required | Description |
|---|---|---|---|
| `thread_id` | `str` | ✅ | Thread ID |
| `text` | `str` | ✅ | Message content |

```python
ig.direct.send_text("340282366841710300949128", "Hello! 🔥")
```

---

### send_link(thread_id, url, text="")

Share a link in a conversation.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `thread_id` | `str` | ✅ | — | Thread ID |
| `url` | `str` | ✅ | — | Link URL |
| `text` | `str` | ❌ | `""` | Additional text |

---

### send_media_share(thread_id, media_id)

Share a post in DMs.

| Param | Type | Required | Description |
|---|---|---|---|
| `thread_id` | `str` | ✅ | Thread ID |
| `media_id` | `int\|str` | ✅ | Post PK |

---

### send_profile(thread_id, user_id)

Share a user's profile in DMs.

| Param | Type | Required | Description |
|---|---|---|---|
| `thread_id` | `str` | ✅ | Thread ID |
| `user_id` | `int\|str` | ✅ | User PK to share |

---

### create_thread(user_ids, text="")

Start a new conversation with one or more users.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `user_ids` | `list[int\|str]` | ✅ | — | Recipient user PKs |
| `text` | `str` | ❌ | `""` | Initial message |

```python
# DM a new user
thread = ig.direct.create_thread([173560420], "Hi there!")
```

---

## Interactions

### send_reaction(thread_id, item_id, emoji="❤️")

React to a message with an emoji.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `thread_id` | `str` | ✅ | — | Thread ID |
| `item_id` | `str` | ✅ | — | Message ID |
| `emoji` | `str` | ❌ | `"❤️"` | Reaction emoji |

---

### unsend_message(thread_id, item_id)

Unsend/delete a message you sent.

---

### mark_seen(thread_id, item_id=None)

Mark messages in a thread as seen.

---

## Thread Management

### mute_thread(thread_id)

Mute notification for a conversation.

---

### unmute_thread(thread_id)

Unmute a conversation.

---

### leave_thread(thread_id)

Leave a group conversation.

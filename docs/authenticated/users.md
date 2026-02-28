# UsersAPI

> `ig.users` — Retrieve and manage Instagram user profiles.

## Quick Example

```python
from instaharvest_v2 import Instagram

ig = Instagram.from_env()

# Get profile
user = ig.users.get_by_username("nike")
print(f"{user.full_name} has {user.followers:,} followers.")

# Full profile with contact + bio parsing
full = ig.users.get_full_profile("nike")
```

## Methods

### get_by_username(username)

Get full user profile by username.

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Instagram username (without @) |

**Returns:** `User` model

```python
user = ig.users.get_by_username("cristiano")
if user:
    print(user.pk, user.username, user.followers)
```

---

### get_by_id(user_id)

Get full user profile by unique ID (PK) via GraphQL.

| Param | Type | Required | Description |
|---|---|---|---|
| `user_id` | `int\|str` | ✅ | User PK |

**Returns:** `User` model

```python
user = ig.users.get_by_id(173560420)
```

---

### get_user_id(username)

Get user_id (PK) by username — shortcut method.

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Instagram username |

**Returns:** `int`

```python
pk = ig.users.get_user_id("cristiano")
# 173560420
```

---

### search(query)

Search for users. If the query looks like a username, it does a direct lookup; otherwise falls back to `/web/search/topsearch/`.

| Param | Type | Required | Description |
|---|---|---|---|
| `query` | `str` | ✅ | Username or name |

**Returns:** `list[UserShort]`

```python
results = ig.users.search("cristiano")
for u in results:
    print(f"@{u.username} — {u.full_name}")
```

---

### parse_bio(user_data)

Parse mentions (`@user`), hashtags (`#tag`), and entities from a bio string.

| Param | Type | Required | Description |
|---|---|---|---|
| `user_data` | `dict\|User` | ✅ | Result from `get_by_username()` or raw dict |

**Returns:** `BioParsed` model

```python
user = ig.users.get_by_username("nike")
bio = ig.users.parse_bio(user)
print("Mentions:", bio.bio_mentions)
print("Hashtags:", bio.bio_hashtags)
print("Emails:", bio.bio_emails)
print("Phones:", bio.bio_phones)
```

---

### get_full_profile(username)

Gather ALL profile data in one call. Combines `web_profile_info` + `user_info` + bio parsing.

| Param | Type | Required | Description |
|---|---|---|---|
| `username` | `str` | ✅ | Instagram username |

**Returns:** `User` model (with full contact, bio counters, etc.)

```python
user = ig.users.get_full_profile("nasa")
print(user.biography)
if user.contact.email:
    print("Email:", user.contact.email)
if user.contact.phone:
    print("Phone:", user.contact.phone)
```

---

## Models

### User Model Reference

| Field | Type | Description |
|---|---|---|
| `pk` | `int` | Unique User ID |
| `username` | `str` | Handle |
| `full_name` | `str` | Display Name |
| `is_private` | `bool` | Private account |
| `is_verified` | `bool` | Verified badge |
| `profile_pic_url` | `str` | Normal avatar |
| `profile_pic_url_hd` | `str` | HD avatar |
| `followers` | `int` | Follower count |
| `following` | `int` | Following count |
| `posts_count` | `int` | Media count |
| `biography` | `str` | Bio text |
| `bio_links` | `list` | URLs in bio |
| `external_url` | `str` | Legacy website field |
| `is_business` | `bool` | Business/creator account |
| `category` | `str` | Business category |
| `contact` | `Contact` | Contact object (email/phone) |

### BioParsed Model

| Field | Type | Description |
|---|---|---|
| `bio_mentions` | `list[str]` | @username mentions |
| `bio_hashtags` | `list[str]` | #tag references |
| `bio_emails` | `list[str]` | Extracted emails |
| `bio_phones` | `list[str]` | Extracted phone numbers |
| `bio_urls` | `list[str]` | Extracted URLs |
| `bio_links` | `list` | Structured link objects |
| `bio_entities` | `list[dict]` | Raw bio entities |

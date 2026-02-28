# AnonClient (Low-Level)

Direct access to anonymous Instagram endpoints. Used internally by `PublicAPI`.

!!! note "Prefer PublicAPI"
    For most use cases, use `ig.public.*` methods. AnonClient is for advanced users who need direct endpoint control.

```python
ig = Instagram.anonymous()
client = ig._anon_client  # AnonClient instance
```

---

## Strategy Methods

### get_profile_html(username)

Parse profile from HTML page (SharedData + meta tags).

```python
profile = client.get_profile_html("cristiano")
# Returns parsed profile dict or None
```

### get_embed_data(shortcode)

Get post data from embed endpoint.

```python
data = client.get_embed_data("ABC123")
# Returns embed media dict or None
```

### get_graphql_public(query_hash, variables)

Make public GraphQL query.

```python
data = client.get_graphql_public(
    query_hash="d4d88dc1500312af6f937f7b804c68c3",
    variables={"user_id": "173560420", "first": 12}
)
```

### get_web_api(path, params=None)

Make web API request to `i.instagram.com/api/v1/`.

```python
data = client.get_web_api(
    "/users/web_profile_info/",
    params={"username": "cristiano"}
)
```

### get_mobile_api(path, params=None)

Make mobile API request to `i.instagram.com/api/v1/`.

```python
data = client.get_mobile_api(
    "/feed/user/173560420/",
    params={"count": 12}
)
```

---

## Endpoint Methods

### get_web_profile(username)

Get profile via web API strategy.

**Returns:** `(profile_dict, posts_list)` or `(None, [])`

```python
profile, posts = client.get_web_profile("cristiano")
```

### get_user_info_mobile(user_id)

Get user info via mobile API.

```python
info = client.get_user_info_mobile(173560420)
```

### search_web(query)

Search via web API.

**Returns:**

```python
{
    "users": [{"username": ..., "follower_count": ...}],
    "hashtags": [{"name": ..., "media_count": ...}],
    "places": [{"title": ..., "location": {...}}],
}
```

### get_user_reels(user_id, max_id=None)

Get reels via mobile API.

**Returns:**

```python
{
    "items": [{"pk": ..., "play_count": ..., "is_reel": True, ...}],
    "more_available": True,
    "next_max_id": "cursor..."
}
```

### get_user_feed_mobile(user_id, count=12, max_id=None)

Get user feed via mobile API.

**Returns:**

```python
{
    "items": [{"pk": ..., "likes": ..., "shortcode": ..., ...}],
    "more_available": True,
    "next_max_id": "cursor..."
}
```

### get_media_info_mobile(media_id)

Get single media details.

### get_hashtag_sections(hashtag, max_id=None)

Get hashtag posts via sections API.

### get_location_sections(location_id, max_id=None)

Get location posts via sections API.

### get_similar_accounts(user_id)

Get similar/recommended accounts.

### get_highlights_tray(user_id)

Get highlight tray metadata.

---

## Parser Methods

| Method | Input | Output |
|---|---|---|
| `_parse_graphql_user(user)` | GraphQL user dict | Normalized profile |
| `_parse_timeline_edges(edges)` | GraphQL edges | Post list |
| `_parse_mobile_feed_item(item)` | Mobile API item | Normalized post |
| `_parse_embed_media(media)` | Embed response | Normalized post |
| `_parse_meta_tags(html)` | HTML string | Profile from meta |
| `_parse_count(text)` | "1.5M" / "12K" | `int` |

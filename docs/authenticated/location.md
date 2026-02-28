# LocationAPI

> `ig.location` — Location info, feed, search, and nearby places.

## Quick Example

```python
from instaharvest_v2 import Instagram

ig = Instagram.from_env()

# Search for places
places = ig.location.search("Times Square")
for v in places.get("venues", []):
    print(f"{v['name']} (PK: {v['external_id']})")

# Get location feed
feed = ig.location.get_feed(213385402)
```

## Methods

### get_info(location_id)

Get location details (name, address, coordinates, media count).

| Param | Type | Required | Description |
|---|---|---|---|
| `location_id` | `int\|str` | ✅ | Location PK |

**Returns:** `dict`

---

### get_feed(location_id, max_id=None)

Get posts from a location (top + recent).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `location_id` | `int\|str` | ✅ | — | Location PK |
| `max_id` | `str` | ❌ | `None` | Pagination cursor |

**Returns:** `dict` with `sections`, `next_max_id`, `more_available`

---

### search(query, lat=None, lng=None)

Search for locations by name. Optionally narrow results with coordinates.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `str` | ✅ | — | Place name |
| `lat` | `float` | ❌ | `None` | Latitude hint |
| `lng` | `float` | ❌ | `None` | Longitude hint |

**Returns:** `dict` with `venues` list

```python
places = ig.location.search("Eiffel Tower", lat=48.858, lng=2.294)
```

---

### get_nearby(lat, lng)

Get locations near given coordinates.

| Param | Type | Required | Description |
|---|---|---|---|
| `lat` | `float` | ✅ | Latitude |
| `lng` | `float` | ✅ | Longitude |

**Returns:** `dict` — list of nearby places

```python
nearby = ig.location.get_nearby(41.311, 69.279)  # Tashkent
for place in nearby.get("venues", []):
    print(f"📍 {place['name']}")
```

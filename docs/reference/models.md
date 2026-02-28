# Models Dictionary

Complete dictionary mapping to the native `instaharvest_v2.models` schema. Extracted payloads provide full code hinting in IDEs like VSCode and PyCharm.

## User Models

### UserShort

Extremely lightweight model specifically designed for packing RAM heavily when scraping 1M+ followers lists.

| Property | Type |
|---|---|
| `pk` | `str` / `int` |
| `username` | `str` |
| `full_name` | `str` |
| `is_private` | `bool` |
| `is_verified` | `bool` |
| `profile_pic_url` | `str` |

### User

Extends `UserShort` encompassing the heavy data profile grabs.

| Property | Type | Note |
|---|---|---|
| `biography` | `str` | Raw string |
| `followers` | `int` | Exact count |
| `following` | `int` | Exact count |
| `external_url` | `str` | |
| `bio_links` | `list` | Contains structured URL maps |
| `is_business` | `bool` | |
| `contact` | `Contact` | Sub-model |

### Contact

Only populates if `is_business` is True.

| Property | Type |
|---|---|
| `email` | `str` |
| `phone` | `str` |
| `phone_country_code` | `str` |
| `city` | `str` |
| `address` | `str` |

## Media Models

### Media

Posts, Reels, and IGTV.

| Property | Type | Note |
|---|---|---|
| `pk` | `str` / `int` | Numeric identifier |
| `shortcode` | `str` | Link identifier |
| `media_type` | `int` | Type Enum |
| `like_count` | `int` | |
| `comment_count` | `int` | |
| `taken_at` | `datetime` | |
| `image_versions` | `list` | URLs to CDN host |
| `video_url` | `str` | If type is Video |
| `carousel_media` | `list[Media]` | If type is Carousel |
| `caption` | `Caption` | Contains `.text` |
| `location` | `Location` | |

### Comment

| Property | Type |
|---|---|
| `pk` | `str` |
| `text` | `str` |
| `user` | `UserShort` |
| `created_at` | `datetime` |
| `like_count` | `int` |

### Location

| Property | Type |
|---|---|
| `pk` | `int` |
| `name` | `str` |
| `city` | `str` |
| `address` | `str` |
| `lat` / `lng` | `float` |

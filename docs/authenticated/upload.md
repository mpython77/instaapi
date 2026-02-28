# UploadAPI

> `ig.upload` — Upload photos, videos, stories, reels, and carousels to Instagram.

## Quick Example

```python
from instaharvest_v2 import Instagram

ig = Instagram.from_env()

# Upload a photo post
result = ig.upload.post_photo(
    image_path="photo.jpg",
    caption="Beautiful day! ☀️ #nature",
)
print(f"Posted! Media PK: {result['media']['pk']}")
```

## Photo Posts

### post_photo(image_path=None, image_data=None, caption="", location=None, usertags=None, disable_comments=False)

Upload a photo as a feed post.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `image_path` | `str` | ❌ | `None` | Path to JPEG/PNG file |
| `image_data` | `bytes` | ❌ | `None` | Raw image bytes (instead of path) |
| `caption` | `str` | ❌ | `""` | Post caption (supports hashtags, mentions) |
| `location` | `dict` | ❌ | `None` | `{"pk": ..., "name": ..., "lat": ..., "lng": ...}` |
| `usertags` | `list[dict]` | ❌ | `None` | Tag users in photo |
| `disable_comments` | `bool` | ❌ | `False` | Disable comments |

!!! note
    Either `image_path` or `image_data` must be provided.

```python
result = ig.upload.post_photo(
    image_path="sunset.jpg",
    caption="Golden hour 🌅 #photography",
    location={"pk": 213385402, "name": "New York"},
)
```

---

## Video Posts

### post_video(video_path=None, video_data=None, thumbnail_path=None, thumbnail_data=None, caption="", duration=0, width=1080, height=1920, location=None, disable_comments=False)

Upload a video as a feed post.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `video_path` | `str` | ❌ | `None` | Path to MP4 file |
| `video_data` | `bytes` | ❌ | `None` | Raw video bytes |
| `thumbnail_path` | `str` | ❌ | `None` | Cover image path |
| `thumbnail_data` | `bytes` | ❌ | `None` | Cover image bytes |
| `caption` | `str` | ❌ | `""` | Post caption |
| `duration` | `float` | ❌ | 0 | Video duration in seconds |
| `width` | `int` | ❌ | 1080 | Video width |
| `height` | `int` | ❌ | 1920 | Video height |

---

## Reels

### post_reel(video_path=None, video_data=None, thumbnail_path=None, thumbnail_data=None, caption="", duration=0, width=1080, height=1920)

Upload a Reel (Clips).

```python
result = ig.upload.post_reel(
    video_path="my_reel.mp4",
    caption="Check it out! 🎬 #reels",
    duration=15.0,
)
```

---

## Carousel / Album

### post_carousel(images=None, caption="", location=None, usertags=None, disable_comments=False)

Upload a multi-image carousel post (2-10 images).

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `images` | `list[str\|bytes]` | ✅ | — | 2-10 file paths or bytes |
| `caption` | `str` | ❌ | `""` | Post caption |
| `location` | `dict` | ❌ | `None` | Location tag |
| `usertags` | `list[dict]` | ❌ | `None` | Tag users |
| `disable_comments` | `bool` | ❌ | `False` | Disable comments |

```python
result = ig.upload.post_carousel(
    images=["photo1.jpg", "photo2.jpg", "photo3.jpg"],
    caption="Album vibes 📸",
)
```

---

## Stories

### post_story_photo(image_path=None, image_data=None)

Upload a photo story.

**Returns:** `dict` with `media` containing `pk`

---

### post_story_video(video_path=None, video_data=None, duration=0)

Upload a video story (max 15 seconds).

**Returns:** `dict` with `media` containing `pk`

---

## Delete

### delete_media(media_id, media_type=1)

Delete a post.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `media_id` | `int\|str` | ✅ | — | Media PK |
| `media_type` | `int` | ❌ | 1 | 1=photo, 2=video, 8=carousel |

**Returns:** `dict` with `status` and `did_delete`

```python
ig.upload.delete_media(3124567890123)
```

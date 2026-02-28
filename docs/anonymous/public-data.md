# Instagram Public Data

The `PublicDataAPI` provides a comprehensive suite of methods to fetch, analyze, and track Instagram data without requiring user authentication. This module is specifically designed to be compatible with Supermetrics-style reporting, offering extensive analytics capabilities through anonymous access.

## Overview

Unlike standard anonymous endpoints, `PublicDataAPI` aggregates multiple endpoints, tracks rating limits (e.g., hashtag quotas limits), computes engagement metrics, and allows you to build standard analytics reports out of the box.

```python
from instaapi import Instagram

ig = Instagram.anonymous()

# Fetch deep profile analytics
profile = ig.public_data.get_profile_info("nike")
print(f"Followers: {profile.followers:,}")

# Look up recent posts by hashtag
top_posts = ig.public_data.search_hashtag_top("fitness")
print(f"Found {len(top_posts)} top posts")
```

## Features

- **No login required**: Works 100% anonymously using the `AnonClient`.
- **Supermetrics Compatibility**: Allows exporting data seamlessly to `PROFILES`, `POSTS`, and `HASHTAGS` tables.
- **Engagement Analysis**: Instantly compute average likes, comments, and engagement scores (Poor to Excellent).
- **Competitor Tracking**: Track account growth over time with `ProfileSnapshot`.
- **Hashtag Quota Tracking**: Automatically tracks the Instagram anonymous limit of 30 unique hashtag searches per profile per 7 days.
- **Async Parity**: Available as `AsyncPublicDataAPI`.

---

## 👤 Profile Information

Fetch detailed statistics and information about a public account or multiple accounts.

### `get_profile_info(username: str) -> PublicProfile`

Retrieves a single profile's analytics.

```python
profile = ig.public_data.get_profile_info("cristiano")
print(profile.is_verified)
```

---

## 📸 Profile Posts

Fetch a user's recent posts along with metadata such as likes, comments, and engagements.

### `get_profile_posts(username: str, max_count: int = 50) -> List[PublicPost]`

```python
posts = ig.public_data.get_profile_posts("nike", max_count=20)
for post in posts:
    print(post.post_url, post.likes, post.comments)
```

---

## 🔍 Hashtag Search

Search for public posts using a specific hashtag.

> **⚠️ Quota Warning**: Instagram anonymously restricts you to 30 unique hashtag searches per profile per 7 rolling days. The `PublicDataAPI` automatically tracks this. You can check your remaining quota using `ig.public_data.get_hashtag_quota()`.

### `search_hashtag_top(hashtag: str) -> List[HashtagPost]`

Fetches the "Top Posts" for a given hashtag (always returns a maximum of 100 posts).

### `search_hashtag_recent(hashtag: str) -> List[HashtagPost]`

Fetches the "Recent Posts" for a given hashtag within the last 24 hours (maximum of 250 posts).

```python
results = ig.public_data.search_hashtag_recent("python")
for item in results:
    print(item.post.shortcode)
```

---

## 📊 Analytics & Reporting

### `compare_profiles(usernames: List[str]) -> Dict`

Ranks and compares multiple profiles based on followers and engagement metrics.

```python
metrics = ig.public_data.compare_profiles(["nike", "adidas", "puma"])
print(metrics["ranks"])
```

### `engagement_analysis(username: str) -> Dict`

Calculates average likes, comments, and assigns an engagement score.

```python
analysis = ig.public_data.engagement_analysis("nike")
print(analysis["rating"]) # Output: 'Excellent', 'Good', etc.
```

### `track_profile(username: str) -> ProfileSnapshot`

Records the profile's current state and saves it to a local historical database (`.instaapi/public_history.json`). Allowing you to measure follower growth over time.

---

## 📤 Export & Supermetrics Reports

### `build_report(usernames, top_hashtags, recent_hashtags) -> PublicDataReport`

Builds an aggregated report containing profiles, posts, and hashtag posts.

```python
report = ig.public_data.build_report(
    usernames=["nike", "adidas"],
    top_hashtags=["shoes"]
)
```

### `export_report(report, format, output_file)`

Exports the built report to a specific file format (`json`, `csv`, or `jsonl`).

```python
ig.public_data.export_report(report, "csv", "my_analytics.csv")
```

Or you can use the object mappings to upload standard tables directly:

```python
db.insert_profiles(report.to_profiles_table())
db.insert_posts(report.to_posts_table())
db.insert_hashtags(report.to_hashtags_table())
```

## Available Models

- `PublicProfile`
- `PublicPost`
- `HashtagPost`
- `ProfileSnapshot`
- `PublicDataReport`

For more details on the models referenced here, see the [Reference Models](../reference/models.md) documentation.

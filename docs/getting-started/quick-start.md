# Quick Start

Get up and running in 5 minutes.

---

## 1. Anonymous — No Login Needed

Scrape public Instagram data **without login**:

```python
from instaapi import Instagram

# Create anonymous client
ig = Instagram.anonymous()

# Get any public profile
profile = ig.public.get_profile("cristiano")

print(f"Username:  {profile['username']}")
print(f"Full Name: {profile['full_name']}")
print(f"Followers: {profile['followers']:,}")
print(f"Following: {profile['following']:,}")
print(f"Posts:     {profile['posts_count']}")
print(f"Bio:      {profile['biography']}")
print(f"Verified:  {profile['is_verified']}")
```

### Get Posts

```python
posts = ig.public.get_posts("cristiano", max_count=12)

for post in posts:
    print(f"[{post['shortcode']}] ❤️ {post['likes']:,} 💬 {post['comments']}")
```

### Get Post by URL

```python
post = ig.public.get_post_by_url("https://instagram.com/p/ABC123/")
print(post['caption'][:100])
```

### Search

```python
results = ig.public.search("fashion")

for user in results["users"]:
    print(f"@{user['username']} — {user['follower_count']:,} followers")
```

---

## 2. Authenticated — Full Access

For private data, login with session cookies:

### Option A: From .env file

Create `.env`:

```env
SESSION_ID=your_session_id_here
CSRF_TOKEN=your_csrf_token
DS_USER_ID=your_user_id
```

```python
from instaapi import Instagram

ig = Instagram.from_env(".env")

# Get any user's full profile
user = ig.users.get_by_username("cristiano")
print(f"{user.full_name} — {user.followers:,} followers")

# Get user's posts and like the first one
posts = ig.feed.get_all_posts(user.pk, max_posts=1)
if posts:
    ig.media.like(posts[0].pk)

# Follow a user
ig.friendships.follow(user.pk)
```

### Option B: Login with credentials

```python
from instaapi import Instagram

ig = Instagram()
ig.login("your_username", "your_password")
ig.save_session("session.json")  # Save for later use
```

### Option C: Load saved session

```python
ig = Instagram.from_session_file("session.json")
```

---

## 3. Async — Maximum Performance

```python
import asyncio
from instaapi import AsyncInstagram

async def main():
    async with AsyncInstagram.anonymous(unlimited=True) as ig:
        # Parallel — 200 profiles in 15 seconds!
        usernames = ["nike", "adidas", "puma", "gucci", "zara"]
        tasks = [ig.public.get_profile(u) for u in usernames]
        profiles = await asyncio.gather(*tasks)

        for p in profiles:
            if p:
                print(f"@{p['username']}: {p['followers']:,}")

asyncio.run(main())
```

---

## Next Steps

- [Configuration](configuration.md) — Learn about `.env`, proxies, and speed modes
- [Anonymous Scraping](../anonymous/overview.md) — Deep dive into 5-strategy scraping
- [Async Guide](../advanced/async-guide.md) — Master async operations

# InstaAPI

<div align="center" markdown>

## Powerful Instagram Private API Library

**curl_cffi** engine · **5-strategy** anonymous scraping · **True async** · **Anti-detection** · **AI Agent**

[:material-download: Install](#installation){ .md-button .md-button--primary }
[:material-book-open-variant: Quick Start](getting-started/quick-start.md){ .md-button }

</div>

---

## Why InstaAPI?

| Feature | InstaAPI | instagrapi | instaloader |
|---|---|---|---|
| Anonymous scraping | ✅ 5 strategies | ⚠️ Limited | ⚠️ Basic |
| Async support | ✅ 32 async modules | ❌ | ❌ |
| TLS fingerprint | ✅ 10+ browsers | ❌ | ❌ |
| Speed modes | ✅ 4 modes | ❌ | ❌ |
| Proxy management | ✅ Built-in | ⚠️ Basic | ❌ |
| AI Agent | ✅ 13 providers | ❌ | ❌ |
| Advanced tools | ✅ 12 tools | ❌ | ❌ |
| CI/CD + Tests | ✅ 475 tests | ⚠️ Basic | ⚠️ Basic |

## Key Features

<div class="grid cards" markdown>

- :material-incognito:{ .lg .middle } **Anonymous Scraping**

    ---

    5-strategy fallback chain — HTML, Embed, GraphQL, Mobile, Web API.
    No login needed for public data.

- :material-lightning-bolt:{ .lg .middle } **Speed Modes**

    ---

    SAFE → FAST → TURBO → UNLIMITED.
    From ban-proof to 1000 concurrent requests.

- :material-sync:{ .lg .middle } **Full Async Parity**

    ---

    32 sync + 32 async modules — complete feature match. `asyncio.gather` for bulk ops.

- :material-shield-lock:{ .lg .middle } **Anti-Detection**

    ---

    TLS fingerprint rotation, browser impersonation, header randomization via `curl_cffi`.

- :material-server-network:{ .lg .middle } **Proxy Management**

    ---

    Built-in `ProxyManager` with health checking, auto-rotation, and BrightData integration.

- :material-puzzle:{ .lg .middle } **Plugin System**

    ---

    Extensible architecture with event hooks, plugins, and middleware.

- :material-robot:{ .lg .middle } **AI Agent** :material-new-box:{ .lg .middle }

    ---

    Control Instagram with natural language. 13 AI providers, 10 tools, memory, scheduling, webhooks.

    [:octicons-arrow-right-24: Learn more](agent/overview.md)

- :material-tools:{ .lg .middle } **12 Advanced Tools** :material-new-box:{ .lg .middle }

    ---

    Analytics, Export, Growth, Automation, Monitor, Scheduler, Pipeline, AI Suggest, Audience, Comment Manager, A/B Test, Bulk Download.

    [:octicons-arrow-right-24: Browse tools](tools/analytics.md)

- :material-test-tube:{ .lg .middle } **Testing & CI/CD**

    ---

    475 tests, pytest-cov, GitHub Actions pipeline — lint, test, security, build.

</div>

## Installation { #installation }

```bash
pip install instaapi
```

**With extras:**

```bash
pip install instaapi[dev]      # pytest, pytest-cov, pytest-asyncio
pip install instaapi[agent]    # AI providers (Gemini, OpenAI, Claude)
pip install instaapi[web]      # FastAPI web playground
pip install instaapi[all]      # everything
```

## Quick Example

=== "Anonymous (no login)"

    ```python
    from instaharvest_v2 import Instagram

    ig = Instagram.anonymous()
    profile = ig.public.get_profile("cristiano")
    print(f"{profile['username']}: {profile['followers']:,} followers")
    ```

=== "Reel / Post Scraping :material-new-box:"

    ```python
    from instaharvest_v2 import Instagram

    ig = Instagram()  # no login needed!

    # Get any reel/post by shortcode or URL — no cookies required
    post = ig.public.get_post_by_shortcode("ABC123")
    print(post["video_url"])    # full video download URL
    print(post["likes"])        # 69603
    print(post["audio"])        # music info for reels
    ```

=== "Authenticated"

    ```python
    from instaharvest_v2 import Instagram

    ig = Instagram.from_env(".env")
    user = ig.users.get_by_username("cristiano")
    ig.media.like(user.media[0].pk)
    ```

=== "Async"

    ```python
    import asyncio
    from instaharvest_v2 import AsyncInstagram

    async def main():
        async with AsyncInstagram.anonymous(unlimited=True) as ig:
            tasks = [ig.public.get_profile(u) for u in ["nike", "adidas"]]
            results = await asyncio.gather(*tasks)

    asyncio.run(main())
    ```

=== "AI Agent :material-new-box:"

    ```python
    from instaharvest_v2 import Instagram
    from instaharvest_v2.agent import InstaAgent, Permission

    ig = Instagram.from_env(".env")
    agent = InstaAgent(
        ig=ig,
        provider="gemini",
        permission=Permission.FULL_ACCESS,
        memory=True,
    )

    agent.ask("Get @cristiano's last 10 posts and save to CSV")
    agent.ask("Compare @nike and @adidas engagement rates")
    agent.ask("Find the best posting time for my account")
    ```

=== "Advanced Tools :material-new-box:"

    ```python
    from instaharvest_v2 import Instagram

    ig = Instagram.from_env()

    # Analytics
    report = ig.analytics.engagement_rate("cristiano")

    # Export to CSV
    ig.export.followers_to_csv("nike", "followers.csv")

    # Growth engine
    ig.growth.follow_users_of("competitor", count=20)

    # Hashtag research
    analysis = ig.hashtag_research.analyze("python")

    # A/B testing
    test = ig.ab_test.create("Test", variants={"A": {}, "B": {}})
    ```

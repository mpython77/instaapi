# Changelog

All notable changes to instaharvest_v2.

## [1.0.0] - 2026-02-28

### 🎉 Initial Release — Full-Featured Instagram API Library

#### Core Engine

- HTTP client powered by `curl_cffi` engine
- Session management with cookie rotation
- Smart proxy rotation with health checking
- Anti-detection system with fingerprint rotation
- Configurable speed modes: safe/normal/aggressive/turbo
- Retry with exponential backoff, jitter, provider fallback

#### API Modules (32 sync + 32 async)

- **Users** — profile info, search, suggestions
- **Media** — posts, reels, IGTV, carousels
- **Feed** — timeline, user feed, saved posts
- **Search** — users, hashtags, locations, top results
- **Hashtags** — feed, related, top posts
- **Friendships** — follow, unfollow, followers, following
- **Direct** — DM threads, messages, media sharing
- **Stories** — view, download, story composer
- **Insights** — account analytics, post insights
- **Account** — profile editing, settings
- **Notifications** — activity feed
- **GraphQL** — raw GraphQL queries
- **Upload** — photo, video, reel, carousel upload
- **Location** — location search, nearby, feed
- **Collections** — saved collections management
- **Download** — media download with quality selection
- **Auth** — login, 2FA, session management
- **Export** — CSV/JSON data export
- **Analytics** — engagement rate, posting times, content analysis
- **Scheduler** — scheduled post/story/reel publishing
- **Growth** — smart follow/unfollow system
- **Automation** — auto-comment, auto-like, story watching
- **Monitor** — account change monitoring
- **Bulk Download** — batch media download
- **Hashtag Research** — analysis & suggestions
- **Pipeline** — SQLite/JSONL data pipeline
- **AI Suggest** — AI hashtag/caption suggestions
- **Audience** — lookalike audience finder
- **Comment Manager** — filtering, sentiment, auto-reply
- **A/B Test** — testing framework
- **Public Data** — anonymous public data access (Supermetrics-style)

#### Async Support

- Full async parity: every sync module has an async counterpart
- `async with` context manager support
- `AsyncInstagram` client class

#### AI Agent System

- **InstaAgent**: Natural language interface for Instagram automation
- **13 AI Providers**: Gemini, OpenAI, Claude, DeepSeek, Qwen, Groq, Together, Mistral, Ollama, OpenRouter, Fireworks, Perplexity, xAI
- **3 Modes**: Login (full API), Anonymous (public only), Async (auto-await)
- **10 Built-in Tools**: code execution, file I/O, data analysis, charts, web search, media download, HTTP requests
- **Memory System**: Persistent conversation history with search
- **10 Task Templates**: Profile analysis, account comparison, follower export, best posting time, hashtag research, engagement report, content calendar, competitor analysis, post scraping, DM campaign
- **Plugin System**: Custom tools with auto-schema generation
- **Cost Tracker**: Token usage monitoring with pricing for 30+ models
- **Vision**: Multimodal image analysis (GPT-4o, Gemini, Claude)
- **Streaming**: Real-time response output for CLI and Web
- **Webhook Notifications**: Telegram Bot, Discord, Email (SMTP), custom HTTP
- **Secure Sandbox**: Import whitelist, pattern blocking, timeout, namespace isolation
- **Permission System**: FULL_ACCESS, ASK_ONCE, ASK_EVERY
- **CLI Interface**: One-shot and interactive modes, parallel execution
- **Web UI**: FastAPI-based browser interface with REST API

#### Models & Type Safety

- Pydantic models: User, Media, Comment, Story, Highlight, DirectThread, DirectMessage, Location
- Public data models: PublicProfile, PublicPost, HashtagPost, ProfileSnapshot
- Full `py.typed` marker for IDE support

#### Infrastructure

- ChallengeHandler: Auto-resolve email/SMS/consent challenges
- AsyncChallengeHandler: Async version with sync+async callbacks
- Session Auto-Refresh: Auto-reload session on LoginRequired
- Rate Limiter: Sliding window per-category limits
- Event System: 10 event types with sync/async callbacks
- Dashboard: Real-time terminal stats
- Device Fingerprint: Realistic Android/iOS/Web fingerprints
- Email Verifier: Account verification support
- Smart Rotation Coordinator: Multi-proxy orchestration
- Multi-Account Manager: Parallel account management

#### Testing & CI/CD

- 475 tests — all passing
- pytest-cov with coverage thresholds
- GitHub Actions: lint, test (Python 3.10-3.12), security scan, package build

#### Documentation

- Full MkDocs Material documentation site
- Getting Started, API Reference, Tools, Advanced guides
- Live at <https://mpython77.github.io/instaapi/>

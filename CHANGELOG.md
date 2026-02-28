# Changelog

All notable changes to instaharvest_v2.

## [1.0.9] - 2026-02-28

### 🐛 Bug Fixes

- **Agent f-string crash**: Banned backslash `\` inside f-string braces — fixes `SyntaxError` on Python 3.10
- **Agent output language**: Enforced English-only in all `print()` statements (agent now outputs English labels: `Followers`, `Verified`, etc.)
- **Meta tag parsing**: Enhanced `_parse_meta_tags` with 3 new fallbacks:
  - Title-based follower/following/posts extraction
  - `og:description` fallback for biography
  - Full title text as biography when no other source found

---

## [1.0.8] - 2026-02-28

### 🌐 i18n: Full English Translation

- Translated **27 Uzbek text instances** to English across 5 files:
  - `stories.py` / `async_stories.py` — docstrings (`get_viewers`, `vote_poll`, `vote_slider`, `answer_quiz`)
  - `search.py` — class docstring, comments, section headers, error messages
  - `gemini_provider.py` — error messages and ImportError text
  - `openai_compatible.py` — error messages in `from_profile()`

---

## [1.0.7] - 2026-02-28

### ✨ Clean Agent TUI (Claude Code Style)

- **Eliminated duplicate code display**: `code` event now skipped entirely in CLI callback
- **Compact tool_call display**: Shows one-line description + dim API call subtext (e.g., `↳ ig.public.get_profile()`)
- **Result truncation**: `tool_result` capped at 15 lines max (10 in compact mode)
- **FallbackConsole**: Updated signature to match new `description` parameter

---

## [1.0.6] - 2026-02-28

### 🐛 Bug Fixes

- **`get_profile` returning zero counts**: Fixed field name mapping in agent knowledge base (`follower_count` → `followers`, `edge_followed_by.count` → `followers`)
- Updated API reference and code recipes in `knowledge.py` to use correct primary keys

---

## [1.0.5] - 2026-02-28

### 🐛 Bug Fixes

- **Stuck "Thinking..." spinner**: Fixed `Live` object leak in `tui.py` — `stop_thinking()` now called before creating new spinner
- **Agent hallucination**: Added strict anti-hallucination rules to system prompt — agent must only present actual code execution output
- **Default permission**: Changed from `ask_once` to `full_access` for smoother CLI experience
- **Max steps**: Increased agent `max_steps` from 15 to 25

---

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
- Live at <https://mpython77.github.io/instaharvest_v2/>

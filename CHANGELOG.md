# Changelog

All notable changes to InstaAPI.

## [3.0.0] - 2026-02-27

### Added — Full Async Parity & Testing Infrastructure

- **14 new async modules** — complete feature parity between sync and async:
  - `async_analytics.py` — engagement rate, posting times, content analysis
  - `async_discover.py` — similar user discovery
  - `async_export.py` — CSV/JSON export operations
  - `async_growth.py` — smart follow/unfollow system
  - `async_automation.py` — auto-comment, auto-like, story watching
  - `async_monitor.py` — account change monitoring
  - `async_bulk_download.py` — bulk media download
  - `async_hashtag_research.py` — hashtag analysis & suggestions
  - `async_pipeline.py` — SQLite/JSONL data pipeline
  - `async_ai_suggest.py` — AI hashtag/caption suggestions
  - `async_audience.py` — lookalike audience finder
  - `async_comment_manager.py` — comment filtering, sentiment, auto-reply
  - `async_ab_test.py` — A/B testing framework
  - `async_scheduler.py` — scheduled post/story/reel publishing

### Added — Testing & Quality

- **3 new test files**: `test_upload_api.py`, `test_direct_api.py`, `test_account_api.py`
- **pytest-cov configuration** in `pyproject.toml` with coverage thresholds
- **390 tests** — all passing
- **33.4% code coverage** — threshold enforced at 30%

### Added — CI/CD Pipeline

- **GitHub Actions** (`.github/workflows/ci.yml`):
  - Lint (flake8 + mypy)
  - Test (Python 3.10, 3.11, 3.12 matrix)
  - Security scan (bandit + safety)
  - Package build (build + twine check)
  - Benchmark automation on main branch

### Added — Performance Benchmarks

- **`benchmarks/benchmark.py`** — 8 automated benchmarks:
  - Import time: ~170ms
  - Pydantic model parsing: 190,840 ops/sec
  - AntiDetect init: 0.2ms
  - Rate limiter: 546,448 ops/sec
  - API init (12 modules): 1.0ms
  - AI keyword extraction: 4,912 ops/sec
  - Memory footprint: 0.5KB peak

### Changed

- **README.md** — full rewrite with all new modules, tools, benchmarks
- **docs/index.md** — updated feature cards and async parity
- **pyproject.toml** — added `[tool.coverage]` sections
- Module count: 17 sync → 32 sync + 32 async

## [2.0.0] - 2026-02-26

### Added — AI Agent (Major Feature)

- **InstaAgent**: Natural language interface for Instagram automation
- **13 AI Providers**: Gemini, OpenAI, Claude, DeepSeek, Qwen, Groq, Together, Mistral, Ollama, OpenRouter, Fireworks, Perplexity, xAI
- **3 Modes**: Login (full API), Anonymous (public only), Async (auto-await)
- **10 Built-in Tools**: code execution, file I/O, data analysis, charts, web search, media download, HTTP requests
- **Memory System** (`memory.py`): Persistent conversation history with search and session management
- **10 Task Templates** (`templates.py`): Profile analysis, account comparison, follower export, best posting time, hashtag research, engagement report, content calendar, competitor analysis, post scraping, DM campaign
- **Plugin System** (`plugins.py`): Register custom tools with auto-schema generation
- **Cost Tracker** (`cost_tracker.py`): Token usage monitoring with pricing for 30+ models
- **Vision** (`vision.py`): Multimodal image analysis (OpenAI GPT-4o, Gemini, Claude)
- **Streaming** (`streaming.py`): Real-time response output for CLI and Web
- **Retry & Recovery** (`retry.py`): Exponential backoff, rate limit detection, provider fallback chain
- **Webhook Notifications** (`webhook.py`): Telegram Bot, Discord, Email (SMTP), custom HTTP
- **Scheduler** (`scheduler.py`): Cron-like background task scheduling with persistence
- **Cross-Platform** (`compat.py`): Windows/Linux/macOS compatibility layer — safe paths, console encoding, atomic writes
- **CLI Interface** (`cli.py`): One-shot and interactive modes, parallel execution
- **Web UI** (`web.py`): FastAPI-based browser interface with REST API
- **Secure Sandbox** (`executor.py`): Import whitelist, pattern blocking, timeout, namespace isolation
- **Permission System** (`permissions.py`): FULL_ACCESS, ASK_ONCE, ASK_EVERY

### Documentation

- **5 new docs**: `agent/overview.md`, `agent/features.md`, `agent/interfaces.md`, `agent/architecture.md`, `agent/providers.md`
- Updated `docs/index.md` with AI Agent feature card and code example

## [1.5.0] - 2026-02-22

### Added

- **Session convenience**: `ig.save_session()`, `ig.load_session()`, `Instagram.from_session_file()`
- **Proxy Health Checker**: Background daemon auto-checks proxy health (`proxy_health.py`)
- **Rate Limit Dashboard**: Real-time terminal stats (`ig.dashboard.show()`)
- **Plugin System**: Extensible hooks (`ig.use(MyPlugin())`) with lifecycle events
- **Story Composer**: Builder-pattern story creation (`ig.compose_story().image().text().build().publish()`)
- **Async Challenge Tests**: `test_async_challenge.py` with `pytest-asyncio`
- **Integration Tests**: Mock-based full flow tests (`test_integration.py`)

## [1.4.0] - 2026-02-22

### Added

- **RetryConfig**: Configurable retry with exponential backoff, jitter ±30%, ceiling
- **LogConfig**: Centralized logging (console + rotating file + silence)
- **EventEmitter**: 10 event types, sync/async callbacks, error-safe
- Event emissions in `client.py` for RATE_LIMIT, NETWORK_ERROR, RETRY
- `ig.on()` / `ig.off()` event convenience methods
- 37 new unit tests (total: 86)

## [1.3.0] - 2026-02-21

### Added

- **ChallengeHandler**: Auto-resolve email/SMS/consent challenges
- **AsyncChallengeHandler**: Async version with sync+async callback support
- **Session Auto-Refresh**: Auto-reload session file on LoginRequired
- PyPI packaging (`pyproject.toml`, `LICENSE`, `MANIFEST.in`, `py.typed`)
- Comprehensive `README.md` with badges, API reference, examples
- **Feed API Models**: `get_all_posts()` returns `List[MediaModel]`
- **Pytest suite**: 49 tests for models, challenges, response handler
- `ChallengeRequired.challenge_url` / `.challenge_type` properties

## [1.2.0] - 2026-02-20

### Added

- **AsyncInstagram**: Full async support with `curl_cffi.AsyncSession`
- **Batch API**: Parallel operations (users, media, friendships)
- **Speed Modes**: safe/normal/aggressive/turbo presets
- All 17 API modules mirrored for async
- `async with` context manager support

## [1.1.0] - 2026-02-19

### Added

- **17 API Modules**: users, media, feed, search, hashtags, friendships, direct, stories, insights, account, notifications, graphql, upload, location, collections, download, auth
- **Pydantic Models**: User, Media, Comment, Story, Highlight, etc.
- **ProxyManager**: Weighted/round-robin/random rotation with scoring
- **RateLimiter**: Sliding window per-category limits
- **AntiDetect**: Fingerprint rotation, human-like delays
- **AnonClient**: Anonymous public API access

## [1.0.0] - 2026-02-18

### Added

- Initial release
- Core HTTP client with `curl_cffi` engine
- Session management with cookie rotation
- Basic Instagram API wrapper

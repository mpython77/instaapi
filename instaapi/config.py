"""
Instagram API Configuration and Constants
"""

# ============================================================
# API Base
# ============================================================
BASE_URL = "https://www.instagram.com"
API_BASE = f"{BASE_URL}/api/v1"

# Instagram Web App ID (required for all requests)
# Captured from real browser traffic via mitmproxy
IG_APP_ID = "1217981644879628"

# Mobile API App ID (for i.instagram.com endpoints)
IG_APP_ID_MOBILE = "936619743392459"

# ============================================================
# Browser Impersonation list (for curl_cffi)
# ============================================================
BROWSER_IMPERSONATIONS = [
    "chrome142",
    "chrome136",
    "chrome131",
]

# ============================================================
# User-Agent list (for random rotation)
# ============================================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

# ============================================================
# Accept-Language variants
# ============================================================
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en-US,en;q=0.9,ru;q=0.8",
    "en,en-US;q=0.9",
    "en-US,en;q=0.9,es;q=0.8",
]

# ============================================================
# Sec-Ch-Ua variants
# ============================================================
SEC_CH_UA_VARIANTS = [
    '"Not A Brand";v="99", "Google Chrome";v="142", "Chromium";v="142"',
    '"Chromium";v="136", "Not A Brand";v="99", "Google Chrome";v="136"',
]

# ============================================================
# Rate Limiting settings (in seconds)
# ============================================================
RATE_LIMITS = {
    # GET requests - softer limits
    "get_default": {"calls": 30, "period": 60},
    "get_profile": {"calls": 20, "period": 60},
    "get_feed": {"calls": 15, "period": 60},
    "get_followers": {"calls": 10, "period": 60},
    "get_search": {"calls": 20, "period": 60},
    "get_stories": {"calls": 15, "period": 60},
    "get_direct": {"calls": 10, "period": 60},
    # POST requests - stricter limits
    "post_like": {"calls": 30, "period": 3600},
    "post_comment": {"calls": 15, "period": 3600},
    "post_follow": {"calls": 20, "period": 3600},
    "post_dm": {"calls": 10, "period": 3600},
    "post_default": {"calls": 20, "period": 3600},
}

# ============================================================
# Request delays (in seconds, min-max)
# ============================================================
REQUEST_DELAYS = {
    "min": 0.5,
    "max": 2.0,
    "after_action": {"min": 1.0, "max": 3.0},  # after like, follow, comment
    "after_error": {"min": 3.0, "max": 8.0},   # after error
    "after_rate_limit": {"min": 30.0, "max": 60.0},  # after 429
}

# ============================================================
# Retry settings
# ============================================================
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2.0  # exponential backoff
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

# ============================================================
# Timeout (in seconds)
# ============================================================
REQUEST_TIMEOUT = 15
CONNECT_TIMEOUT = 10

# ============================================================
# Proxy settings
# ============================================================
PROXY_HEALTH_CHECK_INTERVAL = 300  # check every 5 minutes
PROXY_MAX_FAILURES = 3  # remove proxy after this many failures
PROXY_MIN_SCORE = 0.3  # replace proxies below this score

# ============================================================
# Anonymous scraping settings
# ============================================================

# Rate limits per strategy (requests per window)
ANON_RATE_LIMITS = {
    "html_parse": {"requests": 10, "window": 60},
    "embed": {"requests": 20, "window": 60},
    "graphql": {"requests": 8, "window": 60},
    "mobile_api": {"requests": 12, "window": 60},
    "web_api": {"requests": 10, "window": 60},
}

# Unlimited — no rate limits at all
ANON_RATE_LIMITS_UNLIMITED = {
    "html_parse": {"requests": 999999, "window": 1},
    "embed": {"requests": 999999, "window": 1},
    "graphql": {"requests": 999999, "window": 1},
    "mobile_api": {"requests": 999999, "window": 1},
    "web_api": {"requests": 999999, "window": 1},
}

# Public GraphQL query hashes (may change periodically)
ANON_GRAPHQL_HASHES = {
    "user_posts": "69cba40317214236af40e7efa697781d",
    "post_comments": "bc3296d1ce80a24b1b6e40b1e72903f5",
    "hashtag_posts": "174a21c722f79e55ab5b4b94f8c49ae1",
    "user_info": "c9100bf9110dd6361671f113dd02e7d6",
    "post_info": "2b0673e0dc4580571e0d6623e10e557d",
}

# Embed endpoint
EMBED_URL = "https://www.instagram.com/p/{shortcode}/embed/captioned/"

# Mobile API base
MOBILE_API_BASE = "https://i.instagram.com/api/v1"

# Anonymous request delays (slower than authenticated)
ANON_REQUEST_DELAYS = {
    "min": 1.5,
    "max": 4.0,
    "after_error": {"min": 5.0, "max": 15.0},
    "after_rate_limit": {"min": 30.0, "max": 90.0},
}

# Unlimited — zero delays
ANON_REQUEST_DELAYS_UNLIMITED = {
    "min": 0.0,
    "max": 0.0,
    "after_error": {"min": 0.0, "max": 0.0},
    "after_rate_limit": {"min": 0.0, "max": 0.0},
}

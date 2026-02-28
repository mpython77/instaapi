"""
Anonymous Client
================
HTTP client for public Instagram data without authentication.
Uses 5 strategies with automatic fallback chain.

Strategy chain:
    1. Web HTML Parse — parse profile page for embedded JSON
    2. Embed Endpoint — /p/{shortcode}/embed/captioned/
    3. GraphQL Public — public query_hash queries
    4. Mobile API — i.instagram.com/api/v1
    5. Web API — www.instagram.com/api/v1 (no cookies)
"""

import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from curl_cffi import requests as curl_requests

from .anti_detect import AntiDetect
from .proxy_manager import ProxyManager
from .config import (
    ANON_RATE_LIMITS,
    ANON_RATE_LIMITS_UNLIMITED,
    ANON_GRAPHQL_HASHES,
    ANON_REQUEST_DELAYS,
    ANON_REQUEST_DELAYS_UNLIMITED,
    EMBED_URL,
    MOBILE_API_BASE,
    IG_APP_ID,
    GRAPHQL_DOC_IDS,
    GRAPHQL_LSD_TOKEN,
    MAX_RETRIES,
)

logger = logging.getLogger("instaapi.anon")


class AnonRateLimiter:
    """Simple per-strategy rate limiter for anonymous requests."""

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._windows: Dict[str, List[float]] = {}
        self._limits = ANON_RATE_LIMITS if enabled else ANON_RATE_LIMITS_UNLIMITED

    def check(self, strategy: str) -> bool:
        """Check if we can make a request. Returns True if allowed."""
        if not self._enabled:
            return True

        config = self._limits.get(strategy, {"requests": 10, "window": 60})
        now = time.time()
        window = config["window"]
        max_requests = config["requests"]

        if strategy not in self._windows:
            self._windows[strategy] = []

        # Clean old entries
        self._windows[strategy] = [
            t for t in self._windows[strategy] if now - t < window
        ]

        if len(self._windows[strategy]) >= max_requests:
            return False

        self._windows[strategy].append(now)
        return True

    def wait_if_needed(self, strategy: str) -> None:
        """Wait until a request slot is available."""
        if not self._enabled:
            return

        config = self._limits.get(strategy, {"requests": 10, "window": 60})
        while not self.check(strategy):
            time.sleep(config["window"] / config["requests"] + random.uniform(0.5, 2.0))


class AnonClient:
    """
    Anonymous HTTP client — no cookies, no session.

    Features:
        - 5 scraping strategies with automatic fallback
        - Shared anti-detect (fingerprint rotation)
        - Shared proxy rotation
        - Independent rate limiting per strategy
        - Human-like delays (disabled in unlimited mode)
        - unlimited=True — raw speed, no throttling
    """

    def __init__(
        self,
        anti_detect: Optional[AntiDetect] = None,
        proxy_manager: Optional[ProxyManager] = None,
        unlimited: bool = False,
    ):
        self._anti_detect = anti_detect or AntiDetect()
        self._proxy_mgr = proxy_manager
        self._unlimited = unlimited
        self._rate_limiter = AnonRateLimiter(enabled=not unlimited)
        self._delays = ANON_REQUEST_DELAYS_UNLIMITED if unlimited else ANON_REQUEST_DELAYS
        self._request_count = 0
        self._error_count = 0

    # ═══════════════════════════════════════════════════════════
    # CORE HTTP — anonymous requests via curl_cffi
    # ═══════════════════════════════════════════════════════════

    def _request(
        self,
        url: str,
        strategy: str,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        parse_json: bool = True,
        timeout: int = 15,
    ) -> Any:
        """
        Send anonymous HTTP request with anti-detect and proxy.

        Returns parsed JSON dict or raw response text.
        Raises on HTTP errors (429, 401, etc).
        """
        identity = self._anti_detect.get_identity()

        # Build headers
        req_headers = {
            "user-agent": identity.user_agent,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "accept-language": identity.accept_language,
            "accept-encoding": "gzip, deflate, br",
            "cache-control": "no-cache",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }
        if identity.sec_ch_ua:
            req_headers["sec-ch-ua"] = identity.sec_ch_ua
            req_headers["sec-ch-ua-mobile"] = identity.sec_ch_ua_mobile
            req_headers["sec-ch-ua-platform"] = identity.sec_ch_ua_platform

        if headers:
            req_headers.update(headers)

        # Proxy
        proxy = None
        proxy_info = None
        if self._proxy_mgr and self._proxy_mgr.active_count > 0:
            proxy_info = self._proxy_mgr.get_proxy()
            if proxy_info:
                proxy = proxy_info  # get_proxy() returns string URL

        # Human delay (skipped in unlimited mode)
        self._human_delay()

        # Rate limit check (skipped in unlimited mode)
        self._rate_limiter.wait_if_needed(strategy)

        kwargs = {
            "url": url,
            "headers": req_headers,
            "timeout": timeout,
            "impersonate": identity.impersonation,
            "allow_redirects": True,
            "verify": False,  # Required for proxy SSL
        }
        if params:
            kwargs["params"] = params
        if proxy:
            kwargs["proxies"] = {"https": proxy, "http": proxy}

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = curl_requests.get(**kwargs)
                self._request_count += 1

                # Report proxy success with response time
                elapsed = response.elapsed if hasattr(response, 'elapsed') else 0.0
                if proxy_info:
                    self._proxy_mgr.report_success(proxy_info, elapsed)

                # Check status
                if response.status_code == 429:
                    logger.warning(f"[Anon] Rate limited on {strategy}, attempt {attempt + 1}")
                    self._anti_detect.on_error("rate_limit")
                    wait = random.uniform(
                        self._delays["after_rate_limit"]["min"],
                        self._delays["after_rate_limit"]["max"],
                    )
                    if wait > 0:
                        time.sleep(wait)
                    # Update identity for retry
                    identity = self._anti_detect.get_identity()
                    kwargs["headers"]["user-agent"] = identity.user_agent
                    kwargs["impersonate"] = identity.impersonation
                    continue

                if response.status_code == 404:
                    return None

                if response.status_code in (401, 403):
                    # Retry with new proxy + identity (proxy may be blocked)
                    if attempt < MAX_RETRIES and self._proxy_mgr and self._proxy_mgr.active_count > 0:
                        logger.debug(f"[Anon] Auth {response.status_code} on {strategy}, retrying with new proxy...")
                        if proxy_info:
                            self._proxy_mgr.report_failure(proxy_info)
                        proxy_info = self._proxy_mgr.get_proxy()
                        if proxy_info:
                            kwargs["proxies"] = {"https": proxy_info, "http": proxy_info}
                        identity = self._anti_detect.get_identity()
                        kwargs["headers"]["user-agent"] = identity.user_agent
                        kwargs["impersonate"] = identity.impersonation
                        err_wait = self._delays.get("after_error", {})
                        if err_wait.get("max", 0) > 0:
                            time.sleep(random.uniform(err_wait.get("min", 0.5), err_wait["max"]))
                        continue
                    # No retries left or no proxies
                    logger.debug(f"[Anon] Auth required on {strategy}: {response.status_code}")
                    raise StrategyFailed(f"Auth required: {response.status_code}")

                if response.status_code >= 500:
                    logger.warning(f"[Anon] Server error {response.status_code} on {strategy}")
                    time.sleep(random.uniform(2, 5))
                    continue

                response.raise_for_status()

                if parse_json:
                    return response.json()
                return response.text

            except StrategyFailed:
                raise
            except Exception as e:
                last_error = e
                self._error_count += 1
                if proxy_info:
                    self._proxy_mgr.report_failure(proxy_info)
                self._anti_detect.on_error("network")
                if attempt < MAX_RETRIES:
                    err_min = self._delays["after_error"]["min"]
                    err_max = self._delays["after_error"]["max"]
                    if err_max > 0:
                        time.sleep(random.uniform(err_min, err_max))
                    # Get new proxy for retry
                    if self._proxy_mgr and self._proxy_mgr.active_count > 0:
                        proxy_info = self._proxy_mgr.get_proxy()
                        if proxy_info:
                            kwargs["proxies"] = {"https": proxy_info, "http": proxy_info}

        raise StrategyFailed(f"All attempts failed for {strategy}: {last_error}")

    def _human_delay(self) -> None:
        """Natural delay between requests. Skipped in unlimited mode."""
        if self._unlimited:
            return

        min_d = self._delays["min"]
        max_d = self._delays["max"]
        if max_d <= 0:
            return

        mean = (min_d + max_d) / 2
        std = (max_d - min_d) / 4
        delay = max(min_d, random.gauss(mean, std))
        delay = min(delay, max_d * 1.5)
        # 5% chance of longer pause (natural behavior)
        if random.random() < 0.05:
            delay += random.uniform(3.0, 8.0)
        time.sleep(delay)

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 1: HTML Page Parse
    # ═══════════════════════════════════════════════════════════

    def get_profile_html(self, username: str) -> Optional[Dict]:
        """
        Parse Instagram profile page HTML for embedded JSON data.

        Looks for:
        1. window._sharedData = {...}
        2. window.__additionalDataLoaded(..., {...})
        3. <script type="application/ld+json">
        4. Meta tags (og:title, og:description, og:image)
        """
        url = f"https://www.instagram.com/{username}/"
        try:
            html = self._request(url, "html_parse", parse_json=False)
        except StrategyFailed:
            return None

        if not html:
            return None

        # Check for login redirect
        if '"LoginAndSignupPage"' in html or "login/?next=" in html:
            logger.debug("[Anon] HTML parse: login redirect detected")
            return None

        result = {}

        # Method 1: window._sharedData
        shared_data_match = re.search(
            r'window\._sharedData\s*=\s*({.+?})\s*;</script>',
            html, re.DOTALL
        )
        if shared_data_match:
            try:
                shared = json.loads(shared_data_match.group(1))
                user_data = (
                    shared.get("entry_data", {})
                    .get("ProfilePage", [{}])[0]
                    .get("graphql", {})
                    .get("user", {})
                )
                if user_data:
                    result = self._parse_graphql_user(user_data)
            except (json.JSONDecodeError, IndexError, KeyError):
                pass

        # Method 2: window.__additionalDataLoaded
        if not result:
            additional_match = re.search(
                r'window\.__additionalDataLoaded\s*\(\s*[\'"].*?[\'"]\s*,\s*({.+?})\s*\)\s*;',
                html, re.DOTALL
            )
            if additional_match:
                try:
                    data = json.loads(additional_match.group(1))
                    user_data = data.get("graphql", {}).get("user", {})
                    if not user_data:
                        user_data = data.get("user", {})
                    if user_data:
                        result = self._parse_graphql_user(user_data)
                except (json.JSONDecodeError, KeyError):
                    pass

        # Method 3: JSON-LD schema
        if not result:
            ld_match = re.search(
                r'<script type="application/ld\+json">\s*({.+?})\s*</script>',
                html, re.DOTALL
            )
            if ld_match:
                try:
                    ld = json.loads(ld_match.group(1))
                    result = {
                        "username": ld.get("alternateName", "").lstrip("@"),
                        "full_name": ld.get("name", ""),
                        "biography": ld.get("description", ""),
                        "profile_pic_url": ld.get("image", ""),
                        "url": ld.get("url", ""),
                    }
                except json.JSONDecodeError:
                    pass

        # Method 4: Meta tags fallback
        if not result:
            result = self._parse_meta_tags(html)

        if result:
            result["_strategy"] = "html_parse"
            result["_username"] = username

        return result if result else None

    def _parse_meta_tags(self, html: str) -> Dict:
        """
        Extract profile data from meta tags and title.

        Current Instagram HTML format (2024+):
        - <title>Full Name (&#064;username) • Instagram photos and videos</title>
        - Meta content contains: "NNN Followers, NNN Following, NNN Posts"
        - og:image has profile picture URL
        """
        import html as html_module
        data = {}

        # --- Username + Full name from <title> ---
        title_match = re.search(r'<title>([^<]*)</title>', html)
        if title_match:
            title_text = html_module.unescape(title_match.group(1))
            # Format: "Full Name (@username) • Instagram photos and videos"
            # or: "Full Name (@username) on Instagram • ..."
            name_match = re.search(r'^(.+?)\s*\(@(\w+)\)', title_text)
            if name_match:
                data["full_name"] = name_match.group(1).strip()
                data["username"] = name_match.group(2)

        # --- Followers/Following/Posts from ALL meta content attributes ---
        # Instagram splits data across multiple meta tags, so scan all content values
        all_content = " ".join(re.findall(r'content="([^"]*)"', html))
        all_content = html_module.unescape(all_content)

        # Parse counts — handle formats: "642 Following" "4,015 Posts" "777M Followers"
        followers_m = re.search(r'([\d,.]+[KMBkmb]?)\s*Followers', all_content, re.IGNORECASE)
        following_m = re.search(r'([\d,.]+[KMBkmb]?)\s*Following', all_content, re.IGNORECASE)
        posts_m = re.search(r'([\d,.]+[KMBkmb]?)\s*Posts', all_content, re.IGNORECASE)

        if followers_m:
            data["followers"] = self._parse_count(followers_m.group(1))
        if following_m:
            data["following"] = self._parse_count(following_m.group(1))
        if posts_m:
            data["posts_count"] = self._parse_count(posts_m.group(1))

        # --- Bio from description ---
        # Bio usually appears after "Posts" or after a dash
        desc_match = re.search(r'<meta[^>]+(?:name|property)="description"[^>]+content="([^"]*)"', html)
        if not desc_match:
            desc_match = re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:name|property)="description"', html)
        if desc_match:
            desc = html_module.unescape(desc_match.group(1))
            # Bio text is often after "Posts - " or "Posts – "
            bio_match = re.search(r'Posts\s*[-–—:]\s*(.*)', desc, re.DOTALL)
            if bio_match:
                bio = bio_match.group(1).strip()
                if bio:
                    data["biography"] = bio

        # --- Profile picture from og:image ---
        og_image = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]*)"', html)
        if not og_image:
            og_image = re.search(r'<meta[^>]+content="([^"]*)"[^>]+property="og:image"', html)
        if og_image:
            data["profile_pic_url"] = html_module.unescape(og_image.group(1))

        return data

    def _parse_count(self, text: str) -> int:
        """Parse follower count text: '1.2M' -> 1200000."""
        text = text.replace(",", "").strip()
        multiplier = 1
        if text.endswith(("K", "k")):
            multiplier = 1000
            text = text[:-1]
        elif text.endswith(("M", "m")):
            multiplier = 1000000
            text = text[:-1]
        try:
            return int(float(text) * multiplier)
        except ValueError:
            return 0

    def _parse_graphql_user(self, user: Dict) -> Dict:
        """Parse GraphQL user object into clean format."""
        edges_media = user.get("edge_owner_to_timeline_media", {})
        return {
            "user_id": user.get("id"),
            "username": user.get("username"),
            "full_name": user.get("full_name"),
            "biography": user.get("biography"),
            "profile_pic_url": user.get("profile_pic_url"),
            "profile_pic_url_hd": user.get("profile_pic_url_hd"),
            "is_private": user.get("is_private", False),
            "is_verified": user.get("is_verified", False),
            "is_business": user.get("is_business_account", False),
            "category": user.get("category_name", ""),
            "external_url": user.get("external_url"),
            "followers": user.get("edge_followed_by", {}).get("count"),
            "following": user.get("edge_follow", {}).get("count"),
            "posts_count": edges_media.get("count"),
            "bio_links": user.get("bio_links", []),
            "pronouns": user.get("pronouns", []),
            "highlight_count": user.get("highlight_reel_count", 0),
            "recent_posts": self._parse_timeline_edges(edges_media.get("edges", [])),
        }

    def _parse_timeline_edges(self, edges: List[Dict]) -> List[Dict]:
        """Parse GraphQL timeline edges into post list (with carousel support)."""
        posts = []
        for edge in edges:
            node = edge.get("node", {})
            caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
            caption = caption_edges[0]["node"]["text"] if caption_edges else ""

            post = {
                "shortcode": node.get("shortcode"),
                "media_type": node.get("__typename"),
                "display_url": node.get("display_url"),
                "thumbnail_url": node.get("thumbnail_src"),
                "is_video": node.get("is_video", False),
                "likes": node.get("edge_liked_by", {}).get("count", 0),
                "comments": node.get("edge_media_to_comment", {}).get("count", 0),
                "caption": caption,
                "taken_at": node.get("taken_at_timestamp"),
                "pk": node.get("id"),
                "video_url": node.get("video_url"),
                "video_views": node.get("video_view_count"),
            }

            # Carousel (GraphSidecar) — parse all children
            sidecar = node.get("edge_sidecar_to_children", {})
            if sidecar:
                children = []
                for child_edge in sidecar.get("edges", []):
                    child = child_edge.get("node", {})
                    children.append({
                        "pk": child.get("id"),
                        "shortcode": child.get("shortcode"),
                        "display_url": child.get("display_url"),
                        "is_video": child.get("is_video", False),
                        "video_url": child.get("video_url"),
                        "media_type": child.get("__typename"),
                        # Multiple resolutions
                        "display_resources": [
                            {"url": r.get("src"), "width": r.get("config_width"), "height": r.get("config_height")}
                            for r in child.get("display_resources", [])
                        ],
                    })
                post["carousel_media"] = children
                post["carousel_count"] = len(children)

            posts.append(post)
        return posts

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 2: Embed Endpoint
    # ═══════════════════════════════════════════════════════════

    def get_embed_data(self, shortcode: str) -> Optional[Dict]:
        """
        Get post data from embed endpoint.
        Works without cookies — separate rate limits.
        """
        url = EMBED_URL.format(shortcode=shortcode)
        try:
            html = self._request(url, "embed", parse_json=False)
        except StrategyFailed:
            return None

        if not html:
            return None

        result = {}

        # Extract JSON from embed HTML
        # Look for media data in embedded script
        media_match = re.search(
            r'window\.__additionalDataLoaded\s*\(\s*[\'"]extra[\'"]\s*,\s*({.+?})\s*\)',
            html, re.DOTALL
        )
        if media_match:
            try:
                data = json.loads(media_match.group(1))
                shortcode_media = data.get("shortcode_media", {})
                if shortcode_media:
                    result = self._parse_embed_media(shortcode_media)
            except json.JSONDecodeError:
                pass

        # Fallback: parse embed HTML directly
        if not result:
            result = self._parse_embed_html(html, shortcode)

        if result:
            result["_strategy"] = "embed"
            result["shortcode"] = shortcode

        return result if result else None

    def _parse_embed_media(self, media: Dict) -> Dict:
        """Parse shortcode_media from embed data."""
        owner = media.get("owner", {})
        caption_edges = media.get("edge_media_to_caption", {}).get("edges", [])
        caption = caption_edges[0]["node"]["text"] if caption_edges else ""

        # Media URLs
        images = []
        if media.get("display_url"):
            images.append({"url": media["display_url"]})
        for res in media.get("display_resources", []):
            images.append({
                "url": res.get("src"),
                "width": res.get("config_width"),
                "height": res.get("config_height"),
            })

        return {
            "pk": media.get("id"),
            "shortcode": media.get("shortcode"),
            "media_type": media.get("__typename"),
            "is_video": media.get("is_video", False),
            "caption": caption,
            "likes": media.get("edge_media_preview_like", {}).get("count", 0),
            "comments_count": media.get("edge_media_preview_comment", {}).get("count", 0) or
                              media.get("edge_media_to_parent_comment", {}).get("count", 0),
            "taken_at": media.get("taken_at_timestamp"),
            "owner": {
                "username": owner.get("username"),
                "pk": owner.get("id"),
                "is_verified": owner.get("is_verified"),
                "profile_pic_url": owner.get("profile_pic_url"),
            },
            "images": images,
            "video_url": media.get("video_url"),
            "video_views": media.get("video_view_count"),
        }

    def _parse_embed_html(self, html: str, shortcode: str) -> Dict:
        """Fallback: parse embed HTML tags."""
        data = {"shortcode": shortcode}

        # Caption from embed
        caption_match = re.search(
            r'<div class="Caption"[^>]*>.*?<div class="CaptionTextContainer"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )
        if caption_match:
            caption_html = caption_match.group(1)
            # Strip HTML tags
            data["caption"] = re.sub(r'<[^>]+>', '', caption_html).strip()

        # Username
        user_match = re.search(r'<a[^>]*class="UserName"[^>]*>([^<]+)</a>', html)
        if user_match:
            data["owner"] = {"username": user_match.group(1).strip()}

        # Like count
        likes_match = re.search(r'<button[^>]*>.*?([\d,]+)\s*likes?', html, re.DOTALL | re.IGNORECASE)
        if likes_match:
            data["likes"] = int(likes_match.group(1).replace(",", ""))

        # Image
        img_match = re.search(r'<img[^>]+class="[^"]*EmbeddedMedia[^"]*"[^>]+src="([^"]+)"', html)
        if img_match:
            data["images"] = [{"url": img_match.group(1)}]

        return data if len(data) > 1 else {}

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 3a: GraphQL doc_id (cookie-free, POST /api/graphql)
    # ═══════════════════════════════════════════════════════════

    def _request_post(
        self,
        url: str,
        strategy: str,
        headers: Optional[Dict] = None,
        data: Optional[Dict] = None,
        timeout: int = 15,
    ) -> Any:
        """
        Send anonymous POST request with anti-detect and proxy.
        Used for GraphQL doc_id endpoint which requires POST.
        """
        identity = self._anti_detect.get_identity()

        req_headers = {
            "user-agent": identity.user_agent,
            "accept": "*/*",
            "accept-language": identity.accept_language,
            "accept-encoding": "gzip, deflate, br",
            "content-type": "application/x-www-form-urlencoded",
            "x-ig-app-id": IG_APP_ID,
            "x-fb-lsd": GRAPHQL_LSD_TOKEN,
            "x-asbd-id": "129477",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "referer": "https://www.instagram.com/",
            "origin": "https://www.instagram.com",
        }
        if identity.sec_ch_ua:
            req_headers["sec-ch-ua"] = identity.sec_ch_ua
            req_headers["sec-ch-ua-mobile"] = identity.sec_ch_ua_mobile
            req_headers["sec-ch-ua-platform"] = identity.sec_ch_ua_platform
        if headers:
            req_headers.update(headers)

        # Proxy
        proxy = None
        if self._proxy_mgr and self._proxy_mgr.active_count > 0:
            proxy = self._proxy_mgr.get_proxy()

        self._human_delay()
        self._rate_limiter.wait_if_needed(strategy)

        kwargs = {
            "url": url,
            "headers": req_headers,
            "data": data or {},
            "timeout": timeout,
            "impersonate": identity.impersonation,
            "allow_redirects": True,
            "verify": False,
        }
        if proxy:
            kwargs["proxies"] = {"https": proxy, "http": proxy}

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = curl_requests.post(**kwargs)
                self._request_count += 1

                if response.status_code == 429:
                    logger.warning(f"[Anon] Rate limited on {strategy} POST")
                    self._anti_detect.on_error("rate_limit")
                    wait = random.uniform(
                        self._delays["after_rate_limit"]["min"],
                        self._delays["after_rate_limit"]["max"],
                    )
                    if wait > 0:
                        time.sleep(wait)
                    identity = self._anti_detect.get_identity()
                    kwargs["headers"]["user-agent"] = identity.user_agent
                    kwargs["impersonate"] = identity.impersonation
                    continue

                if response.status_code == 404:
                    return None

                if response.status_code in (401, 403):
                    raise StrategyFailed(f"Auth required: {response.status_code}")

                if response.status_code >= 500:
                    time.sleep(random.uniform(2, 5))
                    continue

                response.raise_for_status()
                return response.json()

            except StrategyFailed:
                raise
            except Exception as e:
                last_error = e
                self._error_count += 1
                self._anti_detect.on_error("network")
                if attempt < MAX_RETRIES:
                    err_min = self._delays["after_error"]["min"]
                    err_max = self._delays["after_error"]["max"]
                    if err_max > 0:
                        time.sleep(random.uniform(err_min, err_max))

        raise StrategyFailed(f"All POST attempts failed for {strategy}: {last_error}")

    def get_graphql_docid(
        self,
        shortcode: str,
    ) -> Optional[Dict]:
        """
        Get post/reel data via GraphQL doc_id API (cookie-free!).

        Uses Instagram's internal GraphQL POST endpoint with doc_id.
        No cookies or authentication required.

        Args:
            shortcode: Post or reel shortcode

        Returns:
            Parsed media dict or None
        """
        doc_id = GRAPHQL_DOC_IDS.get("media_shortcode")
        if not doc_id:
            return None

        url = "https://www.instagram.com/api/graphql"
        post_data = {
            "variables": json.dumps({"shortcode": shortcode}),
            "doc_id": doc_id,
            "lsd": GRAPHQL_LSD_TOKEN,
        }

        try:
            data = self._request_post(
                url, "graphql_docid",
                data=post_data,
            )
        except StrategyFailed:
            return None

        if not data or not isinstance(data, dict):
            return None

        # Parse response — structure: data.xdt_shortcode_media
        media = (
            data.get("data", {})
            .get("xdt_shortcode_media")
        )
        if not media:
            return None

        return self._parse_graphql_docid_media(media)

    def _parse_graphql_docid_media(self, media: Dict) -> Dict:
        """
        Parse xdt_shortcode_media from GraphQL doc_id response.

        Returns a standardized dict compatible with other strategies.
        """
        owner = media.get("owner", {})
        caption_edges = media.get("edge_media_to_caption", {}).get("edges", [])
        caption = caption_edges[0]["node"]["text"] if caption_edges else ""

        result = {
            "_strategy": "graphql_docid",
            "pk": media.get("id"),
            "shortcode": media.get("shortcode"),
            "media_type": media.get("__typename"),
            "product_type": media.get("product_type"),
            "is_video": media.get("is_video", False),
            "caption": caption,
            "likes": (
                media.get("edge_media_preview_like", {}).get("count", 0)
            ),
            "comments_count": (
                media.get("edge_media_preview_comment", {}).get("count", 0)
                or media.get("edge_media_to_parent_comment", {}).get("count", 0)
            ),
            "taken_at": media.get("taken_at_timestamp"),
            "display_url": media.get("display_url"),
            "thumbnail_src": media.get("thumbnail_src"),
            "dimensions": media.get("dimensions"),
            "owner": {
                "pk": owner.get("id"),
                "username": owner.get("username"),
                "full_name": owner.get("full_name"),
                "is_verified": owner.get("is_verified"),
                "is_private": owner.get("is_private"),
                "profile_pic_url": owner.get("profile_pic_url"),
                "followers": owner.get("edge_followed_by", {}).get("count"),
                "posts_count": owner.get("edge_owner_to_timeline_media", {}).get("count"),
            },
            # Video-specific
            "video_url": media.get("video_url"),
            "video_view_count": media.get("video_view_count"),
            "video_play_count": media.get("video_play_count"),
            "video_duration": media.get("video_duration"),
            "has_audio": media.get("has_audio"),
            # Display resources (multiple resolutions)
            "display_resources": [
                {
                    "url": r.get("src"),
                    "width": r.get("config_width"),
                    "height": r.get("config_height"),
                }
                for r in media.get("display_resources", [])
            ],
            # Location
            "location": media.get("location"),
            "is_paid_partnership": media.get("is_paid_partnership"),
        }

        # Music info for reels
        music = media.get("clips_music_attribution_info")
        if music:
            result["audio"] = {
                "title": music.get("song_name"),
                "artist": music.get("artist_name"),
                "audio_id": music.get("audio_id"),
                "uses_original_audio": music.get("uses_original_audio"),
            }

        # Carousel (sidecar)
        sidecar = media.get("edge_sidecar_to_children")
        if sidecar:
            children = []
            for edge in sidecar.get("edges", []):
                child = edge.get("node", {})
                children.append({
                    "pk": child.get("id"),
                    "shortcode": child.get("shortcode"),
                    "display_url": child.get("display_url"),
                    "is_video": child.get("is_video", False),
                    "video_url": child.get("video_url"),
                    "media_type": child.get("__typename"),
                    "dimensions": child.get("dimensions"),
                    "display_resources": [
                        {
                            "url": r.get("src"),
                            "width": r.get("config_width"),
                            "height": r.get("config_height"),
                        }
                        for r in child.get("display_resources", [])
                    ],
                })
            result["carousel_media"] = children
            result["carousel_count"] = len(children)

        return result

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 3b: GraphQL Public Queries (query_hash)
    # ═══════════════════════════════════════════════════════════

    def get_graphql_public(
        self,
        query_hash: str,
        variables: Dict,
    ) -> Optional[Dict]:
        """
        Public GraphQL query (no auth required for some queries).
        """
        url = "https://www.instagram.com/graphql/query/"
        params = {
            "query_hash": query_hash,
            "variables": json.dumps(variables, separators=(",", ":")),
        }
        extra_headers = {
            "x-ig-app-id": IG_APP_ID,
            "x-requested-with": "XMLHttpRequest",
            "referer": "https://www.instagram.com/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

        try:
            data = self._request(
                url, "graphql",
                headers=extra_headers,
                params=params,
                parse_json=True,
            )
        except StrategyFailed:
            return None

        if data and isinstance(data, dict):
            return data.get("data", data)

        return None

    def get_user_posts_graphql(
        self,
        user_id: str,
        first: int = 12,
        after: Optional[str] = None,
    ) -> Optional[Dict]:
        """Fetch user posts via public GraphQL."""
        variables = {"id": str(user_id), "first": first}
        if after:
            variables["after"] = after

        query_hash = ANON_GRAPHQL_HASHES.get("user_posts", "")
        data = self.get_graphql_public(query_hash, variables)
        if data:
            return data.get("user", {}).get("edge_owner_to_timeline_media", {})
        return None

    def get_post_comments_graphql(
        self,
        shortcode: str,
        first: int = 24,
        after: Optional[str] = None,
    ) -> Optional[Dict]:
        """Fetch post comments via public GraphQL."""
        variables = {"shortcode": shortcode, "first": first}
        if after:
            variables["after"] = after

        query_hash = ANON_GRAPHQL_HASHES.get("post_comments", "")
        data = self.get_graphql_public(query_hash, variables)
        if data:
            return data.get("shortcode_media", {}).get("edge_media_to_parent_comment", {})
        return None

    def get_hashtag_posts_graphql(
        self,
        tag_name: str,
        first: int = 12,
        after: Optional[str] = None,
    ) -> Optional[Dict]:
        """Fetch hashtag posts via public GraphQL."""
        variables = {"tag_name": tag_name, "first": first}
        if after:
            variables["after"] = after

        query_hash = ANON_GRAPHQL_HASHES.get("hashtag_posts", "")
        data = self.get_graphql_public(query_hash, variables)
        if data:
            return data.get("hashtag", {})
        return None

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 4: Mobile API (i.instagram.com)
    # ═══════════════════════════════════════════════════════════

    def get_mobile_api(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Fetch data from mobile API (i.instagram.com).
        Different rate limits and sometimes looser auth requirements.
        """
        url = f"{MOBILE_API_BASE}{endpoint}"
        extra_headers = {
            "accept": "*/*",
            "x-ig-app-id": "936619743392459",  # Instagram Android app ID
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "referer": "https://www.instagram.com/",
        }

        try:
            return self._request(
                url, "mobile_api",
                headers=extra_headers,
                params=params,
                parse_json=True,
            )
        except StrategyFailed:
            return None

    def get_user_info_mobile(self, user_id: int | str) -> Optional[Dict]:
        """Get user info via mobile API."""
        data = self.get_mobile_api(f"/users/{user_id}/info/")
        if data and isinstance(data, dict):
            return data.get("user", data)
        return None

    def get_user_feed_mobile(
        self,
        user_id: int | str,
        max_id: Optional[str] = None,
        count: int = 12,
    ) -> Optional[Dict]:
        """
        Get user feed (posts) via mobile API.

        This endpoint returns richer post data than web_profile_info:
        - like_count, comment_count
        - carousel_media with all images/videos
        - video_url, video_duration
        - location info
        - usertags
        - caption with hashtags

        Args:
            user_id: Instagram user PK (numeric ID)
            max_id: Pagination cursor (from previous response's next_max_id)
            count: Number of posts to request (default 12)

        Returns:
            Dict with keys: items, next_max_id, more_available, num_results
            or None on failure
        """
        params = {"count": str(count)}
        if max_id:
            params["max_id"] = max_id

        data = self.get_mobile_api(f"/feed/user/{user_id}/", params=params)
        if data and isinstance(data, dict):
            items = data.get("items", [])
            return {
                "items": [self._parse_mobile_feed_item(item) for item in items],
                "next_max_id": data.get("next_max_id"),
                "more_available": data.get("more_available", False),
                "num_results": data.get("num_results", len(items)),
                "_raw_keys": list(data.keys()),
            }
        return None

    def get_media_info_mobile(self, media_id: int | str) -> Optional[Dict]:
        """
        Get single media info via mobile API.

        Args:
            media_id: Media PK (numeric ID)

        Returns:
            Parsed media dict or None
        """
        data = self.get_mobile_api(f"/media/{media_id}/info/")
        if data and isinstance(data, dict):
            items = data.get("items", [])
            if items:
                return self._parse_mobile_feed_item(items[0])
        return None

    def _parse_mobile_feed_item(self, item: Dict) -> Dict:
        """
        Parse mobile API feed item into clean format.

        Mobile API returns different field names than GraphQL:
        - like_count (not edge_liked_by)
        - comment_count (not edge_media_to_comment)
        - carousel_media (not edge_sidecar_to_children)
        - image_versions2 (not display_url)
        """
        # Caption
        caption_obj = item.get("caption") or {}
        caption_text = caption_obj.get("text", "") if isinstance(caption_obj, dict) else ""

        # Best image URL
        image_url = ""
        image_versions = item.get("image_versions2", {})
        candidates = image_versions.get("candidates", [])
        if candidates:
            # Eng katta razmerni tanlash
            best = max(candidates, key=lambda c: c.get("width", 0) * c.get("height", 0))
            image_url = best.get("url", "")

        # Media type mapping: 1=photo, 2=video, 8=carousel
        media_type_map = {1: "GraphImage", 2: "GraphVideo", 8: "GraphSidecar"}
        raw_type = item.get("media_type", 1)

        result = {
            "pk": str(item.get("pk", "")),
            "id": item.get("id"),
            "shortcode": item.get("code"),
            "media_type": media_type_map.get(raw_type, f"type_{raw_type}"),
            "media_type_raw": raw_type,
            "display_url": image_url,
            "is_video": raw_type == 2,
            "likes": item.get("like_count", 0),
            "comments": item.get("comment_count", 0),
            "caption": caption_text,
            "taken_at": item.get("taken_at"),
        }

        # Video data
        if raw_type == 2:
            video_versions = item.get("video_versions", [])
            if video_versions:
                result["video_url"] = video_versions[0].get("url", "")
            result["video_duration"] = item.get("video_duration")
            result["video_views"] = item.get("view_count") or item.get("play_count")

        # Carousel media
        carousel = item.get("carousel_media", [])
        if carousel:
            children = []
            for child in carousel:
                child_img = ""
                child_versions = child.get("image_versions2", {})
                child_candidates = child_versions.get("candidates", [])
                if child_candidates:
                    best_child = max(child_candidates, key=lambda c: c.get("width", 0) * c.get("height", 0))
                    child_img = best_child.get("url", "")

                child_data = {
                    "pk": str(child.get("pk", "")),
                    "display_url": child_img,
                    "is_video": child.get("media_type") == 2,
                    "media_type": media_type_map.get(child.get("media_type", 1), "unknown"),
                }

                # Child video
                if child.get("media_type") == 2:
                    child_vv = child.get("video_versions", [])
                    if child_vv:
                        child_data["video_url"] = child_vv[0].get("url", "")
                    child_data["video_duration"] = child.get("video_duration")

                children.append(child_data)

            result["carousel_media"] = children
            result["carousel_count"] = len(children)

        # Location
        location = item.get("location")
        if location and isinstance(location, dict):
            result["location"] = {
                "pk": location.get("pk"),
                "name": location.get("name"),
                "city": location.get("city"),
                "lat": location.get("lat"),
                "lng": location.get("lng"),
            }

        # User tags
        usertags = item.get("usertags", {})
        if usertags and usertags.get("in"):
            result["tagged_users"] = [
                tag.get("user", {}).get("username", "")
                for tag in usertags["in"]
                if tag.get("user")
            ]

        return result

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 5: Web API (no cookies)
    # ═══════════════════════════════════════════════════════════

    def get_web_api(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Web API request without cookies.
        Some endpoints return limited data without authentication.
        """
        url = f"https://www.instagram.com/api/v1{endpoint}"
        extra_headers = {
            "accept": "*/*",
            "x-ig-app-id": IG_APP_ID,
            "x-requested-with": "XMLHttpRequest",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "referer": "https://www.instagram.com/",
        }

        try:
            return self._request(
                url, "web_api",
                headers=extra_headers,
                params=params,
                parse_json=True,
            )
        except StrategyFailed:
            return None

    def get_web_profile(self, username: str) -> Optional[Dict]:
        """Get profile via web API without cookies."""
        data = self.get_web_api(
            "/users/web_profile_info/",
            params={"username": username},
        )
        if data and isinstance(data, dict):
            user = data.get("data", {}).get("user", {})
            if user:
                return user
        return None

    # ═══════════════════════════════════════════════════════════
    # FALLBACK CHAIN — try all strategies
    # ═══════════════════════════════════════════════════════════

    def get_profile_chain(self, username: str) -> Optional[Dict]:
        """
        Get profile using fallback chain.
        Tries all strategies in order until one succeeds.
        """
        strategies = [
            ("html_parse", lambda: self.get_profile_html(username)),
            ("web_api", lambda: self.get_web_profile(username)),
            ("graphql", lambda: self._graphql_profile_fallback(username)),
        ]

        for name, fn in strategies:
            try:
                result = fn()
                if result:
                    logger.info(f"[Anon] Profile '{username}' fetched via {name}")
                    return result
                logger.debug(f"[Anon] Strategy {name} returned empty for '{username}'")
            except Exception as e:
                logger.debug(f"[Anon] Strategy {name} failed: {e}")
                continue

        logger.warning(f"[Anon] All strategies failed for profile '{username}'")
        return None

    def get_post_chain(self, shortcode: str) -> Optional[Dict]:
        """
        Get post using fallback chain.
        Tries all strategies in order.
        """
        strategies = [
            ("graphql_docid", lambda: self.get_graphql_docid(shortcode)),
            ("embed", lambda: self.get_embed_data(shortcode)),
            ("graphql", lambda: self._graphql_post_fallback(shortcode)),
            ("web_api", lambda: self._web_post_fallback(shortcode)),
        ]

        for name, fn in strategies:
            try:
                result = fn()
                if result:
                    logger.info(f"[Anon] Post '{shortcode}' fetched via {name}")
                    return result
                logger.debug(f"[Anon] Strategy {name} returned empty for '{shortcode}'")
            except Exception as e:
                logger.debug(f"[Anon] Strategy {name} failed: {e}")
                continue

        logger.warning(f"[Anon] All strategies failed for post '{shortcode}'")
        return None

    def _graphql_profile_fallback(self, username: str) -> Optional[Dict]:
        """GraphQL fallback for profile."""
        query_hash = ANON_GRAPHQL_HASHES.get("user_info", "")
        data = self.get_graphql_public(query_hash, {"username": username})
        if data and data.get("user"):
            return self._parse_graphql_user(data["user"])
        return None

    def _graphql_post_fallback(self, shortcode: str) -> Optional[Dict]:
        """GraphQL fallback for post."""
        query_hash = ANON_GRAPHQL_HASHES.get("post_info", "")
        data = self.get_graphql_public(query_hash, {"shortcode": shortcode})
        if data and data.get("shortcode_media"):
            return self._parse_embed_media(data["shortcode_media"])
        return None

    def _web_post_fallback(self, shortcode: str) -> Optional[Dict]:
        """Web API fallback for post."""
        # Convert shortcode to media_id
        from . import utils
        try:
            media_pk = utils.shortcode_to_pk(shortcode)
            data = self.get_web_api(f"/media/{media_pk}/info/")
            if data and data.get("items"):
                return data["items"][0]
        except Exception:
            pass
        return None

    # ═══════════════════════════════════════════════════════════
    # SEARCH — web/search/topsearch
    # ═══════════════════════════════════════════════════════════

    def search_web(
        self,
        query: str,
        context: str = "blended",
    ) -> Optional[Dict]:
        """
        Search Instagram (anonymous).

        Uses /web/search/topsearch/ endpoint.

        Args:
            query: Search query (username, hashtag, or keyword)
            context: Search context — 'blended', 'user', 'hashtag', 'place'

        Returns:
            Dict with: users, hashtags, places lists
        """
        url = "https://www.instagram.com/web/search/topsearch/"
        headers = {
            "accept": "*/*",
            "x-ig-app-id": IG_APP_ID,
            "x-requested-with": "XMLHttpRequest",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "referer": "https://www.instagram.com/",
        }
        params = {"query": query, "context": context}
        try:
            data = self._request(url, "web_api", headers=headers, params=params)
            if data and isinstance(data, dict):
                return {
                    "users": [
                        {
                            "username": u.get("user", {}).get("username"),
                            "full_name": u.get("user", {}).get("full_name"),
                            "user_id": u.get("user", {}).get("pk"),
                            "is_private": u.get("user", {}).get("is_private"),
                            "is_verified": u.get("user", {}).get("is_verified"),
                            "profile_pic_url": u.get("user", {}).get("profile_pic_url"),
                            "follower_count": u.get("user", {}).get("follower_count"),
                        }
                        for u in data.get("users", [])
                    ],
                    "hashtags": [
                        {
                            "name": h.get("hashtag", {}).get("name"),
                            "media_count": h.get("hashtag", {}).get("media_count"),
                            "search_result_subtitle": h.get("hashtag", {}).get("search_result_subtitle"),
                        }
                        for h in data.get("hashtags", [])
                    ],
                    "places": [
                        {
                            "title": p.get("place", {}).get("title"),
                            "location": p.get("place", {}).get("location", {}),
                            "subtitle": p.get("place", {}).get("subtitle"),
                        }
                        for p in data.get("places", [])
                    ],
                }
        except StrategyFailed:
            pass
        return None

    # ═══════════════════════════════════════════════════════════
    # REELS — /clips/user/
    # ═══════════════════════════════════════════════════════════

    def get_user_reels(
        self,
        user_id: int | str,
        max_id: Optional[str] = None,
        count: int = 12,
    ) -> Optional[Dict]:
        """
        Get user reels/clips via mobile API.

        Args:
            user_id: User PK
            max_id: Pagination cursor
            count: Number of reels per page

        Returns:
            Dict with: items (parsed reels), paging_info
        """
        params = {
            "target_user_id": str(user_id),
            "page_size": str(count),
        }
        if max_id:
            params["max_id"] = max_id

        data = self.get_mobile_api("/clips/user/", params=params)
        if data and isinstance(data, dict):
            items = data.get("items", [])
            paging = data.get("paging_info", {})
            reels = []
            for item in items:
                media = item.get("media", item)
                reel = self._parse_mobile_feed_item(media)
                # Reel-specific fields
                reel["play_count"] = media.get("play_count") or media.get("view_count", 0)
                reel["fb_play_count"] = media.get("fb_play_count", 0)
                reel["is_reel"] = True
                clips_meta = media.get("clips_metadata", {})
                if clips_meta:
                    reel["audio"] = {
                        "title": clips_meta.get("music_info", {}).get("music_asset_info", {}).get("title"),
                        "artist": clips_meta.get("music_info", {}).get("music_asset_info", {}).get("display_artist"),
                    }
                reels.append(reel)

            return {
                "items": reels,
                "more_available": paging.get("more_available", False),
                "max_id": paging.get("max_id"),
                "num_results": len(reels),
            }
        return None

    # ═══════════════════════════════════════════════════════════
    # HASHTAG SECTIONS — /tags/{tag}/sections/
    # ═══════════════════════════════════════════════════════════

    def get_hashtag_sections(
        self,
        tag_name: str,
        tab: str = "recent",
        max_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get hashtag posts via web API sections endpoint.

        Args:
            tag_name: Hashtag name (without #)
            tab: 'recent' or 'top'
            max_id: Pagination cursor

        Returns:
            Dict with: sections (posts), more_available, next_max_id, media_count
        """
        tag = tag_name.lstrip("#").strip().lower()
        endpoint = f"/tags/{tag}/sections/"
        params = {"tab": tab}
        if max_id:
            params["max_id"] = max_id

        data = self.get_web_api(endpoint, params=params)
        if data and isinstance(data, dict):
            posts = []
            for section in data.get("sections", []):
                layout = section.get("layout_content", {})
                medias = layout.get("medias", [])
                for m in medias:
                    media = m.get("media", {})
                    if media:
                        posts.append(self._parse_mobile_feed_item(media))

            return {
                "tag_name": tag,
                "posts": posts,
                "more_available": data.get("more_available", False),
                "next_max_id": data.get("next_max_id"),
                "next_page": data.get("next_page"),
                "media_count": data.get("media_count"),
            }
        return None

    # ═══════════════════════════════════════════════════════════
    # LOCATION SECTIONS — /locations/{id}/sections/
    # ═══════════════════════════════════════════════════════════

    def get_location_sections(
        self,
        location_id: int | str,
        tab: str = "recent",
        max_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get location posts via web API.

        Args:
            location_id: Location PK
            tab: 'recent' or 'ranked'
            max_id: Pagination cursor

        Returns:
            Dict with: location_info, posts, more_available, next_max_id
        """
        endpoint = f"/locations/{location_id}/sections/"
        params = {"tab": tab}
        if max_id:
            params["max_id"] = max_id

        data = self.get_web_api(endpoint, params=params)
        if data and isinstance(data, dict):
            posts = []
            for section in data.get("sections", []):
                layout = section.get("layout_content", {})
                medias = layout.get("medias", [])
                for m in medias:
                    media = m.get("media", {})
                    if media:
                        posts.append(self._parse_mobile_feed_item(media))

            location_info = data.get("location", {})
            return {
                "location": {
                    "pk": location_info.get("pk"),
                    "name": location_info.get("name"),
                    "address": location_info.get("address"),
                    "city": location_info.get("city"),
                    "lat": location_info.get("lat"),
                    "lng": location_info.get("lng"),
                } if location_info else None,
                "posts": posts,
                "more_available": data.get("more_available", False),
                "next_max_id": data.get("next_max_id"),
                "media_count": data.get("media_count"),
            }
        return None

    # ═══════════════════════════════════════════════════════════
    # SIMILAR ACCOUNTS — /discover/chaining/
    # ═══════════════════════════════════════════════════════════

    def get_similar_accounts(self, user_id: int | str) -> Optional[List[Dict]]:
        """
        Get similar/suggested accounts for a user.

        Args:
            user_id: Target user PK

        Returns:
            List of similar user dicts
        """
        endpoint = f"/discover/chaining/"
        params = {"target_id": str(user_id)}

        data = self.get_web_api(endpoint, params=params)
        if data and isinstance(data, dict):
            users = data.get("users", [])
            return [
                {
                    "username": u.get("username"),
                    "full_name": u.get("full_name"),
                    "user_id": u.get("pk"),
                    "is_private": u.get("is_private"),
                    "is_verified": u.get("is_verified"),
                    "profile_pic_url": u.get("profile_pic_url"),
                    "follower_count": u.get("follower_count"),
                    "is_business": u.get("is_business"),
                    "category": u.get("category"),
                }
                for u in users
            ]
        return None

    # ═══════════════════════════════════════════════════════════
    # STORY HIGHLIGHTS — /highlights/{id}/highlights_tray/
    # ═══════════════════════════════════════════════════════════

    def get_highlights_tray(self, user_id: int | str) -> Optional[List[Dict]]:
        """
        Get story highlights tray for a user (anonymous).

        Args:
            user_id: User PK

        Returns:
            List of highlight dicts with title, cover, item_count
        """
        data = self.get_mobile_api(f"/highlights/{user_id}/highlights_tray/")
        if data and isinstance(data, dict):
            tray = data.get("tray", [])
            highlights = []
            for item in tray:
                cover_media = item.get("cover_media", {})
                cropped = cover_media.get("cropped_image_version", {})

                highlight = {
                    "highlight_id": item.get("id"),
                    "title": item.get("title", ""),
                    "media_count": item.get("media_count", 0),
                    "cover_url": cropped.get("url") or cover_media.get("url", ""),
                    "created_at": item.get("created_at"),
                }
                highlights.append(highlight)

            return highlights
        return None

    # ═══════════════════════════════════════════════════════════
    # STATS
    # ═══════════════════════════════════════════════════════════

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def error_count(self) -> int:
        return self._error_count


class StrategyFailed(Exception):
    """Raised when a single strategy fails (triggers fallback)."""
    pass

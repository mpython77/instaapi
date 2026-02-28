"""
Search API
==========
Search endpoints:
    /web/search/topsearch/          -> Users + hashtags + places
    /tags/search/                   -> Hashtag search
    /fbsearch/places/               -> Place search
    /fbsearch/web/top_serp/         -> Hashtag top posts (media_grid)
    /discover/topical_explore/      -> Explore page
"""

import time
import uuid
import logging
from typing import Any, Dict, List, Optional

from ..client import HttpClient
from ..models.user import UserShort
from ..models.media import Media as MediaModel
from ..models.hashtag import HashtagSearchResult

logger = logging.getLogger("instaapi.search")


class SearchAPI:
    """Instagram qidiruv API"""

    def __init__(self, client: HttpClient):
        self._client = client

    # ─── UMUMIY QIDIRUV ─────────────────────────────────────

    def top_search(self, query: str, context: str = "blended") -> Dict[str, Any]:
        """
        Top search (users + hashtags + places).

        Args:
            query: Search query
            context: "blended" (all), "user", "hashtag", "place"

        Returns:
            {users: [...], hashtags: [...], places: [...]}
        """
        return self._client.get(
            "/web/search/topsearch/",
            params={"context": context, "query": query},
            rate_category="get_search",
        )

    def search_users(self, query: str) -> List[UserShort]:
        """
        User search (parsed).

        Args:
            query: Username or ism

        Returns:
            List of UserShort models
        """
        data = self.top_search(query, context="user")
        users = []
        for item in data.get("users", []):
            u = item.get("user", {})
            if isinstance(u, dict):
                users.append(UserShort(**u))
        return users

    def search_hashtags(self, query: str) -> List[Dict]:
        """
        Search hashtags.

        Args:
            query: Hashtag name (without #)

        Returns:
            Topilgan hashtaglar list
        """
        data = self._client.get(
            "/tags/search/",
            params={"q": query},
            rate_category="get_search",
        )
        return data.get("results", [])

    def search_places(self, query: str) -> List[Dict]:
        """
        Location search.

        Args:
            query: Place name

        Returns:
            Topilgan joylar list
        """
        data = self._client.get(
            "/fbsearch/places/",
            params={"query": query},
            rate_category="get_search",
        )
        return data.get("items", [])

    # ─── HASHTAG SEARCH (PAGINATION) ─────────────────────────

    def hashtag_search(
        self,
        hashtag: str,
        max_pages: int = 1,
        next_max_id: Optional[str] = None,
        rank_token: Optional[str] = None,
        search_session_id: Optional[str] = None,
        delay: float = 2.0,
    ) -> HashtagSearchResult:
        """
        Search posts by hashtag — WITH PAGINATION.

        Uses /api/v1/fbsearch/web/top_serp/ endpoint.

        Extracts all data:
        - Post: pk, code, media_type, like_count, comment_count, caption
        - User: username, full_name, is_verified, is_private, profile_pic
        - Tagged users: users tagged in the post
        - Location, Music metadata

        Args:
            hashtag: Hashtag name ("#programmer" or "programmer")
            max_pages: How many pages to load (default 1)
            next_max_id: Cursor for continuation (from previous result)
            rank_token: Rank token (from previous result)
            search_session_id: Search session ID (from previous result)
            delay: Wait between pages (seconds)

        Returns:
            HashtagSearchResult: posts, users, pagination info

        Usage:
            # Single page
            result = ig.search.hashtag_search("#fashion")
            print(result)  # <HashtagSearchResult posts=18 users=25 ...>

            # Multiple pages
            result = ig.search.hashtag_search("#fashion", max_pages=5)
            for post in result.posts:
                print(f"@{post.user.username}: {post.like_count} likes")

            # Continue from where we left off
            if result.has_more:
                more = ig.search.hashtag_search(
                    "#fashion",
                    max_pages=3,
                    next_max_id=result.next_max_id,
                    rank_token=result.rank_token,
                    search_session_id=result.search_session_id,
                )
                result = result.merge(more)
        """
        # Hashtag formatlash
        if not hashtag.startswith("#"):
            hashtag = f"#{hashtag}"

        # Session identifiers
        session_id = search_session_id or str(uuid.uuid4())

        # Collect results
        all_posts: List[MediaModel] = []
        all_users: Dict[str, UserShort] = {}
        current_max_id = next_max_id
        current_rank_token = rank_token
        has_more = False
        pages_fetched = 0

        for page in range(max_pages):
            logger.info(
                f"Hashtag search: {hashtag} | page={page + 1}/{max_pages} | "
                f"max_id={current_max_id}"
            )

            # So'rov parametrlari
            params: Dict[str, str] = {
                "enable_metadata": "true",
                "query": hashtag,
                "search_session_id": session_id,
            }

            # Pagination params (from page 2+)
            if current_max_id:
                params["max_id"] = current_max_id
            if current_rank_token:
                params["rank_token"] = current_rank_token

            # API so'rov
            try:
                raw = self._client.get(
                    "/fbsearch/web/top_serp/",
                    params=params,
                    rate_category="get_search",
                )
            except Exception as e:
                logger.error(f"Hashtag search error: {e}")
                break

            if not isinstance(raw, dict) or raw.get("status") != "ok":
                logger.warning(f"Invalid response: {raw}")
                break

            # Pagination ma'lumotlari
            media_grid = raw.get("media_grid", {})
            has_more = media_grid.get("has_more", False)
            current_max_id = media_grid.get("next_max_id")
            current_rank_token = raw.get("rank_token") or current_rank_token
            sections = media_grid.get("sections", [])

            # Parse posts within each section
            page_posts, page_users = self._parse_sections(sections)
            all_posts.extend(page_posts)
            all_users.update(page_users)
            pages_fetched += 1

            logger.info(
                f"  Page {page + 1}: +{len(page_posts)} posts, "
                f"+{len(page_users)} user | "
                f"Total: {len(all_posts)} post, {len(all_users)} user | "
                f"has_more={has_more}"
            )

            # Stop if no more pages
            if not has_more or not current_max_id:
                break

            # Wait between pages (not after the last page)
            if page < max_pages - 1 and delay > 0:
                time.sleep(delay)

        return HashtagSearchResult(
            posts=all_posts,
            users=all_users,
            has_more=has_more,
            next_max_id=current_max_id,
            rank_token=current_rank_token,
            search_session_id=session_id,
            total_posts=len(all_posts),
            total_users=len(all_users),
            pages_fetched=pages_fetched,
        )

    def _parse_sections(
        self, sections: List[Dict]
    ) -> tuple:
        """
        Parse sections array.

        From each section:
        1. Parse posts with Media.from_api()
        2. Post owner -> UserShort
        3. Tagged users -> UserShort (usertags + carousel usertags)

        Returns:
            (posts: List[Media], users: Dict[str, UserShort])
        """
        posts: List[MediaModel] = []
        users: Dict[str, UserShort] = {}

        for section in sections:
            layout_content = section.get("layout_content", {})
            medias = layout_content.get("medias", section.get("medias", []))

            for m_item in medias:
                media_data = m_item.get("media", {})
                if not media_data:
                    continue

                # Post parse (Media modeli)
                try:
                    media = MediaModel.from_api(media_data)
                    posts.append(media)
                except Exception as e:
                    logger.warning(f"Media parse xato: {e}")
                    continue

                # Post owner -> users dict
                user_data = media_data.get("user", {})
                if isinstance(user_data, dict) and user_data.get("username"):
                    username = user_data["username"]
                    if username not in users:
                        try:
                            users[username] = UserShort(**user_data)
                        except Exception:
                            pass

                # Tagged users (main media)
                self._extract_tagged_users(media_data, users)

                # Tagged users (from carousel)
                for carousel_item in media_data.get("carousel_media", []):
                    self._extract_tagged_users(carousel_item, users)

        return posts, users

    def _extract_tagged_users(
        self, media_data: Dict, users: Dict[str, UserShort]
    ) -> None:
        """
        Add tagged users from media to users dict.

        Tekshiradigan joylar:
        - usertags.in[]
        - fb_user_tags.in[]
        """
        # usertags.in
        for tag_location in ("usertags", "fb_user_tags"):
            tags = media_data.get(tag_location, {})
            if not isinstance(tags, dict):
                continue
            for tag in tags.get("in", []):
                tagged_user = tag.get("user", {})
                if isinstance(tagged_user, dict) and tagged_user.get("username"):
                    username = tagged_user["username"]
                    if username not in users:
                        try:
                            users[username] = UserShort(**tagged_user)
                        except Exception:
                            pass

    # ─── LEGACY: web_search (eski metod, backward compat) ────

    def web_search(
        self,
        query: str,
        enable_metadata: bool = True,
    ) -> Dict[str, Any]:
        """
        Web SERP — get top posts by hashtag (raw).
        /fbsearch/web/top_serp/ endpoint.

        Note: Using hashtag_search() is recommended!

        Args:
            query: Search query (e.g. "#fashion")

        Returns:
            Raw API response dict
        """
        params = {
            "enable_metadata": "true" if enable_metadata else "false",
            "query": query,
            "search_session_id": str(uuid.uuid4()),
        }
        return self._client.get(
            "/fbsearch/web/top_serp/",
            params=params,
            rate_category="get_search",
        )

    def web_search_posts(self, hashtag: str) -> List[Dict]:
        """
        Get top posts by hashtag (parsed, flat dict).

        Note: Using hashtag_search() is recommended!

        Args:
            hashtag: Hashtag name (with or without #)

        Returns:
            List of flat post dicts
        """
        if not hashtag.startswith("#"):
            hashtag = f"#{hashtag}"

        raw = self.web_search(hashtag)
        media_grid = raw.get("media_grid", {})
        sections = media_grid.get("sections", [])

        posts = []
        for section in sections:
            layout_content = section.get("layout_content", {})
            medias = layout_content.get("medias", section.get("medias", []))
            for m_item in medias:
                media = m_item.get("media", {})
                if not media:
                    continue

                caption = media.get("caption") or {}
                caption_text = caption.get("text", "")

                image_url = ""
                img_versions = media.get("image_versions2", {})
                candidates = img_versions.get("candidates", [])
                if candidates:
                    image_url = candidates[0].get("url", "")

                video_url = ""
                video_versions = media.get("video_versions", [])
                if video_versions:
                    video_url = video_versions[0].get("url", "")

                user = media.get("user", {})

                posts.append({
                    "pk": media.get("pk"),
                    "code": media.get("code"),
                    "media_type": media.get("media_type"),
                    "like_count": media.get("like_count", 0),
                    "comment_count": media.get("comment_count", 0),
                    "play_count": media.get("play_count"),
                    "caption_text": caption_text,
                    "image_url": image_url,
                    "video_url": video_url,
                    "username": user.get("username"),
                    "user_pk": user.get("pk"),
                    "is_verified": user.get("is_verified", False),
                    "taken_at": media.get("taken_at"),
                    "has_audio": media.get("has_audio"),
                })

        return posts

    # ─── EXPLORE ────────────────────────────────────────────

    def explore(self) -> Dict[str, Any]:
        """
        Explore page content.

        Returns:
            Explore posts and clusters
        """
        return self._client.get(
            "/discover/topical_explore/",
            rate_category="get_default",
        )

    # Aliases for convenience
    search_top = top_search

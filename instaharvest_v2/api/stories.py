"""
Stories API
===========
Story operations: viewing, parsing, mark seen, viewers.

Info in each story item:
    Base:
        - pk, id: Story identifiers
        - media_type: 1=photo, 2=video
        - taken_at, expiring_at: Unix timestamp (24 hour lifetime)
        - video_duration: video duration (seconds)
        - has_audio: has audio

    Interactive stickers:
        - reel_mentions: Tagged people [@username]
        - story_locations: Location sticker (name, lat/lng, address)
        - story_hashtags: #hashtag sticker (name, media_count)
        - story_polls: Poll (question, tallies/votes)
        - story_questions: Question sticker
        - story_sliders: Emoji slider
        - story_quizzes: Quiz sticker
        - story_countdowns: Countdown sticker
        - story_cta: Link sticker (URL, webUri)
        - story_bloks_stickers: Other stickers

    Media:
        - image_versions2: Image versions [{width, height, url}]
        - video_versions: Video versions [{width, height, url, type}]
        - music_metadata: Music (title, artist, duration)

    Additional:
        - story_feed_media: Reposted post
        - viewer_count, total_viewer_count: Viewer count
        - story_reaction_stickers: Reaction stickers
"""

import re
import json as _json
from typing import Any, Dict, List, Optional

from ..client import HttpClient


class StoriesAPI:
    """Instagram stories API"""

    def __init__(self, client: HttpClient):
        self._client = client

    def get_reels_tray(self) -> Dict[str, Any]:
        """
        Stories of followed users (the ring on the home page).

        Returns:
            dict:
                - tray: [{user, items, ...}]
                - story_ranking_token
                - status
        """
        return self._client.get(
            "/feed/reels_tray/",
            rate_category="get_stories",
        )

    def get_user_stories(self, user_id: int | str) -> Dict[str, Any]:
        """
        Stories for a specific user (raw).

        Args:
            user_id: User PK

        Returns:
            dict:
                - reel: {user, items: [...], ...}
                - status
        """
        return self._client.get(
            f"/feed/user/{user_id}/story/",
            rate_category="get_stories",
        )

    def get_stories_parsed(self, user_id: int | str) -> Dict[str, Any]:
        """
        Get user stories in structured format.
        All stickers, tags, locations are parsed.

        Args:
            user_id: User PK

        Returns:
            dict:
                - user: {username, pk, full_name, is_verified}
                - stories_count: int
                - stories: [{
                    pk, media_type, is_video, is_photo,
                    taken_at, expiring_at, video_duration,
                    has_audio,
                    images: [{width, height, url}],
                    videos: [{width, height, url}],
                    mentions: [{username, pk, full_name}],
                    locations: [{name, address, city, lat, lng, pk}],
                    hashtags: [{name, media_count}],
                    polls: [{question, tallies}],
                    questions: [{question}],
                    sliders: [{question, emoji}],
                    quizzes: [{question, options}],
                    countdowns: [{text, end_ts}],
                    links: [{url, text}],
                    music: {title, artist, duration_ms},
                    repost: {media_pk, ...} or None,
                    viewer_count: int,
                  }]
        """
        raw = self.get_user_stories(user_id)
        reel = raw.get("reel")

        if not reel:
            return {"user": None, "stories_count": 0, "stories": []}

        # User
        raw_user = reel.get("user", {})
        user = {
            "username": raw_user.get("username"),
            "pk": raw_user.get("pk"),
            "full_name": raw_user.get("full_name"),
            "is_verified": raw_user.get("is_verified"),
            "profile_pic_url": raw_user.get("profile_pic_url"),
        }

        stories = []
        for item in reel.get("items", []):
            story = self._parse_story_item(item)
            stories.append(story)

        return {
            "user": user,
            "stories_count": len(stories),
            "stories": stories,
        }

    def _parse_story_item(self, item: Dict) -> Dict[str, Any]:
        """Parse a single story item"""
        media_type = item.get("media_type", 0)

        # Images
        images = []
        for c in item.get("image_versions2", {}).get("candidates", []):
            images.append({
                "width": c.get("width"),
                "height": c.get("height"),
                "url": c.get("url"),
            })

        # Videos
        videos = []
        for v in item.get("video_versions", []):
            videos.append({
                "width": v.get("width"),
                "height": v.get("height"),
                "url": v.get("url"),
                "type": v.get("type"),
            })

        # Mentions (reel_mentions)
        mentions = []
        for rm in item.get("reel_mentions", []):
            u = rm.get("user", {})
            mentions.append({
                "username": u.get("username"),
                "pk": u.get("pk"),
                "full_name": u.get("full_name"),
                "is_verified": u.get("is_verified"),
            })

        # Locations (story_locations)
        locations = []
        for sl in item.get("story_locations", []):
            loc = sl.get("location", {})
            locations.append({
                "name": loc.get("name"),
                "address": loc.get("address"),
                "city": loc.get("city"),
                "lat": loc.get("lat"),
                "lng": loc.get("lng"),
                "pk": loc.get("pk"),
                "short_name": loc.get("short_name"),
                "external_source": loc.get("external_source"),
                "facebook_places_id": loc.get("facebook_places_id"),
            })

        # Hashtags (story_hashtags)
        hashtags = []
        for sh in item.get("story_hashtags", []):
            ht = sh.get("hashtag", {})
            hashtags.append({
                "name": ht.get("name"),
                "media_count": ht.get("media_count"),
                "id": ht.get("id"),
            })

        # Polls (story_polls)
        polls = []
        for sp in item.get("story_polls", []):
            poll = sp.get("poll_sticker", {})
            tallies = []
            for t in poll.get("tallies", []):
                tallies.append({
                    "text": t.get("text"),
                    "count": t.get("count", 0),
                })
            polls.append({
                "id": poll.get("poll_id"),
                "question": poll.get("question"),
                "tallies": tallies,
                "viewer_vote": poll.get("viewer_vote"),
            })

        # Questions (story_questions)
        questions = []
        for sq in item.get("story_questions", []):
            qs = sq.get("question_sticker", {})
            questions.append({
                "question_id": qs.get("question_id"),
                "question": qs.get("question"),
                "question_type": qs.get("question_type"),
            })

        # Sliders (story_sliders)
        sliders = []
        for ss in item.get("story_sliders", []):
            slider = ss.get("slider_sticker", {})
            sliders.append({
                "slider_id": slider.get("slider_id"),
                "question": slider.get("question"),
                "emoji": slider.get("emoji"),
                "slider_vote_average": slider.get("slider_vote_average"),
                "slider_vote_count": slider.get("slider_vote_count"),
            })

        # Quizzes (story_quizzes)
        quizzes = []
        for sq_item in item.get("story_quizzes", []):
            quiz = sq_item.get("quiz_sticker", {})
            options = []
            for opt in quiz.get("tallies", []):
                options.append({
                    "text": opt.get("text"),
                    "count": opt.get("count", 0),
                })
            quizzes.append({
                "quiz_id": quiz.get("quiz_id"),
                "question": quiz.get("question"),
                "correct_answer": quiz.get("correct_answer"),
                "options": options,
                "viewer_answer": quiz.get("viewer_answer"),
            })

        # Countdowns (story_countdowns)
        countdowns = []
        for sc in item.get("story_countdowns", []):
            cd = sc.get("countdown_sticker", {})
            countdowns.append({
                "countdown_id": cd.get("countdown_id"),
                "text": cd.get("text"),
                "end_ts": cd.get("end_ts"),
                "following_enabled": cd.get("following_enabled"),
            })

        # Links / CTA (story_cta)
        links = []
        for cta in item.get("story_cta", []):
            for link in cta.get("links", []):
                links.append({
                    "url": link.get("webUri") or link.get("url", ""),
                    "text": link.get("linkTitle", ""),
                    "link_type": link.get("linkType"),
                })

        # Music
        music = None
        mm = item.get("music_metadata")
        if mm and isinstance(mm, dict):
            mi = mm.get("music_info", {})
            if mi:
                asset = mi.get("music_asset_info", {})
                music = {
                    "title": asset.get("title"),
                    "artist": asset.get("display_artist"),
                    "duration_ms": asset.get("duration_in_ms"),
                    "is_explicit": asset.get("is_explicit"),
                    "audio_asset_id": asset.get("audio_asset_id"),
                }

        # Repost (story_feed_media)
        repost = None
        feed_media = item.get("story_feed_media", [])
        if feed_media:
            fm = feed_media[0]
            repost = {
                "media_id": fm.get("media_id"),
                "media_code": fm.get("media_code"),
            }

        return {
            "pk": item.get("pk"),
            "id": item.get("id"),
            "media_type": media_type,
            "is_photo": media_type == 1,
            "is_video": media_type == 2,
            "taken_at": item.get("taken_at"),
            "expiring_at": item.get("expiring_at"),
            "video_duration": item.get("video_duration"),
            "has_audio": item.get("has_audio"),

            # Media
            "images": images,
            "videos": videos,

            # Interactive stickers
            "mentions": mentions,
            "locations": locations,
            "hashtags": hashtags,
            "polls": polls,
            "questions": questions,
            "sliders": sliders,
            "quizzes": quizzes,
            "countdowns": countdowns,
            "links": links,

            # Music & repost
            "music": music,
            "repost": repost,

            # Viewers
            "viewer_count": item.get("viewer_count"),
            "total_viewer_count": item.get("total_viewer_count"),
        }

    def get_tray_parsed(self) -> List[Dict[str, Any]]:
        """
        Get story tray in structured format.
        Who has stories and how many.

        Returns:
            list: [{
                username, pk, full_name, is_verified,
                stories_count, has_besties_media, latest_reel_media
            }]
        """
        raw = self.get_reels_tray()
        result = []
        for t in raw.get("tray", []):
            u = t.get("user", {})
            items = t.get("items", [])
            result.append({
                "username": u.get("username"),
                "pk": u.get("pk"),
                "full_name": u.get("full_name"),
                "is_verified": u.get("is_verified"),
                "profile_pic_url": u.get("profile_pic_url"),
                "stories_count": len(items) if items else t.get("media_count", 0),
                "has_besties_media": t.get("has_besties_media", False),
                "latest_reel_media": t.get("latest_reel_media"),
            })
        return result

    # ─── Original methods ───────────────────────────────────

    def mark_seen(self, items: List[Dict]) -> Dict[str, Any]:
        """
        Mark story as seen.

        Args:
            items: List of viewed story elements
                   Each: {"media_id": "...", "taken_at": "...", "user_id": "..."}
        """
        import json
        import time

        reels = {}
        for item in items:
            media_id = str(item.get("media_id", item.get("pk", "")))
            taken_at = str(item.get("taken_at", int(time.time())))
            user_id = str(item.get("user_id", ""))

            key = f"{media_id}_{user_id}"
            reels[key] = [f"{taken_at}_{int(time.time())}"]

        return self._client.post(
            "/media/seen/",
            data={"reels": json.dumps(reels)},
            rate_category="post_default",
        )

    def get_viewers(self, story_id: int | str) -> Dict[str, Any]:
        """
        Get story viewers.

        Args:
            story_id: Story media PK

        Returns:
            List of viewers
        """
        return self._client.get(
            f"/media/{story_id}/list_reel_media_viewer/",
            rate_category="get_stories",
        )

    def vote_poll(
        self,
        story_id: int | str,
        poll_id: int | str,
        vote: int = 0,
    ) -> Dict[str, Any]:
        """
        Vote on a story poll.

        Args:
            story_id: Story media PK
            poll_id: Poll ID
            vote: Vote number (0 or 1)
        """
        return self._client.post(
            "/story_interactions/story_poll_vote/",
            data={
                "media_id": str(story_id),
                "poll_id": str(poll_id),
                "vote": str(vote),
            },
            rate_category="post_default",
        )

    def answer_question(
        self,
        story_id: int | str,
        question_id: int | str,
        answer: str,
    ) -> Dict[str, Any]:
        """
        Respond to a story question sticker.

        Args:
            story_id: Story media PK
            question_id: Question sticker ID
            answer: Reply text
        """
        return self._client.post(
            "/story_interactions/story_question_response/",
            data={
                "media_id": str(story_id),
                "question_id": str(question_id),
                "response": answer,
            },
            rate_category="post_default",
        )

    def vote_slider(
        self,
        story_id: int | str,
        slider_id: int | str,
        vote: float,
    ) -> Dict[str, Any]:
        """
        Vote on a story emoji slider.

        Args:
            story_id: Story media PK
            slider_id: Slider sticker ID
            vote: Vote value (0.0 - 1.0)
        """
        return self._client.post(
            "/story_interactions/story_slider_vote/",
            data={
                "media_id": str(story_id),
                "slider_id": str(slider_id),
                "vote": str(vote),
            },
            rate_category="post_default",
        )

    def answer_quiz(
        self,
        story_id: int | str,
        quiz_id: int | str,
        answer: int,
    ) -> Dict[str, Any]:
        """
        Answer a story quiz.

        Args:
            story_id: Story media PK
            quiz_id: Quiz sticker ID
            answer: Answer number (0, 1, 2, ...)
        """
        return self._client.post(
            "/story_interactions/story_quiz_answer/",
            data={
                "media_id": str(story_id),
                "quiz_id": str(quiz_id),
                "answer": str(answer),
            },
            rate_category="post_default",
        )

    # ─── Highlights ─────────────────────────────────────────

    def get_highlights_tray(self, user_id: int | str) -> Dict[str, Any]:
        """
        User highlights list (raw).

        Args:
            user_id: User PK

        Returns:
            dict:
                - tray: [{id, title, media_count, cover_media, ...}]
                - status
        """
        return self._client.get(
            f"/highlights/{user_id}/highlights_tray/",
            rate_category="get_default",
        )

    def get_highlights_parsed(self, user_id: int | str) -> List[Dict[str, Any]]:
        """
        Get highlights list in structured format.

        Args:
            user_id: User PK

        Returns:
            list: [{
                id, title, media_count, cover_url,
                created_at, updated_at, is_pinned
            }]
        """
        raw = self.get_highlights_tray(user_id)
        result = []
        for h in raw.get("tray", []):
            cover = h.get("cover_media", {})
            cover_url = ""
            cropped = cover.get("cropped_image_version", {})
            if cropped:
                cover_url = cropped.get("url", "")

            result.append({
                "id": h.get("id"),
                "title": h.get("title"),
                "media_count": h.get("media_count", 0),
                "cover_url": cover_url,
                "created_at": h.get("created_at"),
                "updated_at": h.get("updated_timestamp"),
                "is_pinned": h.get("is_pinned_highlight", False),
            })
        return result

    def get_highlight_items(self, highlight_id: str) -> Dict[str, Any]:
        """
        Get all items within a highlight (raw).

        Args:
            highlight_id: Highlight ID (e.g. "highlight:17889448593291353")

        Returns:
            dict: Reel data with items
        """
        data = self._client.post(
            "/feed/reels_media/",
            data={"user_ids": _json.dumps([highlight_id])},
            rate_category="get_default",
        )
        reels = data.get("reels", {})
        return reels.get(highlight_id, {})

    def get_highlight_items_parsed(self, highlight_id: str) -> Dict[str, Any]:
        """
        Get highlight items in structured format.
        Story items with consistent structure — mentions, locations,
        hashtags, music, polls, links, and everything is parsed.

        Args:
            highlight_id: Highlight ID

        Returns:
            dict:
                - title: Highlight title
                - items_count: int
                - items: [{pk, media_type, mentions, locations, ...}]
        """
        reel = self.get_highlight_items(highlight_id)
        title = reel.get("title", "")
        items = []
        for item in reel.get("items", []):
            parsed = self._parse_story_item(item)
            items.append(parsed)

        return {
            "title": title,
            "items_count": len(items),
            "items": items,
        }

    def get_all_highlights_with_items(
        self,
        user_id: int | str,
        max_items_per_highlight: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get all highlights AND their items.

        Args:
            user_id: User PK
            max_items_per_highlight: Max items per highlight
                (0 = all)

        Returns:
            list: [{id, title, media_count, cover_url, items: [...]}]
        """
        highlights = self.get_highlights_parsed(user_id)
        result = []
        for h in highlights:
            h_data = self.get_highlight_items_parsed(h["id"])
            items = h_data["items"]
            if max_items_per_highlight > 0:
                items = items[:max_items_per_highlight]

            result.append({
                **h,
                "items": items,
            })
        return result

    # ─── HIGHLIGHT CRUD ─────────────────────────────────────

    def create_highlight(
        self,
        title: str,
        media_ids: List[str],
        cover_media_id: str = None,
    ) -> Dict[str, Any]:
        """
        Create a new highlight.

        Args:
            title: Highlight title
            media_ids: List of story media PKs
            cover_media_id: Cover image PK (optional, first item used by default)

        Returns:
            dict: Created highlight data
        """
        data = {
            "title": title,
            "media_ids": _json.dumps([str(m) for m in media_ids]),
            "source": "story_viewer_profile",
        }
        if cover_media_id:
            data["cover_media_id"] = str(cover_media_id)
        return self._client.post(
            "/highlights/create_reel/",
            data=data,
            rate_category="post_default",
        )

    def delete_highlight(self, highlight_id: str) -> Dict[str, Any]:
        """
        Delete a highlight.

        Args:
            highlight_id: Highlight ID (e.g. "highlight:17889448593291353")
        """
        # Extract number from highlight_id
        reel_id = highlight_id.replace("highlight:", "")
        return self._client.post(
            f"/highlights/{reel_id}/delete_reel/",
            rate_category="post_default",
        )

    def edit_highlight(
        self,
        highlight_id: str,
        title: str = None,
        add_media_ids: List[str] = None,
        remove_media_ids: List[str] = None,
        cover_media_id: str = None,
    ) -> Dict[str, Any]:
        """
        Edit highlight (name, add/remove media).

        Args:
            highlight_id: Highlight ID
            title: New name (optional)
            add_media_ids: Story PKs to add
            remove_media_ids: Story PKs to remove
            cover_media_id: New cover PK
        """
        reel_id = highlight_id.replace("highlight:", "")
        data = {}
        if title:
            data["title"] = title
        if add_media_ids:
            data["added_media_ids"] = _json.dumps([str(m) for m in add_media_ids])
        if remove_media_ids:
            data["removed_media_ids"] = _json.dumps([str(m) for m in remove_media_ids])
        if cover_media_id:
            data["cover_media_id"] = str(cover_media_id)
        return self._client.post(
            f"/highlights/{reel_id}/edit_reel/",
            data=data,
            rate_category="post_default",
        )

    def react_to_story(
        self,
        story_pk: int | str,
        emoji: str = "❤️",
    ) -> Dict[str, Any]:
        """
        Send emoji reaction to a story.

        Args:
            story_pk: Story media PK
            emoji: Reaction emoji
        """
        return self._client.post(
            f"/direct_v2/threads/broadcast/story_react/",
            data={
                "media_id": str(story_pk),
                "reaction_emoji": emoji,
                "entry": "reel",
            },
            rate_category="post_dm",
        )

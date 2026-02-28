"""
Lookalike Audience Finder
==========================
Find similar audiences, analyze overlap, and discover
potential followers based on competitor analysis.

Usage:
    ig = Instagram.from_env(".env")

    # Find lookalike users from competitor
    result = ig.audience.find_lookalike("competitor", count=50)

    # Overlap analysis between two accounts
    overlap = ig.audience.overlap("account1", "account2")

    # Audience insights for a user
    insights = ig.audience.insights("cristiano")
"""

import logging
import random
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("instaharvest_v2.audience")


class AudienceAPI:
    """
    Lookalike Audience Finder & Analyzer.

    Composes: UsersAPI, FriendshipsAPI, HashtagsAPI.
    """

    def __init__(self, client, users_api, friendships_api):
        self._client = client
        self._users = users_api
        self._friendships = friendships_api

    # ═══════════════════════════════════════════════════════════
    # FIND LOOKALIKE
    # ═══════════════════════════════════════════════════════════

    def find_lookalike(
        self,
        source_username: str,
        count: int = 50,
        min_followers: int = 100,
        max_followers: int = 50000,
        filter_private: bool = True,
        method: str = "mixed",
    ) -> Dict[str, Any]:
        """
        Find users similar to a source account's audience.

        Methods:
            - 'followers': Analyze source's followers' followings
            - 'hashtag': Find users using similar hashtags
            - 'mixed': Combine both methods

        Args:
            source_username: Source account to base lookalike on
            count: Number of lookalike users to find
            min_followers: Min follower count filter
            max_followers: Max follower count filter
            filter_private: Skip private accounts
            method: 'followers', 'hashtag', or 'mixed'

        Returns:
            dict: {users, source, method, count, duration_seconds}
        """
        start = time.time()
        user = self._users.get_by_username(source_username)
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)

        candidates: Dict[str, Dict] = {}  # username -> user_info

        # Method 1: Followers' followings (mutual interest graph)
        if method in ("followers", "mixed"):
            self._discover_via_followers(
                user_id, candidates, count * 2,
                min_followers, max_followers, filter_private,
            )

        # Method 2: Hashtag-based discovery
        if method in ("hashtag", "mixed"):
            self._discover_via_hashtags(
                user_id, source_username, candidates, count,
                min_followers, max_followers, filter_private,
            )

        # Score and rank candidates
        scored = self._score_candidates(candidates, source_username)
        scored.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        top = scored[:count]

        duration = time.time() - start
        logger.info(
            f"👥 Lookalike @{source_username}: found {len(top)} users "
            f"(method={method}, {duration:.1f}s)"
        )
        return {
            "users": top,
            "source": source_username,
            "method": method,
            "count": len(top),
            "total_candidates": len(candidates),
            "duration_seconds": round(duration, 1),
        }

    # ═══════════════════════════════════════════════════════════
    # OVERLAP ANALYSIS
    # ═══════════════════════════════════════════════════════════

    def overlap(
        self,
        username_a: str,
        username_b: str,
        max_followers: int = 2000,
    ) -> Dict[str, Any]:
        """
        Find follower overlap between two accounts.

        Args:
            username_a: First account
            username_b: Second account
            max_followers: Max followers to compare

        Returns:
            dict: {common_followers, overlap_rate, unique_to_a, unique_to_b}
        """
        user_a = self._users.get_by_username(username_a)
        user_b = self._users.get_by_username(username_b)
        id_a = getattr(user_a, "pk", None) or (user_a.get("pk") if isinstance(user_a, dict) else None)
        id_b = getattr(user_b, "pk", None) or (user_b.get("pk") if isinstance(user_b, dict) else None)

        followers_a = self._get_follower_set(id_a, max_followers)
        followers_b = self._get_follower_set(id_b, max_followers)

        common = followers_a & followers_b
        union = followers_a | followers_b
        overlap_rate = len(common) / max(len(union), 1) * 100

        return {
            "username_a": username_a,
            "username_b": username_b,
            "followers_a_sampled": len(followers_a),
            "followers_b_sampled": len(followers_b),
            "common_followers": len(common),
            "overlap_rate": round(overlap_rate, 2),
            "unique_to_a": len(followers_a - followers_b),
            "unique_to_b": len(followers_b - followers_a),
            "jaccard_index": round(len(common) / max(len(union), 1), 4),
        }

    # ═══════════════════════════════════════════════════════════
    # AUDIENCE INSIGHTS
    # ═══════════════════════════════════════════════════════════

    def insights(
        self,
        username: str,
        sample_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Audience insights — profile analysis of followers.

        Analyzes a sample of followers to understand demographics.

        Args:
            username: Target username
            sample_size: Number of followers to sample

        Returns:
            dict: {verified_rate, private_rate, avg_followers, avg_posts,
                   bio_keywords, engagement_potential}
        """
        user = self._users.get_by_username(username)
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)

        # Sample followers
        followers = self._get_followers_list(user_id, sample_size)
        if not followers:
            return {"error": "Could not fetch followers", "sampled": 0}

        # Analyze
        verified = 0
        private = 0
        total_followers = 0
        total_posts = 0
        bio_words = Counter()
        has_data = 0

        for f in followers:
            if f.get("is_verified"):
                verified += 1
            if f.get("is_private"):
                private += 1

            # Some data may be sparse
            fc = f.get("follower_count", 0) or f.get("followers", 0)
            mc = f.get("media_count", 0)
            if fc:
                total_followers += fc
                has_data += 1
            total_posts += mc

            bio = f.get("biography", "") or ""
            words = re.findall(r"[a-zA-Z]{3,}", bio.lower())
            bio_words.update(words)

        n = len(followers)
        avg_followers = total_followers / max(has_data, 1)
        avg_posts = total_posts / max(n, 1)

        # Engagement potential score
        if avg_followers > 10000:
            engagement_potential = "high"
        elif avg_followers > 1000:
            engagement_potential = "medium"
        else:
            engagement_potential = "standard"

        # Remove stopwords from bio keywords
        stopwords = {"the", "and", "for", "are", "but", "not", "you", "all",
                     "can", "was", "one", "our", "out", "has", "have", "had",
                     "this", "that", "with", "from"}
        top_bio = [(w, c) for w, c in bio_words.most_common(30) if w not in stopwords]

        result = {
            "username": username,
            "sampled": n,
            "verified_rate": round(verified / max(n, 1) * 100, 1),
            "private_rate": round(private / max(n, 1) * 100, 1),
            "avg_followers": round(avg_followers),
            "avg_posts": round(avg_posts),
            "engagement_potential": engagement_potential,
            "top_bio_keywords": top_bio[:15],
            "audience_quality": self._audience_quality_score(
                verified / max(n, 1), private / max(n, 1), avg_followers, avg_posts,
            ),
        }
        logger.info(f"👥 Insights @{username}: quality={result['audience_quality']} | "
                     f"avg_fol={avg_followers:.0f} | sampled={n}")
        return result

    # ═══════════════════════════════════════════════════════════
    # FIND SIMILAR ACCOUNTS
    # ═══════════════════════════════════════════════════════════

    def find_similar_accounts(
        self,
        username: str,
        count: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Find accounts similar to the given user.

        Uses Instagram's suggestion/explore mechanisms.

        Args:
            username: Source account
            count: Max results

        Returns:
            List of similar account dicts
        """
        user = self._users.get_by_username(username)
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)

        suggestions = []
        try:
            result = self._client.request(
                "GET", f"/api/v1/discover/chaining/",
                params={"target_id": str(user_id)},
            )
            if result and isinstance(result, dict):
                for u in result.get("users", []):
                    suggestions.append({
                        "username": u.get("username", ""),
                        "full_name": u.get("full_name", ""),
                        "followers": u.get("follower_count", 0),
                        "is_verified": u.get("is_verified", False),
                        "biography": (u.get("biography", "") or "")[:100],
                    })
        except Exception as e:
            logger.debug(f"Chaining API error: {e}")

        return suggestions[:count]

    # ═══════════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════════

    def _discover_via_followers(
        self, user_id, candidates, target, min_f, max_f, skip_private,
    ):
        """Discover users by analyzing followers' other followings."""
        followers = self._get_followers_list(user_id, 50)
        random.shuffle(followers)

        for follower in followers[:20]:  # Sample 20 followers
            fid = follower.get("pk")
            if not fid:
                continue

            try:
                result = self._friendships.get_following(fid, count=30)
                following = result.get("users", [])
            except Exception:
                continue

            for u in following:
                uname = u.get("username", "")
                if uname in candidates:
                    candidates[uname]["weight"] = candidates[uname].get("weight", 0) + 1
                    continue

                fc = u.get("follower_count", 0)
                if fc < min_f or fc > max_f:
                    continue
                if skip_private and u.get("is_private", False):
                    continue

                candidates[uname] = {
                    "username": uname,
                    "full_name": u.get("full_name", ""),
                    "followers": fc,
                    "is_verified": u.get("is_verified", False),
                    "is_private": u.get("is_private", False),
                    "weight": 1,
                    "source": "follower_network",
                }

            if len(candidates) >= target:
                break

            time.sleep(random.uniform(0.5, 1.5))

    def _discover_via_hashtags(
        self, user_id, username, candidates, target, min_f, max_f, skip_private,
    ):
        """Discover users via hashtag analysis."""
        # Get source user's hashtags
        hashtags = self._get_user_hashtags(user_id)
        if not hashtags:
            return

        for tag in hashtags[:5]:
            try:
                result = self._client.request(
                    "GET", f"/api/v1/tags/{tag}/sections/",
                    params={"tab": "recent", "count": "20"},
                )
                if not result or not isinstance(result, dict):
                    continue

                for sec in result.get("sections", []):
                    for m in sec.get("layout_content", {}).get("medias", []):
                        media = m.get("media", {})
                        u = media.get("user", {})
                        uname = u.get("username", "")

                        if not uname or uname == username or uname in candidates:
                            continue

                        fc = u.get("follower_count", 0)
                        if fc < min_f or fc > max_f:
                            continue
                        if skip_private and u.get("is_private", False):
                            continue

                        candidates[uname] = {
                            "username": uname,
                            "full_name": u.get("full_name", ""),
                            "followers": fc,
                            "is_verified": u.get("is_verified", False),
                            "is_private": u.get("is_private", False),
                            "weight": 1,
                            "source": f"hashtag:{tag}",
                        }
            except Exception:
                pass

            if len(candidates) >= target:
                break

    def _get_user_hashtags(self, user_id) -> List[str]:
        """Extract hashtags used by a user from recent posts."""
        tags = Counter()
        try:
            result = self._client.request(
                "GET", f"/api/v1/feed/user/{user_id}/",
                params={"count": "15"},
            )
            if result and isinstance(result, dict):
                for item in result.get("items", []):
                    cap = item.get("caption", {})
                    text = cap.get("text", "") if isinstance(cap, dict) else str(cap or "")
                    found = re.findall(r"#(\w+)", text.lower())
                    tags.update(found)
        except Exception:
            pass
        return [t for t, _ in tags.most_common(10)]

    def _get_followers_list(self, user_id, count: int) -> List[Dict]:
        """Fetch followers list."""
        all_users: list = []
        cursor = None
        while len(all_users) < count:
            try:
                result = self._friendships.get_followers(user_id, count=50, max_id=cursor)
            except Exception:
                break
            users = result.get("users", [])
            if not users:
                break
            all_users.extend(users)
            cursor = result.get("next_max_id") or result.get("next_cursor")
            if not cursor:
                break
        return all_users[:count]

    def _get_follower_set(self, user_id, count: int) -> Set[str]:
        """Get set of follower usernames."""
        followers = self._get_followers_list(user_id, count)
        return {f.get("username", "") for f in followers if f.get("username")}

    @staticmethod
    def _score_candidates(candidates: Dict, source: str) -> List[Dict]:
        """Score candidates by relevance."""
        scored = []
        for uname, info in candidates.items():
            if uname == source:
                continue
            weight = info.get("weight", 1)
            fc = info.get("followers", 0)

            # Relevance: weight (how many connections) + follower bonus
            score = weight * 10
            if 1000 <= fc <= 100000:
                score += 5  # Sweet spot followers
            if info.get("is_verified"):
                score += 3

            info["relevance_score"] = score
            scored.append(info)

        return scored

    @staticmethod
    def _audience_quality_score(verified_rate, private_rate, avg_followers, avg_posts) -> str:
        """Calculate audience quality: excellent/good/average/low."""
        score = 0
        if verified_rate > 0.05:
            score += 2
        if private_rate < 0.4:
            score += 2
        if avg_followers > 500:
            score += 2
        if avg_posts > 10:
            score += 2

        if score >= 6:
            return "excellent"
        elif score >= 4:
            return "good"
        elif score >= 2:
            return "average"
        return "low"

"""
A/B Testing Framework
======================
Test different captions, hashtags, posting times.
Track engagement and determine winners statistically.

Usage:
    ig = Instagram.from_env(".env")

    # Create A/B test
    test = ig.ab_test.create(
        name="caption_test",
        variants={
            "A": {"caption": "Short caption ✨"},
            "B": {"caption": "Longer caption with details and hashtags #test"},
        }
    )

    # Run test (post variant A, wait, post variant B)
    result = ig.ab_test.run(test["id"], photo="photo.jpg")

    # Check results after engagement period
    winner = ig.ab_test.results(test["id"])
    print(f"Winner: Variant {winner['winner']}")
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("instaharvest_v2.ab_test")


class ABTestAPI:
    """
    A/B Testing for Instagram content.

    Composes: UploadAPI, MediaAPI, AnalyticsAPI.
    """

    def __init__(self, client, upload_api=None, media_api=None, analytics_api=None):
        self._client = client
        self._upload = upload_api
        self._media = media_api
        self._analytics = analytics_api
        self._tests: Dict[str, Dict] = {}
        self._storage_file = "ab_tests.json"
        self._load()

    # ═══════════════════════════════════════════════════════════
    # CREATE TEST
    # ═══════════════════════════════════════════════════════════

    def create(
        self,
        name: str,
        variants: Dict[str, Dict],
        metric: str = "engagement",
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Create a new A/B test.

        Args:
            name: Test name
            variants: {"A": {caption, hashtags}, "B": {caption, hashtags}, ...}
            metric: Primary metric — 'engagement', 'likes', 'comments', 'reach'
            description: Test description

        Returns:
            dict: Test object with id, status, variants
        """
        test_id = str(uuid.uuid4())[:8]

        test: Dict[str, Any] = {
            "id": test_id,
            "name": name,
            "description": description,
            "metric": metric,
            "status": "created",
            "variants": {},
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "winner": None,
        }

        for variant_name, config in variants.items():
            test["variants"][variant_name] = {
                "config": config,
                "media_id": None,
                "posted_at": None,
                "likes": 0,
                "comments": 0,
                "engagement_rate": 0,
                "reach": 0,
                "saves": 0,
            }

        self._tests[test_id] = test
        self._save()

        logger.info(f"🧪 A/B Test created: '{name}' ({len(variants)} variants)")
        return test

    # ═══════════════════════════════════════════════════════════
    # RUN TEST
    # ═══════════════════════════════════════════════════════════

    def run(
        self,
        test_id: str,
        photo: Optional[str] = None,
        video: Optional[str] = None,
        delay_between: int = 3600,
    ) -> Dict[str, Any]:
        """
        Execute A/B test by posting each variant.

        Args:
            test_id: Test ID from create()
            photo: Photo path (same photo for all variants)
            video: Video path
            delay_between: Seconds between posting variants (default 1 hour)

        Returns:
            dict: Execution result with media IDs
        """
        test = self._tests.get(test_id)
        if not test:
            raise ValueError(f"Test '{test_id}' not found")

        if not self._upload:
            return {"error": "UploadAPI not available. Record media IDs manually."}

        posted = 0
        for variant_name, variant in test["variants"].items():
            config = variant["config"]
            caption = config.get("caption", "")
            hashtags = config.get("hashtags", [])

            if hashtags:
                full_caption = f"{caption}\n\n{' '.join(f'#{t}' for t in hashtags)}"
            else:
                full_caption = caption

            try:
                if photo:
                    result = self._upload.photo(photo, caption=full_caption)
                elif video:
                    result = self._upload.video(video, caption=full_caption)
                else:
                    continue

                media_id = None
                if isinstance(result, dict):
                    media_id = result.get("media", {}).get("pk") or result.get("pk")
                elif hasattr(result, "pk"):
                    media_id = result.pk

                variant["media_id"] = str(media_id) if media_id else None
                variant["posted_at"] = datetime.now().isoformat()
                posted += 1

                logger.info(f"🧪 Posted variant {variant_name}: media_id={media_id}")
            except Exception as e:
                logger.error(f"Post variant {variant_name} error: {e}")
                variant["error"] = str(e)

            # Wait between variants
            if posted < len(test["variants"]):
                time.sleep(delay_between)

        test["status"] = "running"
        self._save()

        return {
            "test_id": test_id,
            "posted": posted,
            "total_variants": len(test["variants"]),
            "status": "running",
        }

    # ═══════════════════════════════════════════════════════════
    # RECORD RESULTS MANUALLY
    # ═══════════════════════════════════════════════════════════

    def record(
        self,
        test_id: str,
        variant_name: str,
        media_id: Optional[str] = None,
        likes: int = 0,
        comments: int = 0,
        reach: int = 0,
        saves: int = 0,
    ) -> None:
        """
        Manually record variant results.

        Args:
            test_id: Test ID
            variant_name: Variant name ("A", "B", etc.)
            media_id: Media ID (optional)
            likes: Like count
            comments: Comment count
            reach: Reach/impressions
            saves: Saves count
        """
        test = self._tests.get(test_id)
        if not test:
            raise ValueError(f"Test '{test_id}' not found")

        variant = test["variants"].get(variant_name)
        if not variant:
            raise ValueError(f"Variant '{variant_name}' not found")

        if media_id:
            variant["media_id"] = media_id
        variant["likes"] = likes
        variant["comments"] = comments
        variant["reach"] = reach
        variant["saves"] = saves

        self._save()

    # ═══════════════════════════════════════════════════════════
    # COLLECT RESULTS (FROM LIVE DATA)
    # ═══════════════════════════════════════════════════════════

    def collect(self, test_id: str) -> Dict[str, Any]:
        """
        Collect live engagement data for all variants.

        Fetches current likes/comments for each posted variant.

        Args:
            test_id: Test ID

        Returns:
            dict: Updated test with fresh data
        """
        test = self._tests.get(test_id)
        if not test:
            raise ValueError(f"Test '{test_id}' not found")

        for variant_name, variant in test["variants"].items():
            media_id = variant.get("media_id")
            if not media_id:
                continue

            try:
                info = self._media.get_info(media_id)
                if isinstance(info, dict):
                    variant["likes"] = info.get("like_count", 0)
                    variant["comments"] = info.get("comment_count", 0)
                elif hasattr(info, "like_count"):
                    variant["likes"] = getattr(info, "like_count", 0)
                    variant["comments"] = getattr(info, "comment_count", 0)
            except Exception as e:
                logger.debug(f"Collect variant {variant_name} error: {e}")

        self._save()
        return test

    # ═══════════════════════════════════════════════════════════
    # ANALYZE RESULTS
    # ═══════════════════════════════════════════════════════════

    def results(self, test_id: str) -> Dict[str, Any]:
        """
        Analyze A/B test results and determine winner.

        Args:
            test_id: Test ID

        Returns:
            dict: {winner, confidence, variants, improvement_pct}
        """
        test = self._tests.get(test_id)
        if not test:
            raise ValueError(f"Test '{test_id}' not found")

        metric = test.get("metric", "engagement")
        variant_scores = {}

        for name, v in test["variants"].items():
            likes = v.get("likes", 0)
            comments = v.get("comments", 0)
            reach = v.get("reach", 0)
            saves = v.get("saves", 0)

            if metric == "likes":
                score = likes
            elif metric == "comments":
                score = comments
            elif metric == "reach":
                score = reach
            else:  # engagement
                score = likes + comments * 2 + saves * 3

            variant_scores[name] = {
                "score": score,
                "likes": likes,
                "comments": comments,
                "reach": reach,
                "saves": saves,
            }

        if not variant_scores:
            return {"winner": None, "error": "No data"}

        # Find winner
        winner = max(variant_scores, key=lambda k: variant_scores[k]["score"])
        scores = [v["score"] for v in variant_scores.values()]
        max_score = max(scores)
        min_score = min(scores)

        improvement = ((max_score - min_score) / max(min_score, 1)) * 100

        # Confidence (basic: based on score difference)
        if improvement > 50:
            confidence = "high"
        elif improvement > 20:
            confidence = "medium"
        else:
            confidence = "low"

        test["winner"] = winner
        test["status"] = "completed"
        test["completed_at"] = datetime.now().isoformat()
        self._save()

        result = {
            "test_id": test_id,
            "name": test["name"],
            "winner": winner,
            "confidence": confidence,
            "improvement_pct": round(improvement, 1),
            "metric": metric,
            "variants": variant_scores,
        }

        logger.info(
            f"🧪 A/B Result: '{test['name']}' → Winner: {winner} "
            f"(+{improvement:.1f}%, confidence={confidence})"
        )
        return result

    # ═══════════════════════════════════════════════════════════
    # MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def list_tests(self, status: str = "") -> List[Dict]:
        """List all tests, optionally filtered by status."""
        tests = list(self._tests.values())
        if status:
            tests = [t for t in tests if t.get("status") == status]
        return tests

    def get_test(self, test_id: str) -> Optional[Dict]:
        """Get a specific test."""
        return self._tests.get(test_id)

    def delete_test(self, test_id: str) -> bool:
        """Delete a test."""
        if test_id in self._tests:
            del self._tests[test_id]
            self._save()
            return True
        return False

    # ═══════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════

    def _save(self):
        """Save tests to JSON file."""
        try:
            with open(self._storage_file, "w") as f:
                json.dump(self._tests, f, indent=2, default=str)
        except Exception as e:
            logger.debug(f"Save tests error: {e}")

    def _load(self):
        """Load tests from JSON file."""
        if os.path.exists(self._storage_file):
            try:
                with open(self._storage_file, "r") as f:
                    self._tests = json.load(f)
            except Exception:
                self._tests = {}

"""
Async A/B Testing Framework
=============================
Async version of ABTestAPI. Full feature parity.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("instaapi.ab_test")


class AsyncABTestAPI:
    """Async A/B Testing for Instagram content."""

    def __init__(self, client, upload_api=None, media_api=None, analytics_api=None):
        self._client = client
        self._upload = upload_api
        self._media = media_api
        self._analytics = analytics_api
        self._tests: Dict[str, Dict] = {}
        self._persist_path = "ab_tests.json"
        self._load()

    async def create(self, name: str, variants: Dict[str, Dict], metric: str = "engagement", description: str = "") -> Dict[str, Any]:
        """Create a new A/B test."""
        test_id = str(uuid.uuid4())[:8]
        test = {
            "id": test_id, "name": name, "description": description,
            "metric": metric, "status": "created",
            "variants": {k: {**v, "results": {}} for k, v in variants.items()},
            "created_at": datetime.now().isoformat(),
        }
        self._tests[test_id] = test
        self._save()
        return test

    async def record(self, test_id: str, variant_name: str, media_id: Optional[str] = None, likes: int = 0, comments: int = 0, reach: int = 0, saves: int = 0) -> Dict[str, Any]:
        """Manually record variant results."""
        test = self._tests.get(test_id)
        if not test:
            return {"error": f"Test '{test_id}' not found"}
        variant = test["variants"].get(variant_name)
        if not variant:
            return {"error": f"Variant '{variant_name}' not found"}
        variant["results"] = {"likes": likes, "comments": comments, "reach": reach, "saves": saves, "media_id": media_id, "recorded_at": datetime.now().isoformat()}
        test["status"] = "recording"
        self._save()
        return test

    async def collect(self, test_id: str) -> Dict[str, Any]:
        """Collect live engagement data for all variants."""
        test = self._tests.get(test_id)
        if not test:
            return {"error": f"Test '{test_id}' not found"}
        if not self._media:
            return {"error": "MediaAPI not available"}
        for vname, variant in test["variants"].items():
            mid = variant.get("results", {}).get("media_id")
            if mid:
                try:
                    info = await self._media.get_info(mid)
                    variant["results"]["likes"] = info.get("like_count", 0)
                    variant["results"]["comments"] = info.get("comment_count", 0)
                    variant["results"]["collected_at"] = datetime.now().isoformat()
                except Exception as e:
                    logger.debug(f"Collect error for {vname}: {e}")
        self._save()
        return test

    async def results(self, test_id: str) -> Dict[str, Any]:
        """Analyze A/B test results and determine winner."""
        test = self._tests.get(test_id)
        if not test:
            return {"error": f"Test '{test_id}' not found"}
        metric = test.get("metric", "engagement")
        scores = {}
        for vname, variant in test["variants"].items():
            r = variant.get("results", {})
            likes = r.get("likes", 0); comments = r.get("comments", 0)
            if metric == "likes":
                scores[vname] = likes
            elif metric == "comments":
                scores[vname] = comments
            else:
                scores[vname] = likes + comments
        if not scores:
            return {"error": "No results recorded"}
        winner = max(scores, key=scores.get)
        sorted_v = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        improvement = 0
        if len(sorted_v) >= 2 and sorted_v[1][1] > 0:
            improvement = round((sorted_v[0][1] - sorted_v[1][1]) / sorted_v[1][1] * 100, 1)
        test["status"] = "completed"
        self._save()
        return {"winner": winner, "scores": scores, "improvement_pct": improvement, "metric": metric, "test": test}

    def list_tests(self, status: str = "") -> List[Dict]:
        """List all tests."""
        tests = list(self._tests.values())
        if status:
            tests = [t for t in tests if t.get("status") == status]
        return tests

    def get_test(self, test_id: str) -> Optional[Dict]:
        return self._tests.get(test_id)

    def delete_test(self, test_id: str) -> bool:
        if test_id in self._tests:
            del self._tests[test_id]
            self._save()
            return True
        return False

    def _save(self):
        try:
            with open(self._persist_path, "w") as f:
                json.dump(self._tests, f, indent=2, default=str)
        except Exception:
            pass

    def _load(self):
        try:
            if os.path.exists(self._persist_path):
                with open(self._persist_path) as f:
                    self._tests = json.load(f)
        except Exception:
            self._tests = {}

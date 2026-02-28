"""
Scheduler API — Scheduled Actions / Auto-poster
=================================================
Schedule posts, stories, and reels with background worker.
Jobs persist to JSON so they survive restarts.

Usage:
    ig = Instagram.from_env(".env")

    # Schedule a post
    job = ig.scheduler.post_at("2024-03-01 10:00", photo="img.jpg", caption="Hello!")

    # Schedule a story
    ig.scheduler.story_at("2024-03-01 12:00", photo="story.jpg")

    # List pending jobs
    ig.scheduler.list_jobs()

    # Start background worker
    ig.scheduler.start()

    # Cancel a job
    ig.scheduler.cancel(job["id"])

    # Stop worker
    ig.scheduler.stop()
"""

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("instaharvest_v2.scheduler")


class SchedulerJob:
    """Represents a scheduled action."""

    def __init__(
        self,
        job_type: str,
        scheduled_at: datetime,
        params: Dict[str, Any],
        job_id: Optional[str] = None,
    ):
        self.id = job_id or uuid.uuid4().hex[:12]
        self.job_type = job_type  # post, story, reel, action
        self.scheduled_at = scheduled_at
        self.params = params
        self.status = "pending"  # pending, running, done, failed, cancelled
        self.created_at = datetime.now()
        self.executed_at: Optional[datetime] = None
        self._action: Optional[Callable] = None
        self.error: Optional[str] = None
        self.result: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "job_type": self.job_type,
            "scheduled_at": self.scheduled_at.isoformat(),
            "params": self.params,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SchedulerJob":
        job = cls(
            job_type=data["job_type"],
            scheduled_at=datetime.fromisoformat(data["scheduled_at"]),
            params=data.get("params", {}),
            job_id=data["id"],
        )
        job.status = data.get("status", "pending")
        job.created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now()
        job.error = data.get("error")
        return job


class SchedulerAPI:
    """
    Instagram post/story/reel scheduler with background worker.

    Features:
        - Schedule posts, stories, reels at specific times
        - Background worker thread checks every 30s
        - Jobs persist to JSON file
        - Cancel / list jobs
    """

    def __init__(self, upload_api, stories_api, persist_path: str = "scheduler_jobs.json"):
        self._upload = upload_api
        self._stories = stories_api
        self._persist_path = persist_path
        self._jobs: List[SchedulerJob] = []
        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._check_interval = 30  # seconds

        # Load persisted jobs
        self._load_jobs()

    # ═══════════════════════════════════════════════════════════
    # SCHEDULE ACTIONS
    # ═══════════════════════════════════════════════════════════

    def post_at(
        self,
        scheduled_time: str,
        photo: str,
        caption: str = "",
        location_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Schedule a photo post.

        Args:
            scheduled_time: When to post (e.g., "2024-03-01 10:00" or ISO format)
            photo: Path to image file
            caption: Post caption
            location_id: Optional location

        Returns:
            dict: Job info {id, job_type, scheduled_at, status}
        """
        dt = self._parse_time(scheduled_time)
        if not os.path.isfile(photo):
            raise FileNotFoundError(f"Photo not found: {photo}")

        job = SchedulerJob(
            job_type="post",
            scheduled_at=dt,
            params={"photo": os.path.abspath(photo), "caption": caption, "location_id": location_id},
        )
        self._add_job(job)
        logger.info(f"📅 Scheduled post at {dt.isoformat()} | id={job.id}")
        return job.to_dict()

    def story_at(
        self,
        scheduled_time: str,
        photo: Optional[str] = None,
        video: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Schedule a story.

        Args:
            scheduled_time: When to post
            photo: Path to image (mutually exclusive with video)
            video: Path to video

        Returns:
            dict: Job info
        """
        dt = self._parse_time(scheduled_time)
        media_path = photo or video
        if media_path and not os.path.isfile(media_path):
            raise FileNotFoundError(f"Media not found: {media_path}")

        job = SchedulerJob(
            job_type="story",
            scheduled_at=dt,
            params={
                "photo": os.path.abspath(photo) if photo else None,
                "video": os.path.abspath(video) if video else None,
            },
        )
        self._add_job(job)
        logger.info(f"📅 Scheduled story at {dt.isoformat()} | id={job.id}")
        return job.to_dict()

    def reel_at(
        self,
        scheduled_time: str,
        video: str,
        caption: str = "",
        cover_photo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Schedule a reel.

        Args:
            scheduled_time: When to post
            video: Path to video file
            caption: Reel caption
            cover_photo: Optional cover image path

        Returns:
            dict: Job info
        """
        dt = self._parse_time(scheduled_time)
        if not os.path.isfile(video):
            raise FileNotFoundError(f"Video not found: {video}")

        job = SchedulerJob(
            job_type="reel",
            scheduled_at=dt,
            params={
                "video": os.path.abspath(video),
                "caption": caption,
                "cover_photo": os.path.abspath(cover_photo) if cover_photo else None,
            },
        )
        self._add_job(job)
        logger.info(f"📅 Scheduled reel at {dt.isoformat()} | id={job.id}")
        return job.to_dict()

    def schedule_action(
        self,
        scheduled_time: str,
        action: Callable,
        action_name: str = "custom",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Schedule any custom action.

        Args:
            scheduled_time: When to execute
            action: Callable to execute
            action_name: Human-readable name
            **kwargs: Arguments to pass to action

        Returns:
            dict: Job info
        """
        dt = self._parse_time(scheduled_time)
        job = SchedulerJob(
            job_type="action",
            scheduled_at=dt,
            params={"action_name": action_name, "kwargs": kwargs},
        )
        job._action = action  # Not persisted
        self._add_job(job)
        logger.info(f"📅 Scheduled action '{action_name}' at {dt.isoformat()} | id={job.id}")
        return job.to_dict()

    # ═══════════════════════════════════════════════════════════
    # JOB MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def list_jobs(self, include_done: bool = False) -> List[Dict]:
        """List all scheduled jobs."""
        with self._lock:
            jobs = self._jobs if include_done else [j for j in self._jobs if j.status == "pending"]
            return [j.to_dict() for j in sorted(jobs, key=lambda j: j.scheduled_at)]

    def cancel(self, job_id: str) -> bool:
        """Cancel a pending job."""
        with self._lock:
            for job in self._jobs:
                if job.id == job_id and job.status == "pending":
                    job.status = "cancelled"
                    self._save_jobs()
                    logger.info(f"❌ Cancelled job {job_id}")
                    return True
        return False

    def clear_done(self) -> int:
        """Remove completed/failed/cancelled jobs."""
        with self._lock:
            before = len(self._jobs)
            self._jobs = [j for j in self._jobs if j.status == "pending"]
            self._save_jobs()
            removed = before - len(self._jobs)
            return removed

    # ═══════════════════════════════════════════════════════════
    # BACKGROUND WORKER
    # ═══════════════════════════════════════════════════════════

    def start(self) -> None:
        """Start background worker thread."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="scheduler-worker")
        self._worker_thread.start()
        logger.info(f"▶️ Scheduler started | {len([j for j in self._jobs if j.status == 'pending'])} pending jobs")

    def stop(self) -> None:
        """Stop background worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
            self._worker_thread = None
        logger.info("⏹️ Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def _worker_loop(self) -> None:
        """Background worker — checks for due jobs."""
        while self._running:
            try:
                self._check_and_execute()
            except Exception as e:
                logger.error(f"Scheduler worker error: {e}")
            time.sleep(self._check_interval)

    def _check_and_execute(self) -> None:
        """Check for due jobs and execute them."""
        now = datetime.now()
        with self._lock:
            due_jobs = [
                j for j in self._jobs
                if j.status == "pending" and j.scheduled_at <= now
            ]

        for job in due_jobs:
            self._execute_job(job)

    def _execute_job(self, job: SchedulerJob) -> None:
        """Execute a single job."""
        job.status = "running"
        job.executed_at = datetime.now()
        logger.info(f"🚀 Executing job {job.id} ({job.job_type})")

        try:
            if job.job_type == "post":
                result = self._upload.photo(
                    path=job.params["photo"],
                    caption=job.params.get("caption", ""),
                )
                job.result = {"media_id": result} if result else None

            elif job.job_type == "story":
                if job.params.get("photo"):
                    result = self._stories.upload_photo(path=job.params["photo"])
                elif job.params.get("video"):
                    result = self._stories.upload_video(path=job.params["video"])
                else:
                    raise ValueError("No media specified for story")
                job.result = {"uploaded": True}

            elif job.job_type == "reel":
                result = self._upload.reel(
                    path=job.params["video"],
                    caption=job.params.get("caption", ""),
                )
                job.result = {"media_id": result} if result else None

            elif job.job_type == "action":
                action_fn = getattr(job, "_action", None)
                if action_fn:
                    result = action_fn(**job.params.get("kwargs", {}))
                    job.result = {"result": str(result)}

            job.status = "done"
            logger.info(f"✅ Job {job.id} completed")

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            logger.error(f"❌ Job {job.id} failed: {e}")

        with self._lock:
            self._save_jobs()

    # ═══════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════

    def _add_job(self, job: SchedulerJob) -> None:
        with self._lock:
            self._jobs.append(job)
            self._save_jobs()

    def _save_jobs(self) -> None:
        """Save jobs to JSON file."""
        try:
            data = [j.to_dict() for j in self._jobs]
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Save jobs error: {e}")

    def _load_jobs(self) -> None:
        """Load jobs from JSON file."""
        if not os.path.isfile(self._persist_path):
            return
        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._jobs = [SchedulerJob.from_dict(d) for d in data if d.get("status") == "pending"]
            logger.info(f"📂 Loaded {len(self._jobs)} pending jobs from {self._persist_path}")
        except Exception as e:
            logger.warning(f"Load jobs error: {e}")

    @staticmethod
    def _parse_time(time_str: str) -> datetime:
        """Parse time string to datetime."""
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(time_str)
        except ValueError:
            raise ValueError(f"Cannot parse time: '{time_str}'. Use format: YYYY-MM-DD HH:MM")

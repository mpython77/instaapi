"""
Async Scheduler API — Scheduled Actions
=========================================
Async version of SchedulerAPI. Full feature parity.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .scheduler import SchedulerJob

logger = logging.getLogger("instaapi.scheduler")


class AsyncSchedulerAPI:
    """Async Instagram post/story/reel scheduler with background worker."""

    def __init__(self, upload_api, stories_api, persist_path: str = "scheduler_jobs.json"):
        self._upload = upload_api
        self._stories = stories_api
        self._jobs: List[SchedulerJob] = []
        self._persist_path = persist_path
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._load_jobs()

    async def post_at(self, scheduled_time: str, photo: str, caption: str = "", location_id: Optional[int] = None) -> Dict[str, Any]:
        """Schedule a photo post."""
        job = SchedulerJob(job_type="post", scheduled_at=self._parse_time(scheduled_time), params={"photo": photo, "caption": caption, "location_id": location_id})
        self._add_job(job)
        return {"id": job['id'], "job_type": "post", "scheduled_at": job.scheduled_at.isoformat(), "status": job.status}

    async def story_at(self, scheduled_time: str, photo: Optional[str] = None, video: Optional[str] = None) -> Dict[str, Any]:
        """Schedule a story."""
        job = SchedulerJob(job_type="story", scheduled_at=self._parse_time(scheduled_time), params={"photo": photo, "video": video})
        self._add_job(job)
        return {"id": job['id'], "job_type": "story", "scheduled_at": job.scheduled_at.isoformat(), "status": job.status}

    async def reel_at(self, scheduled_time: str, video: str, caption: str = "", cover_photo: Optional[str] = None) -> Dict[str, Any]:
        """Schedule a reel."""
        job = SchedulerJob(job_type="reel", scheduled_at=self._parse_time(scheduled_time), params={"video": video, "caption": caption, "cover_photo": cover_photo})
        self._add_job(job)
        return {"id": job['id'], "job_type": "reel", "scheduled_at": job.scheduled_at.isoformat(), "status": job.status}

    def list_jobs(self, include_done: bool = False) -> List[Dict]:
        """List all scheduled jobs."""
        jobs = self._jobs if include_done else [j for j in self._jobs if j.status == "pending"]
        return [j.to_dict() for j in jobs]

    def cancel(self, job_id: str) -> bool:
        """Cancel a pending job."""
        for job in self._jobs:
            if job['id'] == job_id and job.status == "pending":
                job.status = "cancelled"
                self._save_jobs()
                return True
        return False

    async def start(self) -> None:
        """Start background worker."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Stop background worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def _worker_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(30)
                await self._check_and_execute()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

    async def _check_and_execute(self) -> None:
        now = datetime.now()
        for job in self._jobs:
            if job.status == "pending" and job.scheduled_at <= now:
                await self._execute_job(job)

    async def _execute_job(self, job: SchedulerJob) -> None:
        job.status = "running"
        try:
            if job.job_type == "post" and self._upload:
                await self._upload.photo(job.params.get("photo", ""), caption=job.params.get("caption", ""))
                job.status = "done"
            elif job.job_type == "story" and self._stories:
                if job.params.get("photo"):
                    await self._stories.upload_photo(job.params["photo"])
                job.status = "done"
            elif job.job_type == "reel" and self._upload:
                await self._upload.reel(job.params.get("video", ""), caption=job.params.get("caption", ""))
                job.status = "done"
            else:
                job.status = "failed"
                job.error = "API not available"
            job.executed_at = datetime.now()
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
        self._save_jobs()

    def _add_job(self, job: SchedulerJob) -> None:
        self._jobs.append(job)
        self._save_jobs()

    def _save_jobs(self) -> None:
        try:
            with open(self._persist_path, "w") as f:
                json.dump([j.to_dict() for j in self._jobs], f, indent=2, default=str)
        except Exception:
            pass

    def _load_jobs(self) -> None:
        try:
            if os.path.exists(self._persist_path):
                with open(self._persist_path) as f:
                    data = json.load(f)
                self._jobs = [SchedulerJob.from_dict(d) for d in data]
        except Exception:
            self._jobs = []

    @staticmethod
    def _parse_time(time_str: str) -> datetime:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        raise ValueError(f"Unsupported time format: {time_str}")

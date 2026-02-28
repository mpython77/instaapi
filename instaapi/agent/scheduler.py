"""
Agent Scheduler — Cron-like Task Scheduling
=============================================
Schedule agent tasks to run at specific times or intervals.

Features:
    - Cron-like scheduling (every N minutes/hours/days)
    - One-time delayed execution
    - Persistent schedule (survives restart)
    - Task queue with priorities
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("instaapi.agent.scheduler")


@dataclass
class ScheduledTask:
    """A scheduled task definition."""
    task_id: str
    prompt: str
    interval_seconds: int
    next_run: float  # Unix timestamp
    repeat: bool = True
    max_runs: int = 0  # 0 = unlimited
    run_count: int = 0
    enabled: bool = True
    created_at: str = ""
    last_run: str = ""
    last_result: str = ""

    def is_due(self) -> bool:
        """Check if task is due to run."""
        return self.enabled and time.time() >= self.next_run

    def schedule_next(self):
        """Schedule next run."""
        self.next_run = time.time() + self.interval_seconds
        self.run_count += 1
        self.last_run = datetime.now().isoformat()

    def should_continue(self) -> bool:
        """Check if task should continue running."""
        if not self.repeat:
            return False
        if self.max_runs > 0 and self.run_count >= self.max_runs:
            return False
        return True

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "interval_seconds": self.interval_seconds,
            "next_run": self.next_run,
            "repeat": self.repeat,
            "max_runs": self.max_runs,
            "run_count": self.run_count,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "last_result": self.last_result,
        }


class AgentScheduler:
    """
    Schedule agent tasks to run at intervals.

    Usage:
        scheduler = AgentScheduler(agent)

        # Every hour
        scheduler.add(
            "follower_check",
            prompt="Check @cristiano follower count and save to log",
            interval="1h",
        )

        # Every day at specific time
        scheduler.add(
            "daily_report",
            prompt="Generate engagement report for @myaccount",
            interval="24h",
        )

        # Start scheduler
        scheduler.start()

        # Stop
        scheduler.stop()
    """

    def __init__(self, agent=None, persist_path: str = ".instaapi_schedule.json"):
        self._agent = agent
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._persist_path = persist_path
        self._callback: Optional[Callable] = None

        # Load saved schedule
        self._load()

    def add(
        self,
        task_id: str,
        prompt: str,
        interval: str = "1h",
        repeat: bool = True,
        max_runs: int = 0,
        delay: str = "0s",
    ) -> ScheduledTask:
        """
        Add a scheduled task.

        Args:
            task_id: Unique task identifier
            prompt: Agent prompt to execute
            interval: Interval string (e.g., '30m', '1h', '24h', '7d')
            repeat: Whether to repeat
            max_runs: Max number of runs (0 = unlimited)
            delay: Initial delay before first run
        """
        interval_seconds = self._parse_interval(interval)
        delay_seconds = self._parse_interval(delay)

        task = ScheduledTask(
            task_id=task_id,
            prompt=prompt,
            interval_seconds=interval_seconds,
            next_run=time.time() + delay_seconds,
            repeat=repeat,
            max_runs=max_runs,
            created_at=datetime.now().isoformat(),
        )

        self._tasks[task_id] = task
        self._save()
        logger.info(f"Task scheduled: {task_id} (every {interval})")
        return task

    def remove(self, task_id: str) -> bool:
        """Remove a scheduled task."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save()
            return True
        return False

    def enable(self, task_id: str):
        """Enable a task."""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = True
            self._save()

    def disable(self, task_id: str):
        """Disable a task without removing it."""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = False
            self._save()

    def list_tasks(self) -> List[Dict]:
        """List all scheduled tasks."""
        tasks = []
        for task in self._tasks.values():
            next_run_dt = datetime.fromtimestamp(task.next_run)
            tasks.append({
                **task.to_dict(),
                "next_run_human": next_run_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "interval_human": self._format_interval(task.interval_seconds),
            })
        return tasks

    def start(self, callback: Optional[Callable] = None):
        """Start the scheduler in a background thread."""
        if self._running:
            return

        self._running = True
        self._callback = callback
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    # ═══════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════

    def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            for task in list(self._tasks.values()):
                if not task.is_due():
                    continue

                logger.info(f"Running scheduled task: {task.task_id}")

                try:
                    result = self._execute_task(task)
                    task.last_result = str(result)[:500]
                except Exception as e:
                    logger.error(f"Scheduled task error: {e}")
                    task.last_result = f"Error: {e}"

                if task.should_continue():
                    task.schedule_next()
                else:
                    task.enabled = False

                self._save()

                if self._callback:
                    self._callback(task.task_id, task.last_result)

            time.sleep(10)  # Check every 10 seconds

    def _execute_task(self, task: ScheduledTask) -> Any:
        """Execute a single task."""
        if self._agent is None:
            return "Error: no agent configured"

        result = self._agent.ask(task.prompt)
        return result.answer if result.success else result.error

    def _save(self):
        """Persist schedule to disk."""
        data = {tid: t.to_dict() for tid, t in self._tasks.items()}
        try:
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save schedule: {e}")

    def _load(self):
        """Load schedule from disk."""
        if not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for tid, tdata in data.items():
                self._tasks[tid] = ScheduledTask(**tdata)
        except (json.JSONDecodeError, IOError, TypeError):
            pass

    @staticmethod
    def _parse_interval(interval: str) -> int:
        """Parse interval string to seconds (e.g., '30m', '1h', '7d')."""
        if not interval or interval == "0":
            return 0

        interval = interval.strip().lower()
        multipliers = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
            "w": 604800,
        }

        for suffix, multiplier in multipliers.items():
            if interval.endswith(suffix):
                try:
                    value = float(interval[:-1])
                    return int(value * multiplier)
                except ValueError:
                    pass

        # Try as raw seconds
        try:
            return int(interval)
        except ValueError:
            raise ValueError(f"Invalid interval: '{interval}'. Use: 30s, 5m, 1h, 24h, 7d")

    @staticmethod
    def _format_interval(seconds: int) -> str:
        """Format seconds to human-readable interval."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        else:
            return f"{seconds // 86400}d"

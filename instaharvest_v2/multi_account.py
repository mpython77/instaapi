"""
Multi-Account Manager
=====================
Manage multiple Instagram accounts with rotation strategies.

Usage:
    from instaharvest_v2 import MultiAccountManager

    manager = MultiAccountManager()
    manager.add_account("account1.env")
    manager.add_account("account2.env")

    # Round-robin execution
    results = manager.round_robin(lambda ig: ig.users.get_by_username("test"))

    # Random pick
    ig = manager.random_pick()
    user = ig.users.get_by_username("cristiano")

    # Health check all accounts
    health = manager.healthcheck()
"""

import logging
import random
import time
import threading
from typing import Any, Callable, Dict, List, Optional, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from .instagram import Instagram

logger = logging.getLogger("instaharvest_v2.multi_account")

T = TypeVar("T")


class AccountInfo:
    """Metadata for a managed account."""

    def __init__(self, instagram_instance, source: str):
        self.ig = instagram_instance
        self.source = source  # env file path or identifier
        self.username: str = source  # Default to source, overwrite if we find ds_user_id
        self.is_healthy: bool = True
        self.last_used: float = 0.0
        self.use_count: int = 0
        self.error_count: int = 0
        self.last_error: Optional[str] = None
        self.cooldown_until: float = 0.0

        # Try to extract username
        try:
            sm = getattr(instagram_instance, "_session_mgr", None)
            if sm:
                sess = sm.get_session()
                extracted = str(getattr(sess, "ds_user_id", ""))
                if extracted:
                    self.username = extracted
        except Exception:
            pass

    @property
    def is_available(self) -> bool:
        return self.is_healthy and time.time() >= self.cooldown_until


class MultiAccountManager:
    """
    Manage multiple Instagram accounts.

    Strategies:
        - round_robin: rotate through accounts evenly
        - random_pick: random account selection
        - least_used: pick account with fewest requests
        - healthcheck: verify all accounts are working

    Safety:
        - Auto-cooldown on errors
        - Health monitoring
        - Per-account error tracking
    """

    def __init__(self, env_files: Optional[List[str]] = None):
        self._accounts: List[AccountInfo] = []
        self._lock = threading.Lock()
        self._robin_index = 0

        if env_files:
            for f in env_files:
                self.add_account(f)

    # ═══════════════════════════════════════════════════════════
    # ACCOUNT MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def add_account(self, env_file: str, debug: bool = False) -> Dict[str, Any]:
        """
        Load and add an account from .env file.

        Args:
            env_file: Path to .env file with session cookies
            debug: Enable debug logging

        Returns:
            dict: {username, source, status}
        """
        from .instagram import Instagram

        try:
            ig = Instagram.from_env(env_file, debug=debug)
            info = AccountInfo(ig, env_file)
            with self._lock:
                self._accounts.append(info)
            logger.info(f"➕ Added account: {info.username} from {env_file}")
            return {"username": info.username, "source": env_file, "status": "added"}
        except Exception as e:
            logger.error(f"❌ Failed to add account from {env_file}: {e}")
            return {"source": env_file, "status": "failed", "error": str(e)}

    def add_instance(self, ig_instance, name: str = "") -> None:
        """Add an existing Instagram instance."""
        info = AccountInfo(ig_instance, name or f"instance_{len(self._accounts)}")
        with self._lock:
            self._accounts.append(info)
        logger.info(f"➕ Added instance: {info.username}")

    def remove_account(self, username: str) -> bool:
        """Remove account by username."""
        with self._lock:
            before = len(self._accounts)
            self._accounts = [a for a in self._accounts if a.username != username]
            removed = before - len(self._accounts)
        if removed:
            logger.info(f"➖ Removed account: {username}")
        return removed > 0

    def get(self, username: str) -> Optional["Instagram"]:
        """Get Instagram instance by username."""
        with self._lock:
            for acc in self._accounts:
                if acc.username == username:
                    return acc.ig
        return None

    @property
    def accounts(self) -> List[Dict[str, Any]]:
        """List all accounts with status."""
        with self._lock:
            return [
                {
                    "username": a.username,
                    "source": a.source,
                    "is_healthy": a.is_healthy,
                    "is_available": a.is_available,
                    "use_count": a.use_count,
                    "error_count": a.error_count,
                    "last_error": a.last_error,
                }
                for a in self._accounts
            ]

    @property
    def count(self) -> int:
        return len(self._accounts)

    # ═══════════════════════════════════════════════════════════
    # ROTATION STRATEGIES
    # ═══════════════════════════════════════════════════════════

    def round_robin(self, action: Callable, skip_errors: bool = True) -> List[Dict[str, Any]]:
        """
        Execute action on each account in rotation.

        Args:
            action: Callable that receives Instagram instance, returns result
            skip_errors: Continue on error

        Returns:
            List of {username, result/error, success} dicts
        """
        results = []
        for acc in self._get_available_accounts():
            result = self._execute_on(acc, action, skip_errors)
            results.append(result)
        return results

    def random_pick(self) -> "Instagram":
        """
        Get a random available account.

        Returns:
            Instagram instance

        Raises:
            RuntimeError: If no accounts available
        """
        available = self._get_available_accounts()
        if not available:
            raise RuntimeError("No available accounts")
        acc = random.choice(available)
        acc.last_used = time.time()
        acc.use_count += 1
        return acc.ig

    def least_used(self) -> "Instagram":
        """
        Get the least-used available account.

        Returns:
            Instagram instance
        """
        available = self._get_available_accounts()
        if not available:
            raise RuntimeError("No available accounts")
        acc = min(available, key=lambda a: a.use_count)
        acc.last_used = time.time()
        acc.use_count += 1
        return acc.ig

    def execute(
        self,
        action: Callable,
        strategy: str = "least_used",
        retries: int = 2,
    ) -> Any:
        """
        Execute action with automatic account selection and retry.

        Args:
            action: Callable receiving Instagram instance
            strategy: 'round_robin', 'random', 'least_used'
            retries: Max retries with different accounts

        Returns:
            Action result

        Raises:
            RuntimeError: If all accounts fail
        """
        tried = set()
        last_error = None

        for attempt in range(retries + 1):
            available = [a for a in self._get_available_accounts() if a.username not in tried]
            if not available:
                break

            if strategy == "random":
                acc = random.choice(available)
            elif strategy == "round_robin":
                acc = available[self._robin_index % len(available)]
                self._robin_index += 1
            else:
                acc = min(available, key=lambda a: a.use_count)

            tried.add(acc.username)
            try:
                acc.last_used = time.time()
                acc.use_count += 1
                result = action(acc.ig)
                acc.error_count = 0
                return result
            except Exception as e:
                last_error = e
                acc.error_count += 1
                acc.last_error = str(e)
                if acc.error_count >= 3:
                    acc.cooldown_until = time.time() + 300  # 5 min cooldown
                    logger.warning(f"⏸️ Account {acc.username} cooldown (3+ errors)")
                logger.warning(f"Account {acc.username} error: {e}")

        raise RuntimeError(f"All accounts failed. Last error: {last_error}")

    # ═══════════════════════════════════════════════════════════
    # HEALTH CHECK
    # ═══════════════════════════════════════════════════════════

    def healthcheck(self) -> List[Dict[str, Any]]:
        """
        Verify all accounts are working.

        Returns:
            List of {username, healthy, response_time_ms, error} dicts
        """
        results = []
        for acc in self._accounts:
            start = time.time()
            try:
                user = acc.ig.users.get_by_username("instagram")
                elapsed = (time.time() - start) * 1000
                acc.is_healthy = True
                acc.error_count = 0
                results.append({
                    "username": acc.username,
                    "healthy": True,
                    "response_time_ms": round(elapsed, 1),
                })
                logger.info(f"✅ {acc.username} healthy ({elapsed:.0f}ms)")
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                acc.is_healthy = False
                acc.last_error = str(e)
                results.append({
                    "username": acc.username,
                    "healthy": False,
                    "response_time_ms": round(elapsed, 1),
                    "error": str(e),
                })
                logger.warning(f"❌ {acc.username} unhealthy: {e}")
        return results

    # ═══════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════

    def _get_available_accounts(self) -> List[AccountInfo]:
        with self._lock:
            return [a for a in self._accounts if a.is_available]

    def _execute_on(
        self,
        acc: AccountInfo,
        action: Callable,
        skip_errors: bool,
    ) -> Dict[str, Any]:
        """Execute action on a single account."""
        try:
            acc.last_used = time.time()
            acc.use_count += 1
            result = action(acc.ig)
            acc.error_count = 0
            return {"username": acc.username, "success": True, "result": result}
        except Exception as e:
            acc.error_count += 1
            acc.last_error = str(e)
            if acc.error_count >= 3:
                acc.cooldown_until = time.time() + 300
            if not skip_errors:
                raise
            return {"username": acc.username, "success": False, "error": str(e)}

    def close_all(self) -> None:
        """Close all account sessions."""
        for acc in self._accounts:
            try:
                acc.ig.close()
            except Exception:
                pass
        logger.info("🔒 All accounts closed")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close_all()

    def __len__(self):
        return len(self._accounts)

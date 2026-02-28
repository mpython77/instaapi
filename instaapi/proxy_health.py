"""
Proxy Health Checker
====================
Background thread that periodically checks proxy health.
Auto-deactivates dead proxies, reactivates recovered ones.
"""

import logging
import threading
import time
from typing import Optional

from .proxy_manager import ProxyManager

logger = logging.getLogger("instaapi.proxy_health")

# Test URL — lightweight Instagram endpoint
HEALTH_CHECK_URL = "https://www.instagram.com/web/__mid/"


class ProxyHealthChecker:
    """
    Background proxy health monitoring.

    Usage:
        checker = ProxyHealthChecker(proxy_manager, interval=300)
        checker.start()      # Background check every 5 min
        checker.check_all()  # Manual check now
        checker.stop()       # Stop background thread
    """

    def __init__(
        self,
        proxy_manager: ProxyManager,
        interval: float = 300,  # 5 minutes
        timeout: float = 10.0,
        event_emitter=None,
    ):
        """
        Args:
            proxy_manager: ProxyManager instance
            interval: Seconds between health checks
            timeout: Timeout per proxy check (seconds)
            event_emitter: Optional EventEmitter for notifications
        """
        self._proxy_mgr = proxy_manager
        self._interval = interval
        self._timeout = timeout
        self._events = event_emitter
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

    def start(self) -> None:
        """Start background health checking."""
        if self._running:
            return

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="proxy-health-checker",
        )
        self._thread.start()
        logger.info(f"Proxy health checker started (interval={self._interval}s)")

    def stop(self) -> None:
        """Stop background health checking."""
        self._stop_event.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Proxy health checker stopped")

    def _run_loop(self) -> None:
        """Background loop."""
        while not self._stop_event.is_set():
            try:
                self.check_all()
            except Exception as e:
                logger.error(f"Health check error: {e}")

            # Wait with interruptible sleep
            self._stop_event.wait(self._interval)

    def check_all(self) -> dict:
        """
        Check all proxies right now.

        Returns:
            dict: {total, alive, dead, recovered, results: [{url, alive, latency}]}
        """
        import requests

        proxies = self._proxy_mgr._proxies
        results = []
        alive_count = 0
        dead_count = 0
        recovered_count = 0

        for url, info in list(proxies.items()):
            is_alive, latency = self._check_proxy(url)
            results.append({
                "url": url[:40] + "..." if len(url) > 40 else url,
                "alive": is_alive,
                "latency": round(latency, 3) if latency else None,
                "was_active": info.is_active,
            })

            if is_alive:
                alive_count += 1
                if not info.is_active:
                    # Proxy recovered — reactivate
                    info.is_active = True
                    info.consecutive_failures = 0
                    recovered_count += 1
                    logger.info(f"Proxy recovered: {url[:30]}...")
            else:
                dead_count += 1
                if info.is_active:
                    info.is_active = False
                    logger.warning(f"Proxy dead: {url[:30]}...")

        summary = {
            "total": len(proxies),
            "alive": alive_count,
            "dead": dead_count,
            "recovered": recovered_count,
            "results": results,
        }

        logger.debug(f"Health check: {alive_count}/{len(proxies)} alive")

        # Emit event
        if self._events and recovered_count > 0:
            try:
                from .events import EventType
                self._events.emit(
                    EventType.PROXY_ROTATE,
                    extra={"recovered": recovered_count, **summary},
                )
            except Exception:
                pass

        return summary

    def _check_proxy(self, proxy_url: str) -> tuple:
        """
        Test a single proxy.

        Returns:
            (is_alive: bool, latency: float or None)
        """
        try:
            from curl_cffi import requests as curl_requests

            start = time.time()
            resp = curl_requests.get(
                HEALTH_CHECK_URL,
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=self._timeout,
                allow_redirects=False,
                # SSL verify disabled — proxy always present for health checks\n                # Proxy MITM is expected in proxy health checking\n                verify=False,
                impersonate="chrome142",
            )
            latency = time.time() - start
            # Instagram returns 200 or 302 for valid requests
            return resp.status_code < 500, latency
        except Exception:
            return False, None

    @property
    def is_running(self) -> bool:
        """Check if health checker is running."""
        return self._running

    def __del__(self):
        self.stop()

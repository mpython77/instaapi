"""
Proxy Manager
=============
Smart proxy rotation system:
- Round-robin, random, weighted strategies
- Proxy scoring (speed + success rate)
- Health checking and automatic removal
- Sticky sessions
"""

import time
import random
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

from .config import PROXY_MAX_FAILURES, PROXY_MIN_SCORE


class RotationStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    WEIGHTED = "weighted"  # Score-based


@dataclass
class ProxyInfo:
    """Detailed info about a single proxy"""

    url: str  # "socks5://user:pass@ip:port" or "http://ip:port"
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    total_response_time: float = 0.0
    is_active: bool = True
    last_used: float = 0.0
    last_check: float = 0.0
    sticky_session_id: Optional[str] = None

    @property
    def score(self) -> float:
        """Proxy quality score (0.0 - 1.0)"""
        if self.total_requests == 0:
            return 1.0  # New proxy - default high score

        success_rate = self.successful_requests / self.total_requests
        avg_response = (
            self.total_response_time / self.total_requests
            if self.total_requests > 0
            else 5.0
        )

        # Speed score: under 1s = 1.0, over 5s = 0.0
        speed_score = max(0.0, min(1.0, 1.0 - (avg_response - 1.0) / 4.0))

        # 70% success + 30% speed
        return success_rate * 0.7 + speed_score * 0.3

    @property
    def avg_response_time(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time / self.total_requests


class ProxyManager:
    """
    Smart proxy management system.

    Usage:
        pm = ProxyManager()
        pm.add_proxies([
            "socks5://user:pass@ip:port",
            "http://ip:port",
            "socks5://ip:port",
        ])
        proxy = pm.get_proxy()
        pm.report_success(proxy, response_time=0.5)
        pm.report_failure(proxy)
    """

    def __init__(self, strategy: RotationStrategy = RotationStrategy.WEIGHTED):
        self._proxies: Dict[str, ProxyInfo] = {}
        self._strategy = strategy
        self._index = 0
        self._lock = threading.Lock()
        self._sticky_map: Dict[str, str] = {}  # session_id -> proxy_url

    def add_proxies(self, proxy_urls: List[str]) -> None:
        """Add a list of proxies."""
        with self._lock:
            for url in proxy_urls:
                url = url.strip()
                if url and url not in self._proxies:
                    self._proxies[url] = ProxyInfo(url=url)

    def add_proxy(self, proxy_url: str) -> None:
        """Add a single proxy."""
        self.add_proxies([proxy_url])

    def remove_proxy(self, proxy_url: str) -> None:
        """Remove a proxy."""
        with self._lock:
            self._proxies.pop(proxy_url, None)

    def get_proxy(self, session_id: Optional[str] = None) -> Optional[str]:
        """
        Get the next proxy.

        Args:
            session_id: Identifier for sticky sessions.
                        Same session_id always returns the same proxy.

        Returns:
            Proxy URL or None (if no proxies available)
        """
        with self._lock:
            # Check sticky session
            if session_id and session_id in self._sticky_map:
                sticky_url = self._sticky_map[session_id]
                if sticky_url in self._proxies and self._proxies[sticky_url].is_active:
                    self._proxies[sticky_url].last_used = time.time()
                    return sticky_url

            active_proxies = [p for p in self._proxies.values() if p.is_active]
            if not active_proxies:
                return None

            proxy = self._select_proxy(active_proxies)
            proxy.last_used = time.time()

            # Save sticky session
            if session_id:
                self._sticky_map[session_id] = proxy.url

            return proxy.url

    def _select_proxy(self, active: List[ProxyInfo]) -> ProxyInfo:
        """Select proxy based on strategy."""
        if self._strategy == RotationStrategy.ROUND_ROBIN:
            self._index = self._index % len(active)
            proxy = active[self._index]
            self._index += 1
            return proxy

        elif self._strategy == RotationStrategy.RANDOM:
            return random.choice(active)

        else:  # WEIGHTED
            # Weighted random selection based on score
            scores = [max(p.score, 0.01) for p in active]
            total = sum(scores)
            weights = [s / total for s in scores]
            return random.choices(active, weights=weights, k=1)[0]

    def report_success(self, proxy_url: str, response_time: float = 0.0) -> None:
        """Record successful request."""
        with self._lock:
            if proxy_url in self._proxies:
                p = self._proxies[proxy_url]
                p.total_requests += 1
                p.successful_requests += 1
                p.consecutive_failures = 0
                p.total_response_time += response_time

    def report_failure(self, proxy_url: str) -> None:
        """Record failed request."""
        with self._lock:
            if proxy_url in self._proxies:
                p = self._proxies[proxy_url]
                p.total_requests += 1
                p.failed_requests += 1
                p.consecutive_failures += 1

                # Too many consecutive failures - deactivate
                if p.consecutive_failures >= PROXY_MAX_FAILURES:
                    p.is_active = False

                # Score too low - deactivate
                if p.total_requests >= 10 and p.score < PROXY_MIN_SCORE:
                    p.is_active = False

    def get_curl_proxy(self, session_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get proxy in curl_cffi format.
        Returns: {"http": url, "https": url} or None
        """
        proxy_url = self.get_proxy(session_id)
        if not proxy_url:
            return None
        return {"http": proxy_url, "https": proxy_url}

    def reactivate_all(self) -> None:
        """Reactivate all deactivated proxies."""
        with self._lock:
            for p in self._proxies.values():
                p.is_active = True
                p.consecutive_failures = 0

    def get_stats(self) -> Dict:
        """Get proxy statistics."""
        with self._lock:
            active = [p for p in self._proxies.values() if p.is_active]
            inactive = [p for p in self._proxies.values() if not p.is_active]
            return {
                "total": len(self._proxies),
                "active": len(active),
                "inactive": len(inactive),
                "proxies": [
                    {
                        "url": p.url[:30] + "...",
                        "score": round(p.score, 3),
                        "requests": p.total_requests,
                        "success_rate": (
                            round(p.successful_requests / p.total_requests, 3)
                            if p.total_requests > 0
                            else 1.0
                        ),
                        "avg_response": round(p.avg_response_time, 3),
                        "active": p.is_active,
                    }
                    for p in self._proxies.values()
                ],
            }

    @property
    def has_proxies(self) -> bool:
        with self._lock:
            return bool(self._proxies)

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(1 for p in self._proxies.values() if p.is_active)

    def set_strategy(self, strategy: RotationStrategy) -> None:
        """Change rotation strategy."""
        self._strategy = strategy

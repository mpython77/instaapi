"""
Rate Limit Dashboard
====================
Terminal-based real-time statistics display.
Shows request counts, rate limit usage, proxy health, and event metrics.
"""

import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger("instaharvest_v2.dashboard")


class Dashboard:
    """
    Real-time statistics dashboard for instaharvest_v2.

    Usage:
        ig = Instagram.from_env()
        ig.dashboard.show()       # Pretty terminal output
        stats = ig.dashboard.status()  # Programmatic access
    """

    def __init__(
        self,
        rate_limiter=None,
        proxy_manager=None,
        session_manager=None,
        event_emitter=None,
    ):
        self._rate_limiter = rate_limiter
        self._proxy_mgr = proxy_manager
        self._session_mgr = session_manager
        self._events = event_emitter

        # Counters (updated via events)
        self._total_requests = 0
        self._total_errors = 0
        self._total_retries = 0
        self._rate_limits_hit = 0
        self._challenges_hit = 0
        self._start_time = time.time()

        # Auto-register event listeners
        if self._events:
            self._register_listeners()

    def _register_listeners(self) -> None:
        """Register event listeners for auto-tracking."""
        from .events import EventType

        self._events.on(EventType.REQUEST, lambda e: self._inc("requests"))
        self._events.on(EventType.ERROR, lambda e: self._inc("errors"))
        self._events.on(EventType.RETRY, lambda e: self._inc("retries"))
        self._events.on(EventType.RATE_LIMIT, lambda e: self._inc("rate_limits"))
        self._events.on(EventType.CHALLENGE, lambda e: self._inc("challenges"))

    def _inc(self, counter: str) -> None:
        """Increment a counter."""
        if counter == "requests":
            self._total_requests += 1
        elif counter == "errors":
            self._total_errors += 1
        elif counter == "retries":
            self._total_retries += 1
        elif counter == "rate_limits":
            self._rate_limits_hit += 1
        elif counter == "challenges":
            self._challenges_hit += 1

    def status(self) -> Dict[str, Any]:
        """
        Get current statistics as dict.

        Returns:
            {
                uptime, requests, errors, retries, rate_limits,
                challenges, requests_per_min, error_rate,
                rate_limiter: {category: remaining},
                proxies: {total, active, inactive},
                sessions: {total, active},
            }
        """
        uptime = time.time() - self._start_time
        rpm = (self._total_requests / uptime * 60) if uptime > 0 else 0
        error_rate = (
            self._total_errors / self._total_requests * 100
            if self._total_requests > 0
            else 0
        )

        result = {
            "uptime_seconds": round(uptime, 1),
            "uptime_human": self._format_uptime(uptime),
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "total_retries": self._total_retries,
            "rate_limits_hit": self._rate_limits_hit,
            "challenges_hit": self._challenges_hit,
            "requests_per_min": round(rpm, 2),
            "error_rate_pct": round(error_rate, 2),
        }

        # Rate limiter info
        if self._rate_limiter:
            from .config import RATE_LIMITS
            rate_info = {}
            for category in RATE_LIMITS:
                remaining = self._rate_limiter.get_remaining(category)
                rate_info[category] = remaining
            result["rate_limits"] = rate_info

        # Proxy info
        if self._proxy_mgr and self._proxy_mgr.has_proxies:
            result["proxies"] = self._proxy_mgr.get_stats()

        # Session info
        if self._session_mgr:
            sessions = self._session_mgr.get_all_sessions()
            result["sessions"] = {
                "total": len(sessions),
            }

        return result

    def show(self) -> str:
        """
        Display dashboard in terminal.

        Returns:
            Formatted string (also printed to stdout)
        """
        stats = self.status()
        lines = []

        lines.append("")
        lines.append("╔══════════════════════════════════════════╗")
        lines.append("║       📊  instaharvest_v2 Dashboard             ║")
        lines.append("╠══════════════════════════════════════════╣")
        lines.append(f"║  ⏱  Uptime:    {stats['uptime_human']:>24s} ║")
        lines.append(f"║  📨 Requests:  {stats['total_requests']:>24d} ║")
        lines.append(f"║  ⚡ Req/min:   {stats['requests_per_min']:>24.1f} ║")
        lines.append(f"║  ❌ Errors:    {stats['total_errors']:>24d} ║")
        lines.append(f"║  🔄 Retries:   {stats['total_retries']:>24d} ║")
        lines.append(f"║  ⚠️  Rate Lim:  {stats['rate_limits_hit']:>24d} ║")
        lines.append(f"║  🛡  Challenges:{stats['challenges_hit']:>24d} ║")
        lines.append(f"║  📉 Error %:   {stats['error_rate_pct']:>23.1f}% ║")

        # Proxy info
        if "proxies" in stats:
            p = stats["proxies"]
            lines.append("╠══════════════════════════════════════════╣")
            lines.append(f"║  🌐 Proxies:   {p['active']:>3d}/{p['total']:<3d} active            ║")

        # Sessions
        if "sessions" in stats:
            s = stats["sessions"]
            lines.append(f"║  🔑 Sessions:  {s['total']:>24d} ║")

        lines.append("╚══════════════════════════════════════════╝")
        lines.append("")

        output = "\n".join(lines)
        print(output)
        return output

    def reset(self) -> None:
        """Reset all counters."""
        self._total_requests = 0
        self._total_errors = 0
        self._total_retries = 0
        self._rate_limits_hit = 0
        self._challenges_hit = 0
        self._start_time = time.time()

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Format seconds to human-readable."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m}m {s}s"
        else:
            h, remainder = divmod(int(seconds), 3600)
            m, s = divmod(remainder, 60)
            return f"{h}h {m}m {s}s"

    def __repr__(self) -> str:
        return f"Dashboard(requests={self._total_requests}, errors={self._total_errors})"

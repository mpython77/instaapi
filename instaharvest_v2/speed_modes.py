"""
Speed Modes
===========
3 async operation modes with different speed/safety tradeoffs.

SAFE  — ban-proof, low concurrency, human-like delays
FAST  — balanced speed, moderate risk
TURBO — maximum throughput, proxy required

Each mode defines:
    - max_concurrency: global async semaphore limit
    - delay_range: (min, max) seconds between requests
    - rate_per_minute: max requests per minute per IP
    - burst_size: max burst before enforcing delay
    - proxy_multiplier: concurrency multiplied by proxy count
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SpeedMode:
    """Configuration for a speed mode."""
    name: str
    max_concurrency: int         # Global semaphore limit (no proxy)
    delay_range: Tuple[float, float]  # (min, max) delay in seconds
    rate_per_minute: int         # Max req/min per IP
    burst_size: int              # Allow N fast requests before delay
    proxy_multiplier: float      # Concurrency per proxy added
    error_backoff: float         # Extra delay multiplier on errors


# ─── PRESETS ─────────────────────────────────────────────

SAFE = SpeedMode(
    name="safe",
    max_concurrency=5,
    delay_range=(0.8, 2.0),
    rate_per_minute=30,
    burst_size=3,
    proxy_multiplier=3.0,    # +3 concurrent per proxy
    error_backoff=2.0,
)

FAST = SpeedMode(
    name="fast",
    max_concurrency=15,
    delay_range=(0.2, 0.8),
    rate_per_minute=60,
    burst_size=8,
    proxy_multiplier=5.0,    # +5 concurrent per proxy
    error_backoff=1.5,
)

TURBO = SpeedMode(
    name="turbo",
    max_concurrency=50,
    delay_range=(0.05, 0.3),
    rate_per_minute=120,
    burst_size=20,
    proxy_multiplier=10.0,   # +10 concurrent per proxy
    error_backoff=1.2,
)

UNLIMITED = SpeedMode(
    name="unlimited",
    max_concurrency=1000,
    delay_range=(0.0, 0.0),   # no delay at all
    rate_per_minute=999999,   # practically unlimited
    burst_size=1000,
    proxy_multiplier=10.0,
    error_backoff=1.0,        # no backoff increase
)

# ─── REGISTRY ────────────────────────────────────────────

MODES = {
    "safe": SAFE,
    "fast": FAST,
    "turbo": TURBO,
    "unlimited": UNLIMITED,
}


def get_mode(name: str = "safe") -> SpeedMode:
    """Get speed mode by name. Default: SAFE."""
    mode = MODES.get(name.lower())
    if not mode:
        raise ValueError(f"Unknown mode '{name}'. Available: {list(MODES.keys())}")
    return mode

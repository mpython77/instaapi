"""
Retry Configuration
===================
Configurable retry/backoff for HTTP requests.
Exponential backoff with jitter and ceiling.
"""

import random
from dataclasses import dataclass, field
from typing import Set, Type

from .exceptions import (
    RateLimitError,
    NetworkError,
    ChallengeRequired,
    CheckpointRequired,
    InstagramError,
)


@dataclass
class RetryConfig:
    """
    Configurable retry/backoff settings.

    Args:
        max_retries: Maximum retry attempts (default: 3)
        backoff_factor: Exponential base (default: 2.0)
        backoff_max: Maximum delay ceiling in seconds (default: 60.0)
        jitter: Add random ±30% jitter to delay (default: True)
        retry_on: Set of exception types to retry on

    Usage:
        retry = RetryConfig(max_retries=5, backoff_max=120, jitter=True)
        delay = retry.calculate_delay(attempt=2)  # ~4.0s ±30%
    """

    max_retries: int = 3
    backoff_factor: float = 2.0
    backoff_max: float = 60.0
    jitter: bool = True
    retry_on: Set[Type[Exception]] = field(default_factory=lambda: {
        RateLimitError,
        NetworkError,
        ChallengeRequired,
        CheckpointRequired,
    })

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number (0-indexed).

        Formula: min(backoff_factor ^ attempt, backoff_max) * jitter
        Jitter: random multiplier in range [0.7, 1.3]

        Args:
            attempt: Current attempt number (0 = first retry)

        Returns:
            Delay in seconds
        """
        delay = min(self.backoff_factor ** attempt, self.backoff_max)

        if self.jitter:
            jitter_multiplier = 1.0 + random.uniform(-0.3, 0.3)
            delay *= jitter_multiplier

        return max(0.1, delay)

    def should_retry(self, exception: Exception) -> bool:
        """Check if given exception is retryable."""
        return any(isinstance(exception, exc_type) for exc_type in self.retry_on)

    def __repr__(self) -> str:
        return (
            f"RetryConfig(max_retries={self.max_retries}, "
            f"backoff_factor={self.backoff_factor}, "
            f"backoff_max={self.backoff_max}, "
            f"jitter={self.jitter})"
        )

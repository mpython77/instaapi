"""
Retry & Error Recovery
======================
Automatic retry with exponential backoff and provider fallback.

Features:
    - Exponential backoff with jitter
    - Provider fallback chain (e.g., GPT fails → try Gemini)
    - Rate limit detection and wait
    - Configurable max retries
"""

import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

logger = logging.getLogger("instaapi.agent.retry")

# Retryable error patterns
RETRYABLE_ERRORS = [
    "rate limit",
    "rate_limit",
    "429",
    "too many requests",
    "quota exceeded",
    "overloaded",
    "server error",
    "500",
    "502",
    "503",
    "504",
    "timeout",
    "timed out",
    "connection",
    "network",
    "temporarily unavailable",
    "service unavailable",
    "capacity",
]

# Non-retryable errors (give up immediately)
FATAL_ERRORS = [
    "invalid api key",
    "authentication",
    "unauthorized",
    "401",
    "403",
    "not found",
    "404",
    "invalid model",
    "permission denied",
    "billing",
]


def is_retryable(error: Exception) -> bool:
    """Check if an error is retryable."""
    error_str = str(error).lower()
    for pattern in FATAL_ERRORS:
        if pattern in error_str:
            return False
    for pattern in RETRYABLE_ERRORS:
        if pattern in error_str:
            return True
    return False


def extract_retry_after(error: Exception) -> Optional[float]:
    """Try to extract retry-after seconds from error."""
    error_str = str(error).lower()
    # Look for "retry after X seconds" pattern
    import re
    match = re.search(r'retry.?after[:\s]*(\d+\.?\d*)', error_str)
    if match:
        return float(match.group(1))
    return None


class RetryPolicy:
    """
    Configurable retry policy with exponential backoff.

    Usage:
        policy = RetryPolicy(max_retries=3, base_delay=1.0)
        result = policy.execute(my_function, arg1, arg2)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e

                if not is_retryable(e):
                    logger.error(f"Non-retryable error: {e}")
                    raise

                if attempt >= self.max_retries:
                    logger.error(f"Max retries ({self.max_retries}) exhausted: {e}")
                    raise

                # Calculate delay
                delay = self._calculate_delay(attempt, e)
                logger.warning(
                    f"Retry {attempt + 1}/{self.max_retries} after {delay:.1f}s: {e}"
                )
                time.sleep(delay)

        raise last_error  # Should not reach here

    def _calculate_delay(self, attempt: int, error: Exception) -> float:
        """Calculate delay with exponential backoff and jitter."""
        # Check for explicit retry-after
        retry_after = extract_retry_after(error)
        if retry_after:
            return min(retry_after, self.max_delay)

        # Exponential backoff
        delay = self.base_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)

        # Add jitter
        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay


class ProviderFallback:
    """
    Fallback chain for AI providers.

    If the primary provider fails, try the next one in the chain.

    Usage:
        fallback = ProviderFallback(
            providers=["openai", "gemini", "deepseek"],
            api_keys={"openai": "sk-...", "gemini": "AIza..."},
        )
        provider = fallback.get_working_provider()
    """

    def __init__(
        self,
        providers: List[str],
        api_keys: Optional[Dict[str, str]] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.providers = providers
        self.api_keys = api_keys or {}
        self.retry_policy = retry_policy or RetryPolicy(max_retries=2)
        self._failed: Dict[str, float] = {}  # provider -> failure timestamp
        self._cooldown = 300  # 5 minutes cooldown for failed providers

    def get_provider(self, provider_factory: Callable):
        """Get first working provider from the chain."""
        from .providers import resolve_api_key

        current_time = time.time()

        for provider_name in self.providers:
            # Skip if recently failed (cooldown)
            if provider_name in self._failed:
                if current_time - self._failed[provider_name] < self._cooldown:
                    continue
                else:
                    del self._failed[provider_name]

            # Try to create provider
            api_key = self.api_keys.get(provider_name) or resolve_api_key(provider_name)
            if not api_key and provider_name != "ollama":
                continue

            try:
                provider = provider_factory(provider_name, api_key)
                logger.info(f"Using provider: {provider_name}")
                return provider
            except Exception as e:
                logger.warning(f"Provider '{provider_name}' failed: {e}")
                self._failed[provider_name] = current_time

        raise RuntimeError(
            f"All providers failed: {', '.join(self.providers)}. "
            "Check API keys and network connection."
        )

    def mark_failed(self, provider_name: str):
        """Mark a provider as temporarily failed."""
        self._failed[provider_name] = time.time()
        logger.warning(f"Provider marked as failed: {provider_name}")

    def reset(self):
        """Reset all failure states."""
        self._failed.clear()

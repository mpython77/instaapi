"""
Tests for RetryConfig: delay calculation, jitter, ceiling, should_retry.
"""

import pytest
from instaapi.retry import RetryConfig
from instaapi.exceptions import RateLimitError, NetworkError, LoginRequired


class TestRetryConfigDefaults:
    """Test default values."""

    def test_defaults(self):
        rc = RetryConfig()
        assert rc.max_retries == 3
        assert rc.backoff_factor == 2.0
        assert rc.backoff_max == 60.0
        assert rc.jitter is True

    def test_custom_values(self):
        rc = RetryConfig(max_retries=5, backoff_factor=3.0, backoff_max=120.0, jitter=False)
        assert rc.max_retries == 5
        assert rc.backoff_factor == 3.0
        assert rc.backoff_max == 120.0
        assert rc.jitter is False


class TestCalculateDelay:
    """Test delay calculation."""

    def test_exponential_without_jitter(self):
        rc = RetryConfig(backoff_factor=2.0, jitter=False)
        assert rc.calculate_delay(0) == 1.0   # 2^0 = 1
        assert rc.calculate_delay(1) == 2.0   # 2^1 = 2
        assert rc.calculate_delay(2) == 4.0   # 2^2 = 4
        assert rc.calculate_delay(3) == 8.0   # 2^3 = 8

    def test_ceiling(self):
        rc = RetryConfig(backoff_factor=2.0, backoff_max=10.0, jitter=False)
        assert rc.calculate_delay(10) == 10.0  # 2^10=1024 → capped at 10

    def test_jitter_range(self):
        rc = RetryConfig(backoff_factor=2.0, backoff_max=60.0, jitter=True)
        delays = [rc.calculate_delay(2) for _ in range(100)]
        # 2^2 = 4.0, jitter ±30% = [2.8, 5.2]
        assert all(2.5 <= d <= 5.5 for d in delays)

    def test_minimum_delay(self):
        rc = RetryConfig(backoff_factor=0.01, jitter=False)
        assert rc.calculate_delay(0) >= 0.1

    def test_factor_3(self):
        rc = RetryConfig(backoff_factor=3.0, jitter=False)
        assert rc.calculate_delay(0) == 1.0   # 3^0 = 1
        assert rc.calculate_delay(2) == 9.0   # 3^2 = 9


class TestShouldRetry:
    """Test should_retry method."""

    def test_retryable_exceptions(self):
        rc = RetryConfig()
        assert rc.should_retry(RateLimitError("test")) is True
        assert rc.should_retry(NetworkError("test")) is True

    def test_non_retryable_exceptions(self):
        rc = RetryConfig()
        assert rc.should_retry(LoginRequired("test")) is False
        assert rc.should_retry(ValueError("test")) is False

    def test_custom_retry_on(self):
        rc = RetryConfig(retry_on={LoginRequired})
        assert rc.should_retry(LoginRequired("test")) is True
        assert rc.should_retry(RateLimitError("test")) is False


class TestRepr:
    """Test string representation."""

    def test_repr(self):
        rc = RetryConfig(max_retries=5)
        assert "max_retries=5" in repr(rc)

"""
Instagram API Exception Classes
"""


class InstagramError(Exception):
    """Base Instagram error class"""

    def __init__(self, message: str = "", status_code: int = 0, response: dict = None):
        self.message = message
        self.status_code = status_code
        self.response = response or {}
        super().__init__(self.message)


class LoginRequired(InstagramError):
    """Session expired or login required"""
    pass


class RateLimitError(InstagramError):
    """Too many requests - rate limited"""
    pass


class PrivateAccountError(InstagramError):
    """Private account - cannot access info"""
    pass


class NotFoundError(InstagramError):
    """User or resource not found"""
    pass


class ChallengeRequired(InstagramError):
    """Instagram challenge (captcha/phone verification) required"""

    @property
    def challenge_url(self) -> str:
        """Challenge URL from response."""
        challenge = self.response.get("challenge", {})
        if isinstance(challenge, dict):
            return challenge.get("url", "")
        return str(challenge) if challenge else ""

    @property
    def challenge_type(self) -> str:
        """Challenge type hint (if available)."""
        challenge = self.response.get("challenge", {})
        if isinstance(challenge, dict):
            return challenge.get("challenge_type", "unknown")
        return "unknown"


class CheckpointRequired(InstagramError):
    """Instagram checkpoint verification required"""
    pass


class ConsentRequired(InstagramError):
    """User consent required"""
    pass


class NetworkError(InstagramError):
    """Network error"""
    pass


class ProxyError(InstagramError):
    """Proxy-related error"""
    pass


class MediaNotFound(NotFoundError):
    """Media not found"""
    pass


class UserNotFound(NotFoundError):
    """User not found"""
    pass

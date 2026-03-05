"""
instaharvest_v2 — Powerful Instagram Private API Library
==================================================
curl_cffi engine, smart proxy rotation, anti-detection system.
Supports both sync and async modes.
"""

from .instagram import Instagram
from .async_instagram import AsyncInstagram
from .exceptions import (
    InstagramError,
    LoginRequired,
    RateLimitError,
    PrivateAccountError,
    NotFoundError,
    ChallengeRequired,
    CheckpointRequired,
    ConsentRequired,
    NetworkError,
    ProxyError,
    MediaNotFound,
    UserNotFound,
)
from .models import (
    User,
    UserShort,
    Media,
    Comment,
    Story,
    Highlight,
    DirectThread,
    DirectMessage,
    Location,
)
from .challenge import (
    ChallengeHandler,
    ChallengeType,
    ChallengeContext,
    ChallengeResult,
)
from .async_challenge import AsyncChallengeHandler
from .retry import RetryConfig
from .log_config import LogConfig, DebugLogger
from .events import EventEmitter, EventType, EventData
from .dashboard import Dashboard
from .plugin import Plugin, PluginManager
from .proxy_health import ProxyHealthChecker
from .story_composer import StoryComposer, StoryDraft
from .device_fingerprint import DeviceFingerprint
from .email_verifier import EmailVerifier
from .smart_rotation import SmartRotationCoordinator, RotationContext
from .multi_account import MultiAccountManager
from .api.export import ExportAPI, ExportFilter
from .api.analytics import AnalyticsAPI
from .api.scheduler import SchedulerAPI
from .api.growth import GrowthAPI, GrowthFilters, GrowthLimits
from .api.automation import AutomationAPI, AutomationLimits, TemplateEngine
from .api.monitor import MonitorAPI, AccountWatcher
from .api.bulk_download import BulkDownloadAPI
from .api.hashtag_research import HashtagResearchAPI
from .api.pipeline import PipelineAPI
from .api.ai_suggest import AISuggestAPI
from .api.audience import AudienceAPI
from .api.comment_manager import CommentManagerAPI
from .api.ab_test import ABTestAPI
from .api.public_data import PublicDataAPI
from .strategy import ProfileStrategy, PostsStrategy
from .parsers import (
    parse_count,
    parse_meta_tags,
    parse_graphql_user,
    parse_timeline_edges,
    parse_embed_media,
    parse_embed_html,
    parse_mobile_feed_item,
    parse_graphql_docid_media,
)
from .models.public_data import (
    PublicProfile,
    PublicPost,
    HashtagPost,
    ProfileSnapshot,
    PublicDataReport,
)

# Agent (lazy import — loaded only when needed)
def __getattr__(name):
    if name in ("InstaAgent", "AgentResult"):
        from .agent.core import InstaAgent, AgentResult
        return {"InstaAgent": InstaAgent, "AgentResult": AgentResult}[name]
    if name == "Permission":
        from .agent.permissions import Permission
        return Permission
    if name == "AgentCoordinator":
        from .agent.coordinator import AgentCoordinator
        return AgentCoordinator
    raise AttributeError(f"module 'instaharvest_v2' has no attribute {name!r}")

__version__ = "1.0.20"
__all__ = [
    "Instagram",
    "AsyncInstagram",
    # Exceptions
    "InstagramError",
    "LoginRequired",
    "RateLimitError",
    "PrivateAccountError",
    "NotFoundError",
    "ChallengeRequired",
    "CheckpointRequired",
    "ConsentRequired",
    "NetworkError",
    "ProxyError",
    "MediaNotFound",
    "UserNotFound",
    # Models
    "User",
    "UserShort",
    "Media",
    "Comment",
    "Story",
    "Highlight",
    "DirectThread",
    "DirectMessage",
    "Location",
    # Challenge
    "ChallengeHandler",
    "AsyncChallengeHandler",
    "ChallengeType",
    "ChallengeContext",
    "ChallengeResult",
    # Retry / Logging / Events
    "RetryConfig",
    "LogConfig",
    "DebugLogger",
    "EventEmitter",
    "EventType",
    "EventData",
    # Dashboard / Plugin / ProxyHealth / StoryComposer
    "Dashboard",
    "Plugin",
    "PluginManager",
    "ProxyHealthChecker",
    "StoryComposer",
    "StoryDraft",
    "DeviceFingerprint",
    "EmailVerifier",
    "SmartRotationCoordinator",
    "RotationContext",
    # Multi-Account
    "MultiAccountManager",
    # Export / Analytics / Scheduler / Growth / Automation
    "ExportAPI",
    "ExportFilter",
    "AnalyticsAPI",
    "SchedulerAPI",
    "GrowthAPI",
    "GrowthFilters",
    "GrowthLimits",
    "AutomationAPI",
    "AutomationLimits",
    "TemplateEngine",
    # Advanced modules
    "MonitorAPI",
    "AccountWatcher",
    "BulkDownloadAPI",
    "HashtagResearchAPI",
    "PipelineAPI",
    # Intelligence & Management
    "AISuggestAPI",
    "AudienceAPI",
    "CommentManagerAPI",
    "ABTestAPI",
    # Public Data (Supermetrics-style analytics)
    "PublicDataAPI",
    "PublicProfile",
    "PublicPost",
    "HashtagPost",
    "ProfileSnapshot",
    "PublicDataReport",
    # Strategy Configuration
    "ProfileStrategy",
    "PostsStrategy",
    # Agent (lazy import)
    "InstaAgent",
    "AgentResult",
    "Permission",
    "AgentCoordinator",
    # Parsers (standalone functions)
    "parse_count",
    "parse_meta_tags",
    "parse_graphql_user",
    "parse_timeline_edges",
    "parse_embed_media",
    "parse_embed_html",
    "parse_mobile_feed_item",
    "parse_graphql_docid_media",
]


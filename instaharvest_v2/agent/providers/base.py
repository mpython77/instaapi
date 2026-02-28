"""
Base AI Provider
================
Abstract interface for AI model providers.
All providers (OpenAI, Gemini, etc.) implement this interface.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("instaharvest_v2.agent.providers")


@dataclass
class ToolCall:
    """A tool call requested by the AI."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ProviderResponse:
    """Response from an AI provider."""
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: Dict[str, int] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


# InstaHarvest v2 tools schema — shared across providers
instaharvest_v2_TOOLS = [
    {
        "name": "run_instaharvest_v2_code",
        "description": (
            "Execute Python code that uses the InstaHarvest v2 library. "
            "The `ig` variable is a pre-configured Instagram client. "
            "Output results via print() or assign to a `result` variable. "
            "The sandbox includes: json, csv, re, math, datetime, pathlib."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code using InstaHarvest v2 (ig variable is available)",
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what the code does",
                },
            },
            "required": ["code", "description"],
        },
    },
    {
        "name": "save_to_file",
        "description": (
            "Save content to a file. Supported formats: "
            "CSV, JSON, JSONL, TXT, MD, TSV, XLSX (Excel). "
            "Only relative paths in the current directory are allowed. "
            "Returns full absolute path of the saved file. "
            "For Excel (.xlsx): pass JSON content (list of dicts or dict) — "
            "it will be auto-converted to Excel with headers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "File name with extension (e.g. results.json, data.csv)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["filename", "content"],
        },
    },
    {
        "name": "ask_user",
        "description": (
            "Ask the user a question to get additional information. "
            "Use when you need: username, credentials, preferences, "
            "file paths, or confirmation for sensitive actions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Question to ask the user",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read contents of a file from the current directory. "
            "Supports: CSV, JSON, JSONL, TXT, MD, TSV. "
            "Use to load previously saved data or check existing files."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "File name to read (e.g. data.csv, results.json)",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum lines to read (default: 100, max: 500)",
                },
            },
            "required": ["filename"],
        },
    },
    {
        "name": "list_files",
        "description": (
            "List files and directories in the current working directory "
            "or a specific subdirectory. Shows file names, sizes, and types."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Subdirectory to list (default: current directory '.')",
                },
                "pattern": {
                    "type": "string",
                    "description": "Optional glob pattern filter (e.g. '*.csv', '*.json')",
                },
            },
        },
    },
    {
        "name": "download_media",
        "description": (
            "Download Instagram media (photos, videos, stories, reels) "
            "to a local directory. Supports single posts, profile pics, "
            "and bulk downloads."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Instagram URL (post, reel, story) or username",
                },
                "output_dir": {
                    "type": "string",
                    "description": "Output directory (default: 'downloads/')",
                },
                "media_type": {
                    "type": "string",
                    "description": "Type: 'post', 'profile_pic', 'stories', 'reels', 'all'",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "analyze_data",
        "description": (
            "Analyze data from a file or raw data. Compute statistics, "
            "counts, averages, top/bottom items, distributions. "
            "Returns formatted analysis report."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "File path (data.csv, results.json) or raw JSON data",
                },
                "analysis_type": {
                    "type": "string",
                    "description": "Type: 'summary', 'top_n', 'distribution', 'compare', 'trend'",
                },
                "field": {
                    "type": "string",
                    "description": "Field/column to analyze (e.g. 'follower_count', 'like_count')",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of top/bottom items to show (default: 10)",
                },
            },
            "required": ["source", "analysis_type"],
        },
    },
    {
        "name": "http_request",
        "description": (
            "Make an HTTP GET or POST request to an external API or URL. "
            "Returns the response body. Use for fetching public data, "
            "webhooks, or integrating with external services."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "HTTP method: 'GET' or 'POST'",
                },
                "url": {
                    "type": "string",
                    "description": "Full URL to request",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers as key-value pairs",
                },
                "body": {
                    "type": "string",
                    "description": "Optional request body (for POST)",
                },
            },
            "required": ["method", "url"],
        },
    },
    {
        "name": "create_chart",
        "description": (
            "Create a chart/visualization from data and save as an image file. "
            "Supported types: bar, line, pie, horizontal_bar. "
            "Returns the saved image file path."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "description": "Type: 'bar', 'line', 'pie', 'horizontal_bar'",
                },
                "title": {
                    "type": "string",
                    "description": "Chart title",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "X-axis labels or category names",
                },
                "values": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Y-axis values or quantities",
                },
                "filename": {
                    "type": "string",
                    "description": "Output file name (default: chart.png)",
                },
            },
            "required": ["chart_type", "title", "labels", "values"],
        },
    },
    {
        "name": "search_web",
        "description": (
            "Search the web for information. Use when you need "
            "current data, trends, news, or facts that are not "
            "available in the InstaHarvest v2 library."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string",
                },
            },
            "required": ["query"],
        },
    },
]


class BaseProvider(ABC):
    """
    Abstract AI provider interface.

    All AI providers must implement:
        - generate(): send messages and get response with optional tool calls
    """

    def __init__(self, api_key: str, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self._total_tokens = 0

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.1,
    ) -> ProviderResponse:
        """
        Generate AI response.

        Args:
            messages: Chat history [{role, content}, ...]
            tools: Tool definitions (default: instaharvest_v2_TOOLS)
            temperature: Creativity (0=precise, 1=creative)

        Returns:
            ProviderResponse with content and/or tool_calls
        """
        ...

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider name for logging."""
        ...

    def format_tools(self, tools: Optional[List[Dict]] = None) -> List[Dict]:
        """Get tools in provider-specific format. Override if needed."""
        return tools or instaharvest_v2_TOOLS

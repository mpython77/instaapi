"""
Anthropic Claude Provider
=========================
Claude 4.6 / 4.5 / 4 series integration for InstaAgent.
Uses the `anthropic` Python SDK with tool use support.

Supported models:
    - claude-opus-4.6, claude-sonnet-4.6 (latest)
    - claude-haiku-4.5, claude-opus-4.5, claude-sonnet-4.5
    - claude-sonnet-4 (default, stable), claude-opus-4
    - claude-3-5-sonnet, claude-3-5-haiku

Install: pip install anthropic
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from .base import BaseProvider, ProviderResponse, ToolCall, INSTAAPI_TOOLS

logger = logging.getLogger("instaapi.agent.providers.claude")

DEFAULT_MODEL = "claude-sonnet-4-20250514"


class ClaudeProvider(BaseProvider):
    """Anthropic Claude provider with tool use."""

    def __init__(self, api_key: str, model: Optional[str] = None):
        super().__init__(api_key, model or DEFAULT_MODEL)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError:
                raise ImportError(
                    "Anthropic library not found. Install with:\n"
                    "  pip install anthropic\n"
                    "  or: pip install instaapi[agent]"
                )
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.1,
    ) -> ProviderResponse:
        client = self._get_client()

        # Extract system message
        system = ""
        claude_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system = msg["content"]
            elif msg.get("role") == "assistant":
                content = msg.get("content", "")
                if content:
                    claude_messages.append({"role": "assistant", "content": content})
            elif msg.get("role") == "tool":
                # Tool result for Claude
                claude_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_use_id", f"tool_{uuid.uuid4().hex[:8]}"),
                        "content": str(msg.get("content", "")),
                    }]
                })
            elif msg.get("role") == "user":
                content = msg.get("content", "")
                if content:
                    claude_messages.append({"role": "user", "content": content})

        # Merge consecutive same-role messages
        claude_messages = self._merge_messages(claude_messages)

        # Format tools for Claude
        claude_tools = self._format_claude_tools(tools or INSTAAPI_TOOLS)

        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": claude_messages,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if claude_tools:
            kwargs["tools"] = claude_tools

        try:
            response = client.messages.create(**kwargs)
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return ProviderResponse(content=f"AI error: {e}", finish_reason="error")

        # Parse response
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=dict(block.input) if block.input else {},
                ))

        # Usage
        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }
            self._total_tokens += usage["total_tokens"]

        finish = "tool_calls" if tool_calls else "stop"

        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish,
            usage=usage,
        )

    @staticmethod
    def _format_claude_tools(tools: List[Dict]) -> List[Dict]:
        """Convert generic tool schema to Claude format."""
        formatted = []
        for tool in tools:
            formatted.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
            })
        return formatted

    @staticmethod
    def _merge_messages(messages: List[Dict]) -> List[Dict]:
        """Merge consecutive messages with the same role (Claude requirement)."""
        if not messages:
            return []
        merged = [messages[0]]
        for msg in messages[1:]:
            if msg["role"] == merged[-1]["role"]:
                prev_content = merged[-1]["content"]
                new_content = msg["content"]
                if isinstance(prev_content, str) and isinstance(new_content, str):
                    merged[-1]["content"] = prev_content + "\n" + new_content
                elif isinstance(prev_content, list) and isinstance(new_content, list):
                    merged[-1]["content"] = prev_content + new_content
                else:
                    merged.append(msg)
            else:
                merged.append(msg)
        return merged

    @property
    def provider_name(self) -> str:
        return f"Claude ({self.model})"

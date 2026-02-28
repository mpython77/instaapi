"""
OpenAI Provider
===============
GPT-5 / GPT-4.1 / o-series integration for InstaAgent.

Supported models:
    - gpt-5.2, gpt-5, gpt-5-mini, gpt-5-nano
    - gpt-4.1, gpt-4.1-mini (default), gpt-4.1-nano
    - gpt-4o, gpt-4o-mini
    - o3, o3-pro, o3-mini, o4-mini
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from .base import BaseProvider, ProviderResponse, ToolCall, INSTAAPI_TOOLS

logger = logging.getLogger("instaharvest_v2.agent.providers.openai")

DEFAULT_MODEL = "gpt-4.1-mini"


class OpenAIProvider(BaseProvider):
    """OpenAI (GPT) provider."""

    def __init__(self, api_key: str, model: Optional[str] = None):
        super().__init__(api_key, model or DEFAULT_MODEL)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "OpenAI library not found. Install with:\n"
                    "  pip install openai\n"
                    "  or: pip install instaapi[agent]"
                )
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.1,
    ) -> ProviderResponse:
        client = self._get_client()

        # Format tools for OpenAI
        openai_tools = self._format_openai_tools(tools or INSTAAPI_TOOLS)

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return ProviderResponse(content=f"AI error: {e}", finish_reason="error")

        msg = response.choices[0].message
        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            self._total_tokens += response.usage.total_tokens

        # Parse tool calls
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {"raw": tc.function.arguments}

                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        return ProviderResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason or "stop",
            usage=usage,
        )

    @staticmethod
    def _format_openai_tools(tools: List[Dict]) -> List[Dict]:
        """Convert generic tool schema to OpenAI format."""
        formatted = []
        for tool in tools:
            formatted.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                },
            })
        return formatted

    @staticmethod
    def format_tool_result(tool_call_id: str, result: str) -> Dict:
        """Format tool result for OpenAI message history."""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": str(result),
        }

    @staticmethod
    def format_assistant_with_tools(content: str, tool_calls: List[ToolCall]) -> Dict:
        """Format assistant message with tool calls for OpenAI."""
        msg = {"role": "assistant", "content": content or None}
        if tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in tool_calls
            ]
        return msg

    @property
    def provider_name(self) -> str:
        return f"OpenAI ({self.model})"

"""
OpenAI-Compatible Provider (Universal)
=======================================
Works with ANY provider that supports OpenAI API format:
  - DeepSeek
  - Qwen (DashScope)
  - Groq
  - Together AI
  - Mistral (La Plateforme)
  - Ollama (local)
  - OpenRouter
  - Fireworks AI
  - Perplexity
  - xAI (Grok)
  - And any other OpenAI-compatible API

Usage:
    provider = OpenAICompatibleProvider(
        api_key="...",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
    )
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .base import BaseProvider, ProviderResponse, ToolCall, INSTAAPI_TOOLS

logger = logging.getLogger("instaharvest_v2.agent.providers.compatible")


# Pre-configured provider profiles
PROVIDER_PROFILES = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
        "name": "DeepSeek",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen3-32b",
        "env_key": "DASHSCOPE_API_KEY",
        "name": "Qwen",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "env_key": "GROQ_API_KEY",
        "name": "Groq",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "env_key": "TOGETHER_API_KEY",
        "name": "Together AI",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
        "env_key": "MISTRAL_API_KEY",
        "name": "Mistral",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "env_key": None,  # No key needed for local
        "name": "Ollama",
    },
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "default_model": "auto",
        "env_key": None,  # No key needed for local
        "name": "LM Studio",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-sonnet-4",
        "env_key": "OPENROUTER_API_KEY",
        "name": "OpenRouter",
    },
    "fireworks": {
        "base_url": "https://api.fireworks.ai/inference/v1",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "env_key": "FIREWORKS_API_KEY",
        "name": "Fireworks AI",
    },
    "perplexity": {
        "base_url": "https://api.perplexity.ai",
        "default_model": "sonar-pro",
        "env_key": "PERPLEXITY_API_KEY",
        "name": "Perplexity",
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-3-latest",
        "env_key": "XAI_API_KEY",
        "name": "xAI (Grok)",
    },
}


class OpenAICompatibleProvider(BaseProvider):
    """
    Universal provider for any OpenAI-compatible API.

    Just set base_url and model to connect to ANY compatible service.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: Optional[str] = None,
        provider_name_str: str = "OpenAI-Compatible",
        default_model: str = "gpt-4.1-mini",
    ):
        super().__init__(api_key, model or default_model)
        self._base_url = base_url
        self._provider_name_str = provider_name_str
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
            kwargs = {
                "api_key": self.api_key,
                "base_url": self._base_url,
            }
            # Ollama doesn't need a real key
            if "localhost" in self._base_url or "127.0.0.1" in self._base_url:
                kwargs["api_key"] = self.api_key or "ollama"

            self._client = OpenAI(**kwargs)
        return self._client

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.1,
    ) -> ProviderResponse:
        client = self._get_client()

        # Format tools
        openai_tools = self._format_tools(tools or INSTAAPI_TOOLS)

        # Clean messages — some providers don't support all fields
        clean_messages = self._clean_messages(messages)

        kwargs = {
            "model": self.model,
            "messages": clean_messages,
            "temperature": temperature,
        }

        # Some providers don't support tools well — try with, fallback without
        if openai_tools:
            kwargs["tools"] = openai_tools

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            error_str = str(e)
            # If tool calling not supported, retry without tools
            if "tool" in error_str.lower() or "function" in error_str.lower():
                logger.warning(f"{self._provider_name_str}: tool calling not supported, falling back to plain mode")
                kwargs.pop("tools", None)
                try:
                    response = client.chat.completions.create(**kwargs)
                except Exception as e2:
                    logger.error(f"{self._provider_name_str} API error: {e2}")
                    return ProviderResponse(content=f"AI error: {e2}", finish_reason="error")
            else:
                logger.error(f"{self._provider_name_str} API error: {e}")
                return ProviderResponse(content=f"AI error: {e}", finish_reason="error")

        msg = response.choices[0].message
        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            }
            self._total_tokens += usage.get("total_tokens", 0)

        # Parse tool calls
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {"raw": tc.function.arguments}
                tool_calls.append(ToolCall(
                    id=tc.id or f"call_{id(tc)}",
                    name=tc.function.name,
                    arguments=args,
                ))

        return ProviderResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason or "stop",
            usage=usage,
        )

    def _clean_messages(self, messages: List[Dict]) -> List[Dict]:
        """Clean messages for compatibility with various providers."""
        cleaned = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content")

            if role == "tool":
                # Some providers expect tool results differently
                cleaned.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", "unknown"),
                    "content": str(content or ""),
                })
            elif role == "assistant" and msg.get("tool_calls"):
                # Forward tool calls in assistant message
                cleaned.append(msg)
            else:
                if content is not None:
                    cleaned.append({"role": role, "content": str(content)})
        return cleaned

    @staticmethod
    def _format_tools(tools: List[Dict]) -> List[Dict]:
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

    @property
    def provider_name(self) -> str:
        return f"{self._provider_name_str} ({self.model})"

    @classmethod
    def from_profile(
        cls,
        profile_name: str,
        api_key: str,
        model: Optional[str] = None,
    ) -> "OpenAICompatibleProvider":
        """
        Create provider from a pre-configured profile.

        Args:
            profile_name: One of: deepseek, qwen, groq, together, mistral,
                         ollama, openrouter, fireworks, perplexity, xai
            api_key: API key for the service
            model: Optional model override
        """
        profile = PROVIDER_PROFILES.get(profile_name.lower())
        if not profile:
            available = ", ".join(sorted(PROVIDER_PROFILES.keys()))
            raise ValueError(
                f"Noma'lum profil: '{profile_name}'. "
                f"Mavjud profillar: {available}"
            )

        return cls(
            api_key=api_key,
            base_url=profile["base_url"],
            model=model or profile["default_model"],
            provider_name_str=profile["name"],
        )

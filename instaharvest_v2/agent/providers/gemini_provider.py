"""
Gemini Provider
===============
Google Gemini 3.x / 2.5 integration for InstaAgent.

Supported models:
    - gemini-3.1-pro (preview, most advanced)
    - gemini-3-pro, gemini-3-flash, gemini-3-flash-preview
    - gemini-2.5-pro, gemini-2.5-flash (stable)
    - gemini-2.5-flash-lite, gemini-2.0-flash
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from .base import BaseProvider, ProviderResponse, ToolCall, instaharvest_v2_TOOLS

logger = logging.getLogger("instaharvest_v2.agent.providers.gemini")

DEFAULT_MODEL = "gemini-3-flash-preview"


class GeminiProvider(BaseProvider):
    """Google Gemini provider."""

    def __init__(self, api_key: str, model: Optional[str] = None):
        super().__init__(api_key, model or DEFAULT_MODEL)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
            except ImportError:
                raise ImportError(
                    "Google GenAI library not found. Install with:\n"
                    "  pip install google-genai\n"
                    "  or: pip install instaharvest_v2[agent]"
                )
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.1,
    ) -> ProviderResponse:
        client = self._get_client()

        try:
            from google.genai import types
        except ImportError:
            raise ImportError("google-genai not installed: pip install google-genai")

        # Build Gemini tools
        gemini_tools = self._build_gemini_tools(tools or instaharvest_v2_TOOLS)

        # Convert messages to Gemini format
        gemini_contents = self._convert_messages(messages)

        # Extract system instruction
        system_instruction = None
        for msg in messages:
            if msg.get("role") == "system":
                system_instruction = msg["content"]
                break

        try:
            config = types.GenerateContentConfig(
                temperature=temperature,
                tools=gemini_tools if gemini_tools else None,
                system_instruction=system_instruction,
            )

            # Retry logic for transient 500/503 errors
            response = None
            last_error = None
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=self.model,
                        contents=gemini_contents,
                        config=config,
                    )
                    last_error = None
                    break
                except Exception as api_err:
                    err_str = str(api_err)
                    # Retry on 500 INTERNAL, 503 UNAVAILABLE, DEADLINE_EXCEEDED
                    if any(code in err_str for code in ["500", "503", "INTERNAL", "UNAVAILABLE", "DEADLINE_EXCEEDED"]):
                        wait_time = 2 ** (attempt + 1)  # 2s, 4s, 8s
                        logger.warning(
                            f"Gemini API error (attempt {attempt + 1}/3): {err_str[:100]}. "
                            f"Retrying in {wait_time}s..."
                        )
                        import time as _time
                        _time.sleep(wait_time)
                        last_error = api_err
                        continue
                    else:
                        raise  # Non-transient error — raise immediately

            if response is None:
                logger.error(f"Gemini API failed after 3 retries: {last_error}")
                return ProviderResponse(
                    content=f"AI service temporarily unavailable. Please try again. ({last_error})",
                    finish_reason="error",
                )
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return ProviderResponse(content=f"AI error: {e}", finish_reason="error")

        # Parse response
        content = ""
        tool_calls = []

        if response.candidates:
            candidate = response.candidates[0]
            finish_reason = str(getattr(candidate, "finish_reason", ""))

            # CRITICAL: Handle MALFORMED_FUNCTION_CALL —
            # Gemini tried to call a tool but the call was malformed.
            # Use 3-layer retry strategy to maximize code execution success.
            if "MALFORMED_FUNCTION_CALL" in finish_reason:
                logger.warning("Gemini returned MALFORMED_FUNCTION_CALL — starting smart retry")
                candidate = self._retry_malformed(
                    client, types, gemini_contents,
                    gemini_tools, system_instruction, temperature
                )
                if candidate is None:
                    return ProviderResponse(
                        content="Sorry, AI could not respond. Please try again.",
                        finish_reason="error",
                    )

            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.text:
                        content += part.text
                    elif part.function_call:
                        fc = part.function_call
                        args = dict(fc.args) if fc.args else {}
                        tool_calls.append(ToolCall(
                            id=f"call_{uuid.uuid4().hex[:8]}",
                            name=fc.name,
                            arguments=args,
                        ))

        # Usage
        usage = {}
        if response.usage_metadata:
            um = response.usage_metadata
            prompt_tokens = getattr(um, "prompt_token_count", 0) or 0
            completion_tokens = getattr(um, "candidates_token_count", 0) or 0
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
            self._total_tokens += prompt_tokens + completion_tokens

        finish = "stop"
        if tool_calls:
            finish = "tool_calls"

        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish,
            usage=usage,
        )

    def _retry_malformed(self, client, types, gemini_contents,
                         gemini_tools, system_instruction, temperature):
        """
        3-layer retry for MALFORMED_FUNCTION_CALL.

        Layer 1: Retry with same tools (intermittent error)
        Layer 2: Retry with only run_instaharvest_v2_code tool (fewer tools = less confusion)
        Layer 3: Retry without tools (text-only fallback)

        Returns: candidate object or None if all retries fail.
        """
        # Build minimal tool set — only run_instaharvest_v2_code
        minimal_tool = None
        for tool_def in instaharvest_v2_TOOLS:
            if tool_def["name"] == "run_instaharvest_v2_code":
                minimal_tool = self._build_gemini_tools([tool_def])
                break

        retry_configs = [
            ("same tools", gemini_tools),
            ("minimal tool (run_instaharvest_v2_code only)", minimal_tool),
            ("no tools", None),
        ]

        for label, tools_config in retry_configs:
            try:
                logger.info(f"MALFORMED retry: {label}")
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    tools=tools_config,
                    system_instruction=system_instruction,
                )
                response = client.models.generate_content(
                    model=self.model,
                    contents=gemini_contents,
                    config=config,
                )
                if response.candidates:
                    candidate = response.candidates[0]
                    fr = str(getattr(candidate, "finish_reason", ""))
                    if "MALFORMED" not in fr:
                        logger.info(f"MALFORMED retry '{label}' succeeded: {fr}")
                        return candidate
                    logger.warning(f"Retry '{label}' still MALFORMED")
            except Exception as e:
                logger.error(f"Retry '{label}' failed: {e}")

        return None

    def _convert_messages(self, messages: List[Dict]) -> List:
        """Convert OpenAI-style messages to Gemini contents."""
        try:
            from google.genai import types
        except ImportError:
            return []

        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content_val = msg.get("content", "")

            if role == "system":
                continue  # Handled as system_instruction
            elif role == "assistant":
                if content_val:
                    contents.append(types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=content_val)]
                    ))
            elif role == "tool":
                # Tool result
                tool_name = msg.get("name", "run_instaharvest_v2_code")
                try:
                    result_data = json.loads(content_val) if isinstance(content_val, str) else content_val
                except (json.JSONDecodeError, TypeError):
                    result_data = {"output": str(content_val)}

                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(
                        name=tool_name,
                        response=result_data if isinstance(result_data, dict) else {"output": str(result_data)},
                    )]
                ))
            else:
                # User message
                if content_val:
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=str(content_val))]
                    ))

        return contents

    @staticmethod
    def _build_gemini_tools(tools: List[Dict]) -> List:
        """Convert generic tool schema to Gemini format."""
        try:
            from google.genai import types
        except ImportError:
            return []

        declarations = []
        for tool in tools:
            params = tool.get("parameters", {})
            declarations.append(types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=params if params else None,
            ))

        if declarations:
            return [types.Tool(function_declarations=declarations)]
        return []

    @property
    def provider_name(self) -> str:
        return f"Gemini ({self.model})"

"""
Agent Vision — Image Analysis (Multimodal)
============================================
Analyze Instagram images using AI vision capabilities.

Supported providers for vision:
    - OpenAI GPT-4.1 / GPT-4o (vision)
    - Google Gemini 3.x / 2.5 (vision)
    - Anthropic Claude 4.6 / 4 (vision)

Features:
    - Analyze Instagram posts/stories images
    - Describe image content
    - Extract text (OCR-like)
    - Detect objects, faces, brands
    - Compare images
"""

import base64
import logging
import os
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("instaapi.agent.vision")

# Providers that support vision
VISION_PROVIDERS = {"openai", "gemini", "claude"}

# Max image size (5MB)
MAX_IMAGE_SIZE = 5 * 1024 * 1024


class VisionAnalyzer:
    """
    Analyze images using AI vision.

    Usage:
        vision = VisionAnalyzer(provider)
        result = vision.analyze_image("photo.jpg", "Describe this image")
        result = vision.analyze_url("https://...", "What's in this photo?")
    """

    def __init__(self, provider):
        """
        Args:
            provider: BaseProvider instance (must support vision)
        """
        self._provider = provider
        self._provider_type = self._detect_provider_type()

    def analyze_image(
        self,
        image_path: str,
        prompt: str = "Describe this image in detail.",
        language: str = "en",
    ) -> str:
        """Analyze a local image file."""
        if not os.path.exists(image_path):
            return f"Error: image not found: {image_path}"

        file_size = os.path.getsize(image_path)
        if file_size > MAX_IMAGE_SIZE:
            return f"Error: image too large ({file_size / 1024 / 1024:.1f}MB). Max: 5MB"

        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = f.read()

        base64_image = base64.b64encode(image_data).decode("utf-8")
        mime_type = self._detect_mime(image_path)

        return self._analyze(base64_image, mime_type, prompt, language)

    def analyze_url(
        self,
        image_url: str,
        prompt: str = "Describe this image in detail.",
        language: str = "en",
    ) -> str:
        """Analyze an image from URL."""
        if self._provider_type == "openai":
            # OpenAI can handle URLs directly
            return self._analyze_openai_url(image_url, prompt)

        # For other providers, download first
        try:
            req = urllib.request.Request(image_url)
            req.add_header("User-Agent", "InstaAPI-Agent/1.0")
            with urllib.request.urlopen(req, timeout=15) as resp:
                image_data = resp.read()
                if len(image_data) > MAX_IMAGE_SIZE:
                    return "Error: image too large"
                base64_image = base64.b64encode(image_data).decode("utf-8")
                mime_type = resp.headers.get("Content-Type", "image/jpeg")
                return self._analyze(base64_image, mime_type, prompt, language)
        except Exception as e:
            return f"Error downloading image: {e}"

    def is_supported(self) -> bool:
        """Check if current provider supports vision."""
        return self._provider_type in VISION_PROVIDERS

    # ═══════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════

    def _detect_provider_type(self) -> str:
        """Detect provider type from provider instance."""
        name = type(self._provider).__name__.lower()
        if "openai" in name:
            return "openai"
        elif "gemini" in name:
            return "gemini"
        elif "claude" in name:
            return "claude"
        elif "compatible" in name:
            return "openai"  # OpenAI-compatible may support vision
        return "unknown"

    def _analyze(
        self,
        base64_image: str,
        mime_type: str,
        prompt: str,
        language: str,
    ) -> str:
        """Analyze image using the appropriate provider format."""
        if self._provider_type == "openai":
            return self._analyze_openai(base64_image, mime_type, prompt)
        elif self._provider_type == "gemini":
            return self._analyze_gemini(base64_image, mime_type, prompt)
        elif self._provider_type == "claude":
            return self._analyze_claude(base64_image, mime_type, prompt)
        else:
            return "Error: vision not supported by this provider"

    def _analyze_openai(self, base64_image: str, mime_type: str, prompt: str) -> str:
        """OpenAI vision format."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}",
                        },
                    },
                ],
            }
        ]
        try:
            response = self._provider.generate(messages=messages, tools=[])
            return response.content
        except Exception as e:
            return f"Vision error: {e}"

    def _analyze_openai_url(self, image_url: str, prompt: str) -> str:
        """OpenAI vision with URL."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]
        try:
            response = self._provider.generate(messages=messages, tools=[])
            return response.content
        except Exception as e:
            return f"Vision error: {e}"

    def _analyze_gemini(self, base64_image: str, mime_type: str, prompt: str) -> str:
        """Gemini vision using genai SDK."""
        try:
            from google.genai import types as genai_types

            client = self._provider._get_client()

            # Build multimodal content
            image_part = genai_types.Part.from_bytes(
                data=base64.b64decode(base64_image),
                mime_type=mime_type,
            )
            text_part = genai_types.Part.from_text(text=prompt)

            contents = [genai_types.Content(
                role="user",
                parts=[text_part, image_part],
            )]

            response = client.models.generate_content(
                model=self._provider.model,
                contents=contents,
            )

            if response.candidates and response.candidates[0].content:
                parts = response.candidates[0].content.parts
                return "".join(p.text for p in parts if p.text)
            return "No response from vision model"

        except ImportError:
            return "Error: google-genai not installed"
        except Exception as e:
            return f"Gemini vision error: {e}"

    def _analyze_claude(self, base64_image: str, mime_type: str, prompt: str) -> str:
        """Claude vision format."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": base64_image,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        try:
            response = self._provider.generate(messages=messages, tools=[])
            return response.content
        except Exception as e:
            return f"Claude vision error: {e}"

    @staticmethod
    def _detect_mime(path: str) -> str:
        """Detect MIME type from file extension."""
        ext = os.path.splitext(path)[1].lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        return mime_map.get(ext, "image/jpeg")

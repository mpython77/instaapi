"""
Utilities
=========
URL/shortcode conversion and helper functions.
Extract data from Instagram URLs.
"""

import re
from typing import Optional


# Shortcode alphabet (base64url)
SHORTCODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def shortcode_to_pk(shortcode: str) -> int:
    """
    Convert Instagram shortcode to media PK.

    Args:
        shortcode: URL shortcode (e.g. "DVDk2dSjcq_")

    Returns:
        int: Media PK

    Raises:
        ValueError: If shortcode contains invalid characters
    """
    pk = 0
    for char in shortcode:
        idx = SHORTCODE_ALPHABET.find(char)
        if idx == -1:
            raise ValueError(
                f"Invalid character '{char}' in shortcode '{shortcode}'. "
                f"Valid chars: A-Z, a-z, 0-9, -, _"
            )
        pk = pk * 64 + idx
    return pk


def pk_to_shortcode(pk: int) -> str:
    """
    Convert media PK to shortcode.

    Args:
        pk: Media PK (number)

    Returns:
        str: Shortcode
    """
    shortcode = ""
    while pk > 0:
        shortcode = SHORTCODE_ALPHABET[pk % 64] + shortcode
        pk //= 64
    return shortcode


def extract_shortcode(url: str) -> Optional[str]:
    """
    Extract shortcode from Instagram URL.

    Supports:
        - instagram.com/p/ABC123/
        - instagram.com/reel/ABC123/
        - instagram.com/tv/ABC123/
        - instagr.am/p/ABC123/

    Args:
        url: Instagram URL

    Returns:
        str: Shortcode or None
    """
    patterns = [
        r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)",
        r"instagr\.am/p/([A-Za-z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def url_to_media_pk(url: str) -> Optional[int]:
    """
    Convert Instagram URL to media PK.

    Args:
        url: Instagram post URL

    Returns:
        int: Media PK or None
    """
    shortcode = extract_shortcode(url)
    if shortcode:
        return shortcode_to_pk(shortcode)
    return None


def media_pk_to_url(media_pk: int) -> str:
    """
    Convert media PK to Instagram URL.

    Args:
        media_pk: Media PK

    Returns:
        str: Instagram URL
    """
    shortcode = pk_to_shortcode(media_pk)
    return f"https://www.instagram.com/p/{shortcode}/"


def extract_username(url: str) -> Optional[str]:
    """
    Extract username from Instagram profile URL.

    Args:
        url: URL in instagram.com/username/ format

    Returns:
        str: Username or None
    """
    match = re.search(r"instagram\.com/([A-Za-z0-9_.]+)/?", url)
    if match:
        username = match.group(1)
        # Filter out built-in pages
        reserved = {
            "p", "reel", "tv", "stories", "explore", "direct",
            "accounts", "about", "legal", "developer", "nametag",
            "hashtag", "challenge",
        }
        if username.lower() not in reserved:
            return username
    return None


def extract_story_pk(url: str) -> Optional[str]:
    """
    Extract story PK from story URL.

    Args:
        url: URL in instagram.com/stories/username/12345/ format

    Returns:
        str: Story PK or None
    """
    match = re.search(r"instagram\.com/stories/[^/]+/(\d+)", url)
    if match:
        return match.group(1)
    return None


def media_id_to_pk(media_id: str) -> int:
    """
    Convert media ID (pk_user_pk format) to PK.

    Args:
        media_id: ID in "1234567890_1234567" format

    Returns:
        int: Media PK
    """
    return int(str(media_id).split("_")[0])


def format_count(count: int) -> str:
    """
    Format number in compact form.

    Args:
        count: Number

    Returns:
        str: "1.2K", "3.5M", "1.2B", etc.
    """
    if count >= 1_000_000_000:
        return f"{count/1_000_000_000:.1f}B"
    elif count >= 1_000_000:
        return f"{count/1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count/1_000:.1f}K"
    return str(count)

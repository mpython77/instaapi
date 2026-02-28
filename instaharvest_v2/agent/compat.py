"""
Cross-Platform Compatibility Layer
====================================
Ensures InstaHarvest v2 Agent works smoothly on Windows, Linux, and macOS.

Handles:
    - Path separators and temp directories
    - Console encoding (emoji/unicode)
    - File operations (atomic writes, line endings)
    - Process management (signals, threading)
    - Terminal capabilities (colors, width)
"""

import io
import locale
import logging
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger("instaharvest_v2.agent.compat")

# ═══════════════════════════════════════════════════════════
# PLATFORM DETECTION
# ═══════════════════════════════════════════════════════════

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"
PLATFORM_NAME = platform.system()  # "Windows", "Linux", "Darwin"
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_platform_info() -> dict:
    """Get detailed platform information."""
    return {
        "os": PLATFORM_NAME,
        "os_version": platform.version(),
        "python": PYTHON_VERSION,
        "arch": platform.machine(),
        "is_windows": IS_WINDOWS,
        "is_linux": IS_LINUX,
        "is_macos": IS_MACOS,
        "encoding": get_console_encoding(),
        "supports_unicode": supports_unicode(),
    }


# ═══════════════════════════════════════════════════════════
# PATH HANDLING
# ═══════════════════════════════════════════════════════════

def get_data_dir(app_name: str = "instaharvest_v2") -> Path:
    """
    Get platform-appropriate data directory.

    Windows: %APPDATA%/instaharvest_v2
    macOS:   ~/Library/Application Support/instaharvest_v2
    Linux:   ~/.local/share/instaharvest_v2
    """
    if IS_WINDOWS:
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif IS_MACOS:
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))

    path = Path(base) / app_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_temp_dir() -> Path:
    """Get platform-appropriate temp directory."""
    return Path(tempfile.gettempdir())


def get_config_dir(app_name: str = "instaharvest_v2") -> Path:
    """
    Get platform-appropriate config directory.

    Windows: %APPDATA%/instaharvest_v2
    macOS:   ~/Library/Preferences/instaharvest_v2
    Linux:   ~/.config/instaharvest_v2
    """
    if IS_WINDOWS:
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif IS_MACOS:
        base = os.path.expanduser("~/Library/Preferences")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))

    path = Path(base) / app_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_path(path: str) -> str:
    """Normalize path for current OS."""
    return str(Path(path))


def ensure_dir(path: str) -> Path:
    """Create directory if it doesn't exist, return Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ═══════════════════════════════════════════════════════════
# CONSOLE / ENCODING
# ═══════════════════════════════════════════════════════════

def get_console_encoding() -> str:
    """Get current console encoding."""
    return sys.stdout.encoding or locale.getpreferredencoding() or "utf-8"


def supports_unicode() -> bool:
    """Check if console supports unicode/emoji output."""
    encoding = get_console_encoding().lower()
    if encoding in ("utf-8", "utf8", "utf_8"):
        return True

    # Windows Terminal and modern terminals support unicode
    if IS_WINDOWS:
        # Check if running in Windows Terminal or modern console
        if os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM"):
            return True
        # Check for ConEmu, cmder, etc.
        if os.environ.get("ConEmuPID"):
            return True
    return False


def safe_print(text: str, fallback: str = "", end: str = "\n", flush: bool = True):
    """
    Print text safely, handling encoding errors.
    Falls back to ASCII if unicode not supported.
    """
    try:
        print(text, end=end, flush=flush)
    except UnicodeEncodeError:
        # Remove emoji/special chars for legacy terminals
        ascii_text = text.encode("ascii", errors="replace").decode("ascii")
        print(fallback or ascii_text, end=end, flush=flush)


def emoji(icon: str, fallback: str = "*") -> str:
    """Return emoji if supported, ASCII fallback otherwise."""
    if supports_unicode():
        return icon
    return fallback


def setup_console_encoding():
    """
    Configure console for UTF-8 output.
    Call this at startup for best compatibility.
    """
    if IS_WINDOWS:
        try:
            # Try to set UTF-8 mode on Windows
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

        # Set console code page to UTF-8
        try:
            os.system("chcp 65001 >nul 2>&1")
        except Exception:
            pass
    else:
        # Linux/macOS — ensure UTF-8
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════
# FILE OPERATIONS
# ═══════════════════════════════════════════════════════════

def safe_open(filepath: str, mode: str = "r", **kwargs):
    """
    Open file with safe defaults for cross-platform use.
    Always uses UTF-8 encoding and handles errors gracefully.
    """
    if "b" not in mode:
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    if "w" in mode:
        kwargs.setdefault("newline", "")  # Prevent double \r\n on Windows
    return open(filepath, mode, **kwargs)


def atomic_write(filepath: str, content: str, encoding: str = "utf-8"):
    """
    Write file atomically (write to temp, then rename).
    Prevents data corruption if process is interrupted.
    """
    dir_path = os.path.dirname(filepath) or "."
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
                f.write(content)
            # On Windows, need to remove target first
            if IS_WINDOWS and os.path.exists(filepath):
                os.replace(tmp_path, filepath)
            else:
                os.rename(tmp_path, filepath)
        except Exception:
            # Cleanup temp file on error
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError:
        # Fallback to direct write
        with open(filepath, "w", encoding=encoding, newline="") as f:
            f.write(content)


def get_file_size_str(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


# ═══════════════════════════════════════════════════════════
# PROCESS / THREADING
# ═══════════════════════════════════════════════════════════

def get_thread_timeout_method():
    """
    Get the best timeout method for current platform.
    Returns 'threading' (all platforms).
    Note: signal.alarm is NOT available on Windows.
    """
    return "threading"


def safe_thread_name(prefix: str = "agent") -> str:
    """Generate a safe thread name."""
    import threading
    return f"{prefix}-{threading.current_thread().ident}"


# ═══════════════════════════════════════════════════════════
# TERMINAL
# ═══════════════════════════════════════════════════════════

def get_terminal_width(default: int = 80) -> int:
    """Get terminal width, cross-platform."""
    try:
        return os.get_terminal_size().columns
    except (OSError, ValueError):
        return default


def clear_screen():
    """Clear terminal screen, cross-platform."""
    if IS_WINDOWS:
        os.system("cls")
    else:
        os.system("clear")


def supports_color() -> bool:
    """Check if terminal supports ANSI colors."""
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False

    if IS_WINDOWS:
        # Windows 10+ supports ANSI escape codes
        return os.environ.get("WT_SESSION") is not None or \
               os.environ.get("TERM_PROGRAM") is not None or \
               os.environ.get("ANSICON") is not None
    return True


# ═══════════════════════════════════════════════════════════
# ENVIRONMENT
# ═══════════════════════════════════════════════════════════

def find_env_file(search_dirs: Optional[list] = None) -> Optional[str]:
    """Find .env file in common locations."""
    if search_dirs is None:
        search_dirs = [
            os.getcwd(),
            str(Path.home()),
            str(get_config_dir()),
        ]

    for directory in search_dirs:
        env_path = os.path.join(directory, ".env")
        if os.path.isfile(env_path):
            return env_path
    return None


def get_default_memory_dir() -> str:
    """Get default memory storage directory."""
    return str(get_data_dir() / "memory")


def get_default_schedule_path() -> str:
    """Get default schedule file path."""
    return str(get_data_dir() / "schedule.json")


def get_default_cost_path() -> str:
    """Get default cost tracking file path."""
    return str(get_data_dir() / "costs.json")

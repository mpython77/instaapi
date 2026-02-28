"""
Agent Auth — Smart Authentication Manager
==========================================
Simple authentication for InstaAgent CLI.

Features:
    - API key entry with secure local storage
    - .env file auto-detection
    - Credential caching
    - Ollama (local AI) support
    - /login and /logout support

Storage:
    Windows: %APPDATA%/instaharvest_v2/auth.json
    macOS:   ~/Library/Application Support/instaharvest_v2/auth.json
    Linux:   ~/.config/instaharvest_v2/auth.json
"""

import json
import logging
import os
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("instaharvest_v2.agent.auth")


# ═══════════════════════════════════════════════════════════
# CREDENTIAL STORAGE PATHS
# ═══════════════════════════════════════════════════════════

def _get_auth_dir() -> Path:
    """Get platform-specific auth storage directory."""
    import sys
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))

    path = Path(base) / "instaharvest_v2"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_auth_file() -> Path:
    """Get the auth credential file path."""
    return _get_auth_dir() / "auth.json"


# ═══════════════════════════════════════════════════════════
# AUTH MANAGER
# ═══════════════════════════════════════════════════════════

class AuthManager:
    """
    Smart authentication manager for InstaAgent CLI.

    Usage:
        auth = AuthManager(console=tui_console)
        credentials = auth.authenticate()
        # credentials = {"provider": "gemini", "api_key": "...", ...}

        # Explicit login/logout
        auth.login()
        auth.logout()
    """

    # Supported provider display names
    PROVIDERS = {
        "gemini": "Google Gemini (default, recommended)",
        "openai": "OpenAI (GPT-4.1, o3, o4-mini)",
        "claude": "Anthropic Claude (Opus, Sonnet)",
        "deepseek": "DeepSeek (V3, Reasoner)",
        "groq": "Groq (fast, free tier)",
        "openrouter": "OpenRouter (all models in one)",
        "ollama": "Ollama (local, free, no key needed)",
        "lmstudio": "LM Studio (local, free, no key needed)",
    }

    # Provider → env key name mapping
    PROVIDER_ENV_KEYS = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "groq": "GROQ_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "ollama": None,
        "lmstudio": None,
    }

    # Provider → key URL for getting API keys
    PROVIDER_KEY_URLS = {
        "gemini": "https://aistudio.google.com/apikey",
        "openai": "https://platform.openai.com/api-keys",
        "claude": "https://console.anthropic.com/settings/keys",
        "deepseek": "https://platform.deepseek.com/api_keys",
        "groq": "https://console.groq.com/keys",
        "openrouter": "https://openrouter.ai/keys",
    }

    def __init__(self, console=None, env_path: str = ".env"):
        """
        Args:
            console: TUI console instance (AgentConsole or FallbackConsole)
            env_path: Path to .env file for fallback
        """
        self._console = console
        self._env_path = env_path
        self._auth_file = _get_auth_file()

    # ─── Main Auth Flow ─────────────────────────────────

    def authenticate(
        self,
        provider_override: Optional[str] = None,
        api_key_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main authentication flow.

        Priority:
            1. CLI arguments (--provider, --api-key)
            2. Cached credentials (auth.json)
            3. Environment variables / .env file
            4. Interactive prompt (first-run experience)

        Returns:
            dict with keys: provider, api_key, method, auth_type, model (optional)
        """

        # 1. CLI argument overrides — highest priority
        if api_key_override:
            provider = provider_override or "gemini"
            creds = {
                "provider": provider,
                "api_key": api_key_override,
                "auth_type": "api_key",
                "method": "cli_argument",
            }
            self._log_auth(creds)
            return creds

        # 2. Cached credentials
        cached = self._load_credentials()
        if cached:
            # If provider override specified, check if cached matches
            if provider_override and cached.get("provider") != provider_override:
                pass  # Don't use cache if provider doesn't match
            else:
                cached["method"] = "cached"
                self._update_last_used()
                self._log_auth(cached)
                return cached

        # 3. Environment variables / .env
        env_creds = self._try_env_auth(provider_override)
        if env_creds:
            self._log_auth(env_creds)
            return env_creds

        # 4. Interactive auth (first-run)
        return self._interactive_auth(provider_override)

    # ─── Cached Credentials ─────────────────────────────

    def _load_credentials(self) -> Optional[Dict[str, Any]]:
        """Load cached credentials from auth.json."""
        if not self._auth_file.exists():
            return None

        try:
            data = json.loads(self._auth_file.read_text(encoding="utf-8"))
            if data.get("api_key") and data.get("provider"):
                logger.info(f"Loaded cached auth: {data['provider']}")
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load auth cache: {e}")

        return None

    def _save_credentials(self, credentials: Dict[str, Any]):
        """Save credentials to auth.json."""
        credentials["created_at"] = credentials.get("created_at", datetime.now().isoformat())
        credentials["last_used"] = datetime.now().isoformat()

        try:
            self._auth_file.parent.mkdir(parents=True, exist_ok=True)
            self._auth_file.write_text(
                json.dumps(credentials, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Set restrictive permissions on Unix
            if os.name != "nt":
                os.chmod(self._auth_file, 0o600)

            logger.info(f"Saved auth to: {self._auth_file}")
        except IOError as e:
            logger.warning(f"Failed to save auth: {e}")

    def _update_last_used(self):
        """Update last_used timestamp in auth.json."""
        try:
            if self._auth_file.exists():
                data = json.loads(self._auth_file.read_text(encoding="utf-8"))
                data["last_used"] = datetime.now().isoformat()
                self._auth_file.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        except Exception:
            pass

    # ─── Environment Auth ───────────────────────────────

    def _try_env_auth(self, provider_override: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Try to authenticate from environment variables or .env file."""
        # Load .env
        try:
            from dotenv import load_dotenv
            load_dotenv(self._env_path)
        except ImportError:
            pass

        # If provider specified, try that provider's key
        if provider_override:
            key_name = self.PROVIDER_ENV_KEYS.get(provider_override)
            if provider_override in ("ollama", "lmstudio"):
                return {"provider": provider_override, "api_key": provider_override, "auth_type": "local", "method": "env"}
            if key_name:
                val = os.environ.get(key_name)
                if val:
                    return {"provider": provider_override, "api_key": val, "auth_type": "api_key", "method": "env"}
            return None

        # Try all providers in priority order
        priority = ["gemini", "openai", "claude", "deepseek", "groq", "openrouter"]
        for provider in priority:
            key_name = self.PROVIDER_ENV_KEYS.get(provider)
            if key_name:
                val = os.environ.get(key_name)
                if val:
                    return {"provider": provider, "api_key": val, "auth_type": "api_key", "method": "env"}

        return None

    # ─── Interactive Auth ───────────────────────────────

    def _interactive_auth(self, provider_override: Optional[str] = None) -> Dict[str, Any]:
        """Interactive first-run authentication dialog."""
        c = self._console

        if c and hasattr(c, 'console'):
            return self._rich_interactive_auth(provider_override)
        else:
            return self._plain_interactive_auth(provider_override)

    def _rich_interactive_auth(self, provider_override: Optional[str] = None) -> Dict[str, Any]:
        """Rich TUI interactive auth dialog."""
        try:
            from rich.panel import Panel
            from rich.text import Text
            from rich.prompt import IntPrompt
            from rich.box import ROUNDED
        except ImportError:
            return self._plain_interactive_auth(provider_override)

        c = self._console
        console = c.console

        # Build auth options
        options = (
            "\n"
            "  [bold]Welcome! Choose how to connect:[/]\n\n"
            "  [bold cyan][1][/] 🔑 Enter API Key [dim](Gemini, OpenAI, Claude, ...)[/]\n"
            "  [bold cyan][2][/] 🖥️  Ollama [dim](local, completely free)[/]\n"
            "  [bold cyan][3][/] 🧪 LM Studio [dim](local, completely free)[/]\n"
        )

        auth_text = Text.from_markup(options)

        panel = Panel(
            auth_text,
            title="[bold cyan]✻ InstaHarvest v2 Agent — Authentication[/]",
            title_align="left",
            border_style="cyan",
            box=ROUNDED,
            padding=(0, 1),
        )

        console.print()
        console.print(panel)

        # Get choice
        try:
            choice = IntPrompt.ask(
                "\n  [bold cyan]Your choice[/]",
                choices=["1", "2", "3"],
                default=1,
                console=console,
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [dim]Authentication cancelled.[/]")
            import sys
            sys.exit(0)

        # ── Option 1: Enter API Key ──
        if choice == 1:
            return self._auth_enter_key(console, provider_override)

        # ── Option 2: Ollama (local) ──
        elif choice == 2:
            return self._auth_local(console, "ollama")

        # ── Option 3: LM Studio (local) ──
        elif choice == 3:
            return self._auth_local(console, "lmstudio")

        return self._auth_enter_key(console, provider_override)

    def _auth_enter_key(self, console, provider_override: Optional[str] = None) -> Dict[str, Any]:
        """Flow: User enters their API key manually."""
        from rich.prompt import Prompt
        from rich.table import Table
        from rich.box import ROUNDED
        from rich.padding import Padding

        # Choose provider
        if not provider_override:
            console.print()
            table = Table(
                title="Choose Provider to Get API Key",
                box=ROUNDED,
                border_style="cyan",
                show_header=False,
                padding=(0, 1),
            )
            table.add_column("#", style="bold cyan", width=3)
            table.add_column("Provider", style="bold")
            table.add_column("URL", style="dim")

            provider_list = [
                (k, v) for k, v in self.PROVIDERS.items() if k != "ollama"
            ]
            for i, (key, _) in enumerate(provider_list, 1):
                url = self.PROVIDER_KEY_URLS.get(key, "")
                table.add_row(str(i), key, url)

            console.print(Padding(table, (0, 2)))

            try:
                choice = Prompt.ask(
                    "\n  [bold cyan]Provider number[/]",
                    default="1",
                    console=console,
                )
            except (KeyboardInterrupt, EOFError):
                import sys
                sys.exit(0)

            # Parse choice
            try:
                idx = int(choice) - 1
                provider = provider_list[idx][0]
            except (ValueError, IndexError):
                provider = choice.lower().strip()
                if provider not in self.PROVIDERS:
                    provider = "gemini"  # Default
        else:
            provider = provider_override

        # Ollama doesn't need a key
        if provider == "ollama" or provider == "lmstudio":
            return self._auth_local(console, provider)

        # Ask for API key
        key_name = self.PROVIDER_ENV_KEYS.get(provider, "API_KEY")
        url = self.PROVIDER_KEY_URLS.get(provider, "")

        console.print(f"\n  [dim]Enter your {provider} API key[/]")
        if url:
            console.print(f"  [dim]Get one at: [link={url}]{url}[/link][/]")

        try:
            api_key = Prompt.ask(
                f"\n  [bold cyan]{key_name}[/]",
                console=console,
            )
        except (KeyboardInterrupt, EOFError):
            import sys
            sys.exit(0)

        api_key = api_key.strip()
        if not api_key:
            console.print("  [red]No key provided. Exiting.[/]")
            import sys
            sys.exit(1)

        # Save credentials
        creds = {
            "provider": provider,
            "api_key": api_key,
            "auth_type": "api_key",
            "method": "api_key",
        }
        self._save_credentials(creds)

        # Also set as environment variable for this session
        if key_name:
            os.environ[key_name] = api_key

        console.print(f"\n  [green]✓ Authenticated with {provider}![/]")
        console.print(f"  [dim]Credentials saved to: {self._auth_file}[/]")
        console.print(f"  [dim]You won't need to enter this again.[/]\n")

        return creds

    def _auth_local(self, console, provider: str = "ollama") -> Dict[str, Any]:
        """Flow: Setup local AI (Ollama or LM Studio)."""
        from rich.prompt import Prompt

        if provider == "lmstudio":
            console.print(f"\n  [bold green]🧪 LM Studio — Local AI (Free)[/]")
            console.print(f"  [dim]Make sure LM Studio is running with local server enabled[/]")
            default_model = "auto"
        else:
            console.print(f"\n  [bold green]🖥️  Ollama — Local AI (Free)[/]")
            console.print(f"  [dim]Make sure Ollama is running: ollama serve[/]")
            default_model = "llama3.2"

        model = Prompt.ask(
            "  [bold cyan]Model name[/]",
            default=default_model,
            console=console,
        )

        creds = {
            "provider": provider,
            "api_key": provider,
            "auth_type": "local",
            "method": provider,
            "model": model.strip(),
        }
        self._save_credentials(creds)

        console.print(f"\n  [green]✓ Configured {provider} with model: {model}[/]")
        console.print(f"  [dim]Saved to: {self._auth_file}[/]\n")

        return creds

    def _plain_interactive_auth(self, provider_override: Optional[str] = None) -> Dict[str, Any]:
        """Fallback plain-text auth dialog (no Rich)."""

        print("\n" + "=" * 50)
        print("  InstaHarvest v2 Agent — Authentication")
        print("=" * 50)
        print()
        print("  [1] Enter API Key")
        print("  [2] Ollama (local, free)")
        print("  [3] LM Studio (local, free)")
        print()

        try:
            choice = input("  Choice [1]: ").strip() or "1"
        except (KeyboardInterrupt, EOFError):
            import sys
            sys.exit(0)

        if choice == "2" or choice == "3":
            provider = "ollama" if choice == "2" else "lmstudio"
            default = "llama3.2" if provider == "ollama" else "auto"
            model = input(f"  Model [{default}]: ").strip() or default
            creds = {"provider": provider, "api_key": provider, "auth_type": "local", "method": provider, "model": model}
            self._save_credentials(creds)
            print(f"  OK: {provider} configured with {model}")
            return creds

        # API key entry
        provider = provider_override or "gemini"
        print(f"\n  Provider: {provider}")
        url = self.PROVIDER_KEY_URLS.get(provider, "")
        if url:
            print(f"  Get API key at: {url}")

        try:
            api_key = input(f"  API Key: ").strip()
        except (KeyboardInterrupt, EOFError):
            import sys
            sys.exit(0)

        if not api_key:
            print("  No key provided.")
            import sys
            sys.exit(1)

        creds = {"provider": provider, "api_key": api_key, "auth_type": "api_key", "method": "api_key"}
        self._save_credentials(creds)

        key_name = self.PROVIDER_ENV_KEYS.get(provider)
        if key_name:
            os.environ[key_name] = api_key

        print(f"  OK: Authenticated with {provider}!")
        print(f"  Saved to: {self._auth_file}\n")
        return creds

    # ─── Login / Logout ─────────────────────────────────

    def login(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Explicit login (re-authenticate)."""
        # Clear existing
        self.logout(quiet=True)
        # Run interactive auth
        return self._interactive_auth(provider)

    def logout(self, quiet: bool = False):
        """Clear saved credentials."""
        if self._auth_file.exists():
            try:
                self._auth_file.unlink()
                if not quiet:
                    if self._console:
                        self._console.success(f"Logged out. Credentials removed from {self._auth_file}")
                    else:
                        print(f"  Logged out. Credentials removed from {self._auth_file}")
            except IOError as e:
                logger.warning(f"Failed to remove auth file: {e}")
        else:
            if not quiet:
                if self._console:
                    self._console.info("No saved credentials found.")
                else:
                    print("  No saved credentials found.")

    # ─── Utilities ──────────────────────────────────────

    def _log_auth(self, creds: Dict[str, Any]):
        """Log authentication details."""
        provider = creds.get("provider", "?")
        method = creds.get("method", "?")
        key_preview = creds.get("api_key", "")[:8] + "..." if creds.get("api_key") else "none"
        logger.info(f"Auth: {provider} via {method} (key: {key_preview})")

    @property
    def is_authenticated(self) -> bool:
        """Check if cached credentials exist."""
        return self._auth_file.exists()

    @property
    def cached_provider(self) -> Optional[str]:
        """Get cached provider name."""
        creds = self._load_credentials()
        return creds.get("provider") if creds else None

    @property
    def auth_type(self) -> Optional[str]:
        """Get cached auth type (api_key, local)."""
        creds = self._load_credentials()
        return creds.get("auth_type") if creds else None

    @property
    def auth_file_path(self) -> str:
        """Get auth file path as string."""
        return str(self._auth_file)

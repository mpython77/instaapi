"""
Agent CLI — Modern Terminal Interface
======================================
Claude Code-style interactive CLI for InstaAgent.

Usage:
    # One-shot question
    python -m instaharvest_v2.agent.cli "Get Cristiano's follower count"

    # Interactive chat
    python -m instaharvest_v2.agent.cli --interactive

    # With specific provider
    python -m instaharvest_v2.agent.cli --provider gemini "question here"

    # Full access (no permission prompts)
    python -m instaharvest_v2.agent.cli --full-access "do something"

    # Compact mode (less verbose output)
    python -m instaharvest_v2.agent.cli --compact "question"
"""

import argparse
import os
import sys
import time
from typing import Any, Dict, Optional


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="instaharvest_v2-agent",
        description="✻ InstaHarvest v2 Agent — Control Instagram with natural language",
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=None,
        help="Question or command (e.g.: 'Get Cristiano follower count')",
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Interactive chat mode",
    )
    parser.add_argument(
        "--provider",
        default="gemini",
        help=(
            "AI provider: openai, gemini, claude, deepseek, qwen, groq, "
            "together, mistral, ollama, openrouter, fireworks, perplexity, xai "
            "(default: gemini)"
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        help="AI model override (e.g.: gpt-4.1-mini, gemini-2.5-pro, o3)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="AI API key (or set GEMINI_API_KEY/OPENAI_API_KEY in .env)",
    )
    parser.add_argument(
        "--env",
        default=".env",
        help="Path to Instagram .env file (default: .env)",
    )
    parser.add_argument(
        "--permission",
        choices=["ask_every", "ask_once", "full_access"],
        default="full_access",
        help="Permission level (default: full_access)",
    )
    parser.add_argument(
        "--full-access",
        action="store_true",
        help="Full access (skip all permission checks)",
    )
    parser.add_argument(
        "--parallel",
        nargs="+",
        metavar="TASK",
        help="Run multiple tasks in parallel",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=25,
        help="Maximum agent steps (default: 25)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Code execution timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Show only result (hide progress)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact output mode (less visual detail)",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Skip welcome banner",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Re-authenticate (login again)",
    )
    parser.add_argument(
        "--logout",
        action="store_true",
        help="Clear saved credentials and exit",
    )
    return parser


# ═══════════════════════════════════════════════════════════
# STEP CALLBACK — Bridges agent loop events to TUI
# ═══════════════════════════════════════════════════════════

class RichStepCallback:
    """
    Receives step events from InstaAgent._agent_loop and renders
    them through the TUI console.
    """

    def __init__(self, console):
        self.console = console
        self._thinking = False

    def __call__(self, event: Dict[str, Any]):
        event_type = event.get("type", "")

        if event_type == "status":
            pass  # Handled by console.start_thinking

        elif event_type == "thinking":
            step = event.get("step", 0)
            msg = event.get("message", "Analyzing...")
            if not self._thinking:
                self.console.start_thinking()
                self._thinking = True
            self.console.update_thinking(f"Step {step}: {msg}")

        elif event_type == "code":
            self.console.stop_thinking()
            self._thinking = False
            code = event.get("content", "")
            desc = event.get("description", "")
            if code:
                if desc:
                    self.console.info(f"  {desc}")
                self.console.show_code(code)

        elif event_type == "tool_call":
            self.console.stop_thinking()
            self._thinking = False
            name = event.get("name", "?")
            args = event.get("arguments", {})
            code = ""
            if name == "run_instaharvest_v2_code":
                code = args.get("code", "")
            self.console.tool_call(name, args=args, code=code)

        elif event_type == "tool_result":
            output = event.get("output", "")
            success = event.get("success", True)
            name = event.get("name", "")
            self.console.tool_result(output, success=success, name=name)

        elif event_type == "error":
            self.console.stop_thinking()
            self._thinking = False
            self.console.error(event.get("message", "Unknown error"))

    def finish(self):
        """Ensure thinking spinner is stopped."""
        self.console.stop_thinking()
        self._thinking = False


# ═══════════════════════════════════════════════════════════
# SLASH COMMAND HANDLER
# ═══════════════════════════════════════════════════════════

def handle_slash_command(
    command: str,
    agent,
    console,
    templates_runner=None,
    auth_manager=None,
) -> bool:
    """
    Handle slash commands from the interactive loop.

    Returns True if command was handled, False if not a slash command.
    """
    if not command.startswith("/"):
        return False

    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    # ── /help ──
    if cmd in ("/help", "/h", "/?"):
        console.show_help()
        return True

    # ── /exit, /quit ──
    if cmd in ("/exit", "/quit", "/q"):
        console.goodbye()
        sys.exit(0)

    # ── /reset ──
    if cmd in ("/reset", "/new"):
        agent.reset()
        console.reset_notification()
        return True

    # ── /clear ──
    if cmd == "/clear":
        os.system("cls" if sys.platform == "win32" else "clear")
        return True

    # ── /history ──
    if cmd == "/history":
        console.show_history(agent.history)
        return True

    # ── /compact ──
    if cmd == "/compact":
        console.toggle_compact()
        return True

    # ── /cost ──
    if cmd == "/cost":
        cost_tracker = agent.cost
        if cost_tracker:
            try:
                cost_data = {
                    "total_tokens": cost_tracker.total_tokens,
                    "total_cost": cost_tracker.total_cost,
                    "session_requests": cost_tracker.session_requests,
                }
            except Exception:
                cost_data = {"info": "Cost tracking not available"}
        else:
            cost_data = {"info": "Cost tracking disabled"}
        console.show_cost(cost_data)
        return True

    # ── /model ──
    if cmd == "/model":
        console.show_model_info(
            provider=agent.provider_name,
            model=getattr(agent, '_model_name', 'auto'),
            mode=agent.mode,
            permission=agent._permissions.level.value,
        )
        return True

    # ── /templates ──
    if cmd == "/templates":
        if templates_runner:
            templates_list = templates_runner.list()
            console.show_templates(templates_list)
        else:
            console.info("Templates not available.")
        return True

    # ── /template <name> ──
    if cmd == "/template":
        if not rest:
            console.warning("Usage: /template <name> [param=value ...]")
            return True

        if not templates_runner:
            console.error("Templates not available.")
            return True

        # Parse template name and kwargs
        tparts = rest.split()
        template_name = tparts[0]
        kwargs = {}
        for p in tparts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                kwargs[k] = v

        try:
            console.start_thinking()
            callback = RichStepCallback(console)
            result = templates_runner.run(template_name, **kwargs)
            callback.finish()

            if result.success:
                console.response(result.answer)
            else:
                console.error(result.error)
            console.step_footer(
                steps=result.steps,
                tokens=result.tokens_used,
                duration=result.duration,
            )
        except ValueError as e:
            console.error(str(e))
        return True

    # ── /login ──
    if cmd == "/login":
        if auth_manager:
            creds = auth_manager.login()
            console.success(f"Re-authenticated with {creds.get('provider', '?')}")
            console.info("Restart agent to use new credentials.")
        else:
            console.warning("Auth manager not available.")
        return True

    # ── /logout ──
    if cmd == "/logout":
        if auth_manager:
            auth_manager.logout()
        else:
            console.warning("Auth manager not available.")
        return True

    # Unknown slash command
    console.warning(f"Unknown command: {cmd}. Type /help for available commands.")
    return True


# ═══════════════════════════════════════════════════════════
# INTERACTIVE CHAT LOOP
# ═══════════════════════════════════════════════════════════

def interactive_chat(agent, console, templates_runner=None, auth_manager=None):
    """Run the interactive chat loop with Rich TUI."""

    # Welcome banner
    console.welcome(
        provider=agent.provider_name,
        model=getattr(agent, '_model_name', 'auto'),
        mode=agent.mode,
        permission=agent._permissions.level.value,
    )

    while True:
        # Get user input
        user_input = console.get_input()

        if not user_input:
            continue

        # Handle slash commands
        if user_input.startswith("/"):
            handle_slash_command(
                user_input, agent, console,
                templates_runner=templates_runner,
                auth_manager=auth_manager,
            )
            continue

        # Agent processing
        callback = RichStepCallback(console)
        console.start_thinking()

        try:
            result = agent.ask(user_input, step_callback=callback)
        except KeyboardInterrupt:
            console.stop_thinking()
            callback.finish()
            console.warning("Interrupted")
            continue
        except Exception as e:
            console.stop_thinking()
            callback.finish()
            console.error(f"Agent error: {e}")
            continue
        finally:
            # GUARANTEED spinner stop — never leave it spinning
            console.stop_thinking()

        callback.finish()
        console.stop_thinking()  # Triple safety

        # Display response
        if result.success:
            console.response(result.answer)
        else:
            console.error(result.error)

        # Footer with stats
        console.step_footer(
            steps=result.steps,
            tokens=result.tokens_used,
            duration=result.duration,
        )


# ═══════════════════════════════════════════════════════════
# ONE-SHOT MODE
# ═══════════════════════════════════════════════════════════

def one_shot(agent, console, question: str):
    """Run a single question and display the result."""

    callback = RichStepCallback(console)
    console.start_thinking()

    try:
        result = agent.ask(question, step_callback=callback)
    except KeyboardInterrupt:
        console.stop_thinking()
        callback.finish()
        console.error("Interrupted")
        sys.exit(130)
    except Exception as e:
        console.stop_thinking()
        callback.finish()
        console.error(f"Agent error: {e}")
        sys.exit(1)
    finally:
        # GUARANTEED spinner stop
        console.stop_thinking()

    callback.finish()
    console.stop_thinking()  # Triple safety

    if result.success:
        console.response(result.answer)
        console.step_footer(
            steps=result.steps,
            tokens=result.tokens_used,
            duration=result.duration,
        )
    else:
        console.error(result.error)
        sys.exit(1)


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    parser = create_parser()
    args = parser.parse_args()

    # Cross-platform console setup
    from .compat import setup_console_encoding
    setup_console_encoding()

    # Load env
    try:
        from dotenv import load_dotenv
        load_dotenv(args.env)
    except ImportError:
        pass

    # Create TUI console
    from .tui import create_console
    console = create_console(compact=args.compact, no_banner=args.no_banner)

    # ─── Smart Auth ─────────────────────────────────
    from .auth import AuthManager
    auth_manager = AuthManager(console=console, env_path=args.env)

    # Handle --logout
    if args.logout:
        auth_manager.logout()
        sys.exit(0)

    # Handle --login (force re-authenticate)
    if args.login:
        creds = auth_manager.login(provider=args.provider if args.provider != "gemini" else None)
    else:
        # Normal auth flow: cached → env → interactive
        creds = auth_manager.authenticate(
            provider_override=args.provider if args.api_key or args.provider != "gemini" else None,
            api_key_override=args.api_key,
        )

    # Use auth results
    provider = creds.get("provider", args.provider)
    api_key = creds.get("api_key", args.api_key)
    model = args.model or creds.get("model")

    # ─── Permission Level ───────────────────────────
    from ..agent.permissions import Permission

    if args.full_access:
        permission = Permission.FULL_ACCESS
    else:
        permission_map = {
            "ask_every": Permission.ASK_EVERY,
            "ask_once": Permission.ASK_ONCE,
            "full_access": Permission.FULL_ACCESS,
        }
        permission = permission_map.get(args.permission, Permission.ASK_ONCE)

    # ─── Instagram Client ───────────────────────────
    ig = None
    try:
        from ..instagram import Instagram
        ig = Instagram.from_env(args.env)
    except Exception as e:
        # Not fatal — agent can work in anonymous mode
        console.warning(f"Instagram client not available: {e}")
        console.info("Running in anonymous mode (public data only)")

    # ─── Create Agent ───────────────────────────────
    try:
        from ..agent.core import InstaAgent
        agent = InstaAgent(
            ig=ig,
            provider=provider,
            api_key=api_key,
            model=model,
            permission=permission,
            max_steps=args.max_steps,
            timeout=args.timeout,
            verbose=False,  # TUI handles output now
        )
    except ValueError as e:
        console.error(f"Failed to create agent: {e}")
        sys.exit(1)
    except ImportError as e:
        console.error(f"Required package not found: {e}")
        console.info("Install with: pip install instaharvest_v2[agent]")
        sys.exit(1)

    # Override permission prompt to use TUI
    agent._permissions._prompt = console.ask_permission

    # Create template runner
    templates_runner = None
    try:
        from ..agent.templates import TemplateRunner
        templates_runner = TemplateRunner(agent)
    except Exception:
        pass

    # ─── Run Mode ───────────────────────────────────

    # Parallel mode
    if args.parallel:
        from ..agent.coordinator import AgentCoordinator
        coord = AgentCoordinator(
            ig=ig,
            provider=provider,
            api_key=api_key,
            model=model,
            permission=permission,
            verbose=not args.quiet,
        )
        result = coord.run_parallel(args.parallel)
        if result.success:
            console.response(str(result))
        else:
            console.error(str(result))
        sys.exit(0 if result.success else 1)

    # Interactive mode
    if args.interactive or (not args.question):
        interactive_chat(agent, console, templates_runner=templates_runner, auth_manager=auth_manager)
        sys.exit(0)

    # One-shot mode
    one_shot(agent, console, args.question)


if __name__ == "__main__":
    main()

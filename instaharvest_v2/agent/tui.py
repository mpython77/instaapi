"""
Agent TUI — Rich Terminal User Interface
==========================================
Modern, Claude Code-style terminal interface for InstaAgent.

Components:
    - AgentConsole     — Main console wrapper with themed output
    - WelcomeBanner    — Animated welcome screen
    - CodePanel        — Syntax-highlighted Python code
    - ToolCallDisplay  — Spinner + tool execution status
    - PermissionPrompt — Rich permission dialogs
    - MarkdownResponse — Terminal markdown rendering
    - StatusFooter     — Token/cost/step summary line
"""

import os
import sys
import time
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.markdown import Markdown
    from rich.text import Text
    from rich.table import Table
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.prompt import Prompt, Confirm
    from rich.rule import Rule
    from rich.columns import Columns
    from rich.align import Align
    from rich.padding import Padding
    from rich.theme import Theme
    from rich.style import Style
    from rich.box import ROUNDED, HEAVY, DOUBLE, SIMPLE, MINIMAL, HORIZONTALS

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# ═══════════════════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════════════════

AGENT_THEME = Theme({
    "agent.brand":       "bold cyan",
    "agent.accent":      "bold magenta",
    "agent.success":     "bold green",
    "agent.error":       "bold red",
    "agent.warning":     "bold yellow",
    "agent.info":        "dim cyan",
    "agent.muted":       "dim white",
    "agent.step":        "bold blue",
    "agent.tool":        "bold yellow",
    "agent.code":        "green",
    "agent.user":        "bold white",
    "agent.thinking":    "dim italic cyan",
    "agent.result":      "green",
    "agent.permission":  "bold yellow",
    "agent.slash":       "bold magenta",
    "agent.cost":        "dim green",
})


# ═══════════════════════════════════════════════════════════
# AGENT CONSOLE — Main TUI Controller
# ═══════════════════════════════════════════════════════════

class AgentConsole:
    """
    Rich-based terminal interface for InstaAgent.

    Usage:
        console = AgentConsole()
        console.welcome(provider="gemini", model="gemini-2.5-pro")
        console.thinking()
        console.tool_call("run_instaharvest_v2_code", code="...")
        console.tool_result("Success", success=True)
        console.response("Here is the answer...")
        console.step_footer(steps=2, tokens=450, duration=1.8)
    """

    # ─── Symbols ─────────────────────────────────────
    SYM_PROMPT   = "❯"
    SYM_AGENT    = "✻"
    SYM_TOOL     = "⬡"
    SYM_SUCCESS  = "✓"
    SYM_ERROR    = "✗"
    SYM_WARNING  = "⚠"
    SYM_STEP     = "●"
    SYM_THINKING = "◐"
    SYM_ARROW    = "→"
    SYM_LOCK     = "⊘"
    SYM_KEY      = "⟡"

    def __init__(self, compact: bool = False, no_banner: bool = False):
        if not HAS_RICH:
            raise ImportError(
                "Rich is required for the modern CLI. "
                "Install with: pip install instaharvest_v2[agent]"
            )

        self.console = Console(theme=AGENT_THEME, highlight=False)
        self.compact = compact
        self.no_banner = no_banner
        self._live: Optional[Live] = None
        self._spinner_start: float = 0

    # ─── Welcome Banner ────────────────────────────────

    def welcome(
        self,
        provider: str = "gemini",
        model: str = "",
        mode: str = "login",
        permission: str = "ask_once",
        version: str = "3.0",
    ):
        """Display the welcome banner."""
        if self.no_banner:
            return

        # Build info grid
        info_parts = []
        info_parts.append(f"[agent.info]Provider:[/] [bold]{provider}[/]")
        if model:
            info_parts.append(f"[agent.info]Model:[/] [bold]{model}[/]")
        info_parts.append(f"[agent.info]Mode:[/] [bold]{mode}[/]")
        info_parts.append(f"[agent.info]Permission:[/] [bold]{permission}[/]")

        info_line = "  │  ".join(info_parts)

        # Banner
        banner_text = Text()
        banner_text.append("  ✻  ", style="bold cyan")
        banner_text.append("InstaHarvest v2 Agent", style="bold white")
        banner_text.append(f"  v{version}", style="dim")

        panel = Panel(
            Align.left(
                Text.from_markup(
                    f"{info_line}\n"
                    f"  [agent.muted]Type a message or use [/]"
                    f"[agent.slash]/help[/]"
                    f"[agent.muted] for commands[/]"
                )
            ),
            title=banner_text,
            title_align="left",
            border_style="cyan",
            box=ROUNDED,
            padding=(0, 1),
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    # ─── User Input Prompt ──────────────────────────────

    def get_input(self) -> str:
        """Display the input prompt and get user input."""
        try:
            text = self.console.input(
                Text.from_markup(f"[bold cyan]{self.SYM_PROMPT}[/] ")
            )
            return text.strip()
        except (KeyboardInterrupt, EOFError):
            return "/exit"

    # ─── Thinking Spinner ───────────────────────────────

    def start_thinking(self):
        """Start the thinking spinner."""
        self._spinner_start = time.time()
        spinner = Spinner("dots", text=Text.from_markup(
            "[agent.thinking]Thinking...[/]"
        ), style="cyan")
        self._live = Live(
            spinner,
            console=self.console,
            transient=True,
            refresh_per_second=12,
        )
        self._live.start()

    def stop_thinking(self):
        """Stop the thinking spinner."""
        if self._live:
            self._live.stop()
            self._live = None

    def update_thinking(self, text: str):
        """Update the thinking spinner text."""
        if self._live:
            spinner = Spinner("dots", text=Text.from_markup(
                f"[agent.thinking]{text}[/]"
            ), style="cyan")
            self._live.update(spinner)

    # ─── Step Indicator ─────────────────────────────────

    def step(self, number: int, total: int = 0):
        """Show step indicator."""
        if self.compact:
            return
        if total:
            self.console.print(
                f"  [agent.step]{self.SYM_STEP} Step {number}/{total}[/]"
            )
        else:
            self.console.print(
                f"  [agent.step]{self.SYM_STEP} Step {number}[/]"
            )

    # ─── Tool Call Display ──────────────────────────────

    def tool_call(self, name: str, args: Optional[Dict] = None, code: str = ""):
        """Display a tool call with optional code."""
        self.stop_thinking()

        # Tool header
        self.console.print(
            f"\n  [agent.tool]{self.SYM_TOOL} {name}[/]"
        )

        # Show code if it's a code execution tool
        if code:
            self.show_code(code)
        elif name == "run_instaharvest_v2_code" and args:
            code_content = args.get("code", "")
            if code_content:
                desc = args.get("description", "")
                if desc:
                    self.console.print(
                        f"    [dim]{desc}[/]"
                    )
                self.show_code(code_content)

    def tool_result(self, result: str, success: bool = True, name: str = ""):
        """Display tool result."""
        if success:
            # Truncate long results
            display = result
            if len(display) > 500 and self.compact:
                display = display[:500] + "\n... (truncated)"
            elif len(display) > 2000:
                display = display[:2000] + "\n... (truncated)"

            if display.strip():
                result_panel = Panel(
                    Text(display, overflow="fold"),
                    title=f"[agent.success]{self.SYM_SUCCESS} Result[/]",
                    title_align="left",
                    border_style="green",
                    box=ROUNDED,
                    padding=(0, 1),
                    width=min(100, self.console.width - 4),
                )
                self.console.print(Padding(result_panel, (0, 2)))
        else:
            error_panel = Panel(
                Text(result[:500], style="red", overflow="fold"),
                title=f"[agent.error]{self.SYM_ERROR} Error[/]",
                title_align="left",
                border_style="red",
                box=ROUNDED,
                padding=(0, 1),
                width=min(100, self.console.width - 4),
            )
            self.console.print(Padding(error_panel, (0, 2)))

    # ─── Code Display ───────────────────────────────────

    def show_code(self, code: str, language: str = "python"):
        """Display syntax-highlighted code."""
        # Clean up code
        code = code.strip()
        if not code:
            return

        syntax = Syntax(
            code,
            language,
            theme="monokai",
            line_numbers=len(code.splitlines()) > 3,
            word_wrap=True,
            padding=(0, 1),
        )

        code_panel = Panel(
            syntax,
            border_style="dim green",
            box=ROUNDED,
            padding=(0, 0),
            width=min(100, self.console.width - 4),
        )
        self.console.print(Padding(code_panel, (0, 2)))

    # ─── Agent Response ─────────────────────────────────

    def response(self, text: str):
        """Display agent response with markdown rendering."""
        self.stop_thinking()

        if not text or not text.strip():
            return

        self.console.print()

        # Try markdown rendering
        try:
            md = Markdown(text, code_theme="monokai")
            self.console.print(Padding(md, (0, 2)))
        except Exception:
            # Fallback to plain text
            self.console.print(Padding(Text(text), (0, 2)))

    # ─── Step Footer ────────────────────────────────────

    def step_footer(
        self,
        steps: int = 0,
        tokens: int = 0,
        duration: float = 0.0,
        cost: float = 0.0,
    ):
        """Display step/token/time summary footer."""
        parts = []
        if steps:
            parts.append(f"{steps} step{'s' if steps != 1 else ''}")
        if tokens:
            parts.append(f"{tokens:,} tokens")
        if duration:
            parts.append(f"{duration:.1f}s")
        if cost > 0:
            parts.append(f"${cost:.4f}")

        if parts:
            footer = " · ".join(parts)
            self.console.print(
                f"\n  [agent.muted]{'─' * 3} {footer} {'─' * 3}[/]\n"
            )

    # ─── Error Display ──────────────────────────────────

    def error(self, message: str):
        """Display an error message."""
        self.stop_thinking()
        self.console.print(
            f"\n  [agent.error]{self.SYM_ERROR} {message}[/]\n"
        )

    def warning(self, message: str):
        """Display a warning message."""
        self.console.print(
            f"  [agent.warning]{self.SYM_WARNING} {message}[/]"
        )

    def info(self, message: str):
        """Display an info message."""
        self.console.print(
            f"  [agent.info]{message}[/]"
        )

    def success(self, message: str):
        """Display a success message."""
        self.console.print(
            f"  [agent.success]{self.SYM_SUCCESS} {message}[/]"
        )

    # ─── Permission Prompt ──────────────────────────────

    def ask_permission(
        self,
        description: str,
        action_type: str = "read",
        code: str = "",
    ) -> bool:
        """Ask user for permission with rich formatting."""

        # Color by action type
        style_map = {
            "read":      ("green",  "📖"),
            "write":     ("yellow", "✏️"),
            "export":    ("yellow", "📤"),
            "code_exec": ("cyan",   "💻"),
            "delete":    ("red",    "🗑️"),
        }
        color, icon = style_map.get(action_type, ("yellow", "⚠️"))

        # Show code if code execution
        if code and action_type == "code_exec":
            self.show_code(code)

        # Permission panel
        perm_text = Text()
        perm_text.append(f" {icon} ", style="bold")
        perm_text.append(f"{description}", style=f"bold {color}")
        perm_text.append(f"\n    Action type: ", style="dim")
        perm_text.append(f"{action_type}", style=f"bold {color}")

        self.console.print(
            Panel(
                perm_text,
                title="[agent.permission]Permission Required[/]",
                title_align="left",
                border_style=color,
                box=ROUNDED,
                padding=(0, 1),
            )
        )

        try:
            result = Confirm.ask(
                f"  [bold {color}]Allow?[/]",
                console=self.console,
                default=True,
            )
            return result
        except (KeyboardInterrupt, EOFError):
            return False

    # ─── Ask User (Agent's question) ────────────────────

    def ask_user(self, question: str) -> str:
        """Agent asks the user a question."""
        self.console.print(
            Panel(
                Text(question, style="bold"),
                title=f"[agent.brand]{self.SYM_AGENT} Agent Question[/]",
                title_align="left",
                border_style="cyan",
                box=ROUNDED,
                padding=(0, 1),
            )
        )

        try:
            answer = Prompt.ask(
                "  [bold cyan]Your answer[/]",
                console=self.console,
            )
            return answer.strip() or "(no response)"
        except (KeyboardInterrupt, EOFError):
            return "(no response)"

    # ─── Slash Command Help ─────────────────────────────

    def show_help(self):
        """Display slash commands help."""
        table = Table(
            title="Commands",
            box=ROUNDED,
            border_style="cyan",
            title_style="bold cyan",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
        )
        table.add_column("Command", style="agent.slash", min_width=16)
        table.add_column("Description", style="white")

        commands = [
            ("/help",       "Show this help message"),
            ("/exit, /quit", "Exit agent"),
            ("/reset",      "Reset conversation (start fresh)"),
            ("/clear",      "Clear terminal screen"),
            ("/history",    "Show conversation history"),
            ("/compact",    "Toggle compact/expanded mode"),
            ("/cost",       "Show token & cost statistics"),
            ("/model",      "Show current model info"),
            ("/templates",  "List available task templates"),
            ("/template <n>", "Run a task template"),
            ("/login",      "Re-authenticate with new credentials"),
            ("/logout",     "Clear saved credentials"),
        ]

        for cmd, desc in commands:
            table.add_row(cmd, desc)

        self.console.print()
        self.console.print(Padding(table, (0, 2)))
        self.console.print()

    # ─── History Display ────────────────────────────────

    def show_history(self, history: List[Dict]):
        """Display conversation history."""
        if not history:
            self.info("No conversation history yet.")
            return

        table = Table(
            title="Conversation History",
            box=ROUNDED,
            border_style="dim",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Role", style="bold", width=8)
        table.add_column("Content", overflow="fold")

        for i, msg in enumerate(history, 1):
            role = msg.get("role", "?")
            content = str(msg.get("content", ""))[:120]

            role_display = {
                "user": "[bold white]You[/]",
                "assistant": "[bold cyan]Agent[/]",
                "tool": "[bold yellow]Tool[/]",
            }.get(role, role)

            table.add_row(str(i), role_display, content)

        self.console.print()
        self.console.print(Padding(table, (0, 2)))
        self.console.print()

    # ─── Templates List ─────────────────────────────────

    def show_templates(self, templates: List[Dict]):
        """Display available templates."""
        if not templates:
            self.info("No templates available.")
            return

        table = Table(
            title="Task Templates",
            box=ROUNDED,
            border_style="magenta",
            title_style="bold magenta",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
        )
        table.add_column("Name", style="agent.slash", min_width=18)
        table.add_column("Title", style="bold")
        table.add_column("Category", style="dim")
        table.add_column("Params", style="dim")

        for t in templates:
            params = ", ".join(t.get("required_params", []))
            table.add_row(
                t["name"],
                t.get("title", ""),
                t.get("category", ""),
                params or "—",
            )

        self.console.print()
        self.console.print(Padding(table, (0, 2)))
        self.console.print(
            "  [agent.muted]Usage: /template profile_analysis username=cristiano[/]"
        )
        self.console.print()

    # ─── Cost Display ───────────────────────────────────

    def show_cost(self, cost_data: Dict):
        """Display cost/token statistics."""
        table = Table(
            title="Token & Cost Statistics",
            box=ROUNDED,
            border_style="green",
            title_style="bold green",
            show_header=False,
            padding=(0, 1),
        )
        table.add_column("Metric", style="bold", min_width=20)
        table.add_column("Value", style="agent.cost")

        for key, value in cost_data.items():
            if isinstance(value, float):
                display = f"${value:.4f}" if "cost" in key.lower() else f"{value:.2f}"
            elif isinstance(value, int):
                display = f"{value:,}"
            else:
                display = str(value)
            table.add_row(key.replace("_", " ").title(), display)

        self.console.print()
        self.console.print(Padding(table, (0, 2)))
        self.console.print()

    # ─── Model Info ─────────────────────────────────────

    def show_model_info(
        self,
        provider: str,
        model: str,
        mode: str,
        permission: str,
    ):
        """Display current model/provider info."""
        table = Table(
            title="Agent Configuration",
            box=ROUNDED,
            border_style="cyan",
            title_style="bold cyan",
            show_header=False,
            padding=(0, 1),
        )
        table.add_column("Setting", style="bold", min_width=15)
        table.add_column("Value")

        table.add_row("Provider", f"[bold]{provider}[/]")
        table.add_row("Model", f"[bold]{model}[/]")
        table.add_row("Mode", f"[bold]{mode}[/]")
        table.add_row("Permission", f"[bold]{permission}[/]")

        self.console.print()
        self.console.print(Padding(table, (0, 2)))
        self.console.print()

    # ─── Goodbye ────────────────────────────────────────

    def goodbye(self):
        """Display goodbye message."""
        self.console.print(
            f"\n  [agent.brand]{self.SYM_AGENT} Goodbye![/]\n"
        )

    # ─── Compact Toggle ─────────────────────────────────

    def toggle_compact(self) -> bool:
        """Toggle compact mode and return new state."""
        self.compact = not self.compact
        state = "ON" if self.compact else "OFF"
        self.info(f"Compact mode: {state}")
        return self.compact

    # ─── Reset Notification ─────────────────────────────

    def reset_notification(self):
        """Show reset notification."""
        self.console.print(
            f"  [agent.brand]↺ Conversation reset[/]\n"
        )


# ═══════════════════════════════════════════════════════════
# FALLBACK CONSOLE (no Rich)
# ═══════════════════════════════════════════════════════════

class FallbackConsole:
    """Plain text fallback when Rich is not available."""

    def __init__(self, **kwargs):
        self.compact = kwargs.get("compact", False)

    def welcome(self, **kwargs):
        print("\n" + "=" * 50)
        print(f"  InstaHarvest v2 Agent v{kwargs.get('version', '3.0')}")
        print(f"  Provider: {kwargs.get('provider', '?')}")
        print(f"  /help for commands")
        print("=" * 50 + "\n")

    def get_input(self) -> str:
        try:
            return input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            return "/exit"

    def start_thinking(self):
        print("  Thinking...", end="", flush=True)

    def stop_thinking(self):
        print()

    def update_thinking(self, text: str):
        pass

    def step(self, number: int, total: int = 0):
        pass

    def tool_call(self, name: str, args=None, code: str = ""):
        print(f"  >> {name}")
        if code:
            print(f"  {code[:200]}")

    def tool_result(self, result: str, success: bool = True, name: str = ""):
        status = "OK" if success else "ERR"
        print(f"  [{status}] {result[:200]}")

    def show_code(self, code: str, language: str = "python"):
        print(f"  ```{language}")
        for line in code.splitlines()[:20]:
            print(f"  {line}")
        print("  ```")

    def response(self, text: str):
        print(f"\n  {text}\n")

    def step_footer(self, **kwargs):
        parts = []
        if kwargs.get("steps"):
            parts.append(f"{kwargs['steps']} steps")
        if kwargs.get("tokens"):
            parts.append(f"{kwargs['tokens']} tokens")
        if kwargs.get("duration"):
            parts.append(f"{kwargs['duration']:.1f}s")
        if parts:
            print(f"  --- {' | '.join(parts)} ---\n")

    def error(self, message: str):
        print(f"  ERROR: {message}")

    def warning(self, message: str):
        print(f"  WARN: {message}")

    def info(self, message: str):
        print(f"  {message}")

    def success(self, message: str):
        print(f"  OK: {message}")

    def ask_permission(self, description: str, action_type: str = "read", code: str = "") -> bool:
        print(f"\n  Permission: {description} [{action_type}]")
        try:
            ans = input("  Allow? [y/n]: ").strip().lower()
            return ans in ("y", "yes", "")
        except (KeyboardInterrupt, EOFError):
            return False

    def ask_user(self, question: str) -> str:
        try:
            return input(f"\n  Agent asks: {question}\n  Answer: ").strip() or "(no response)"
        except (KeyboardInterrupt, EOFError):
            return "(no response)"

    def show_help(self):
        print("\n  Commands:")
        for cmd, desc in [
            ("/help", "Show help"), ("/exit", "Exit"),
            ("/reset", "Reset"), ("/clear", "Clear screen"),
            ("/history", "History"), ("/compact", "Toggle compact"),
        ]:
            print(f"    {cmd:16s} {desc}")
        print()

    def show_history(self, history):
        for msg in history:
            role = msg.get("role", "?")
            content = str(msg.get("content", ""))[:100]
            print(f"  [{role}] {content}")

    def show_templates(self, templates):
        for t in templates:
            print(f"  {t['name']:20s} {t.get('title', '')}")

    def show_cost(self, cost_data):
        for k, v in cost_data.items():
            print(f"  {k}: {v}")

    def show_model_info(self, **kwargs):
        for k, v in kwargs.items():
            print(f"  {k}: {v}")

    def goodbye(self):
        print("\n  Goodbye!\n")

    def toggle_compact(self) -> bool:
        self.compact = not self.compact
        return self.compact

    def reset_notification(self):
        print("  Conversation reset.\n")


# ═══════════════════════════════════════════════════════════
# FACTORY
# ═══════════════════════════════════════════════════════════

def create_console(**kwargs) -> "AgentConsole | FallbackConsole":
    """Create the best available console."""
    if HAS_RICH:
        return AgentConsole(**kwargs)
    return FallbackConsole(**kwargs)

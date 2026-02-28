"""
Agent Web UI — FastAPI Chat Interface
======================================
Browser-based chat interface for InstaAgent.

Usage:
    python -m instaapi.agent.web
    # Opens http://localhost:8899

    python -m instaapi.agent.web --port 9000 --provider openai
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("instaapi.agent.web")

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    env_path: str = ".env",
    provider: str = "gemini",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    permission_level: str = "ask_once",
):
    """Create FastAPI application."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import HTMLResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError:
        raise ImportError(
            "FastAPI not found. Install with:\n"
            "  pip install fastapi uvicorn\n"
        )

    from ..instagram import Instagram
    from .core import InstaAgent
    from .coordinator import AgentCoordinator
    from .permissions import Permission

    # Load env
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        pass

    # Permission
    perm_map = {
        "ask_every": Permission.ASK_EVERY,
        "ask_once": Permission.ASK_ONCE,
        "full_access": Permission.FULL_ACCESS,
    }
    permission = perm_map.get(permission_level, Permission.ASK_ONCE)

    # For web, auto-approve (no terminal input)
    def web_permission_callback(description, action_type):
        logger.info(f"Web auto-approve: {description}")
        return True

    # Create Instagram + Agent
    ig = Instagram.from_env(env_path)

    # Resolve API key
    api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")

    agent = InstaAgent(
        ig=ig,
        provider=provider,
        api_key=api_key,
        model=model,
        permission=permission,
        permission_callback=web_permission_callback,
        verbose=False,
    )

    coordinator = AgentCoordinator(
        ig=ig,
        provider=provider,
        api_key=api_key,
        model=model,
        permission=Permission.FULL_ACCESS,
        verbose=False,
    )

    app = FastAPI(title="InstaAPI Agent", version="1.0.0")

    # Static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # ─── Routes ───────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve main HTML page."""
        html_path = STATIC_DIR / "index.html"
        if html_path.exists():
            return HTMLResponse(html_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>InstaAPI Agent</h1><p>static/index.html not found</p>")

    @app.post("/api/ask")
    async def ask(request: Request):
        """Process a question."""
        body = await request.json()
        message = body.get("message", "")

        if not message:
            return JSONResponse({"error": "Message is empty"}, status_code=400)

        try:
            result = agent.ask(message)
            return JSONResponse({
                "success": result.success,
                "answer": result.answer,
                "code": result.code_executed,
                "files": result.files_created,
                "steps": result.steps,
                "tokens": result.tokens_used,
                "duration": round(result.duration, 2),
                "error": result.error,
            })
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.post("/api/parallel")
    async def parallel(request: Request):
        """Run multiple tasks in parallel."""
        body = await request.json()
        tasks = body.get("tasks", [])

        if not tasks:
            return JSONResponse({"error": "Task list is empty"}, status_code=400)

        try:
            result = coordinator.run_parallel(tasks)
            return JSONResponse({
                "success": result.success,
                "results": [
                    {
                        "answer": r.answer,
                        "success": r.success,
                        "duration": round(r.duration, 2),
                    }
                    for r in result.results
                ],
                "total_duration": round(result.total_duration, 2),
                "total_tokens": result.total_tokens,
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/api/history")
    async def history():
        """Get conversation history."""
        return JSONResponse({
            "history": [
                {"role": m["role"], "content": str(m.get("content", ""))[:300]}
                for m in agent.history
            ]
        })

    @app.post("/api/reset")
    async def reset():
        """Reset conversation."""
        agent.reset()
        return JSONResponse({"status": "reset"})

    @app.get("/api/info")
    async def info():
        """Agent info."""
        return JSONResponse({
            "provider": agent.provider_name,
            "history_length": len(agent.history),
            "instagram": {
                "sessions": ig.session_count,
                "proxies": ig._proxy_mgr.active_count,
            },
        })

    return app


def main():
    """Run web server."""
    import argparse

    parser = argparse.ArgumentParser(description="🤖 InstaAPI Agent Web UI")
    parser.add_argument("--port", type=int, default=8899, help="Port (default: 8899)")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--provider", default="gemini", help="AI provider")
    parser.add_argument("--model", default=None, help="AI model")
    parser.add_argument("--api-key", default=None, help="AI API key")
    parser.add_argument("--env", default=".env", help="Path to .env file")
    parser.add_argument("--permission", default="full_access", help="Permission level")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not found. Install with: pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    app = create_app(
        env_path=args.env,
        provider=args.provider,
        api_key=args.api_key,
        model=args.model,
        permission_level=args.permission,
    )

    print(f"\nInstaAPI Agent Web UI")
    print(f"   http://{args.host}:{args.port}")
    print(f"   Provider: {args.provider}")
    print(f"   Press Ctrl+C to stop\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()

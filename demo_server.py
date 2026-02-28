"""
instaharvest_v2 Web Playground v2 — Enhanced Demo Server
===================================================
Full-featured web playground for testing instaharvest_v2 library.
Features: AI Chat, Data Saving, Full API Coverage, Export.

Usage:
    python demo_server.py
    # Opens http://localhost:8877
"""

import csv
import io
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── FastAPI ─────────────────────────────────────────────
try:
    from fastapi import FastAPI, Query, Request
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    print("❌ FastAPI not found. Install:\n  pip install fastapi uvicorn")
    sys.exit(1)

# ── instaharvest_v2 ────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from instaharvest_v2 import Instagram

logger = logging.getLogger("demo_server")

DEMO_DIR = Path(__file__).parent / "demo"
SAVED_DIR = DEMO_DIR / "saved"
SAVED_DIR.mkdir(parents=True, exist_ok=True)

# ── Create app ──────────────────────────────────────────

app = FastAPI(title="instaharvest_v2 Playground", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ══════════════════════════════════════════════════════════
#  GLOBAL STATE
# ══════════════════════════════════════════════════════════

_ig: Optional[Instagram] = None
_agent = None
_start_time = time.time()
_request_count = 0
_error_count = 0
_last_result: Optional[Dict] = None
_history: List[Dict] = []


def get_ig() -> Instagram:
    global _ig
    if _ig is None:
        env_path = os.environ.get("instaharvest_v2_ENV", ".env")
        _ig = Instagram.from_env(env_path)
        logger.info("Instagram client initialized from %s", env_path)
    return _ig


def get_agent():
    """Lazy-create AI agent."""
    global _agent
    if _agent is not None:
        return _agent

    try:
        from instaharvest_v2.agent.core import InstaAgent
        from instaharvest_v2.agent.permissions import Permission

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        provider = "gemini" if os.environ.get("GEMINI_API_KEY") else "openai"

        if not api_key:
            return None

        _agent = InstaAgent(
            ig=get_ig(),
            provider=provider,
            api_key=api_key,
            permission=Permission.FULL_ACCESS,
            permission_callback=lambda desc, action: True,
            verbose=False,
        )
        logger.info("AI Agent initialized: provider=%s", provider)
        return _agent
    except Exception as e:
        logger.warning("Could not initialize AI Agent: %s", e)
        return None


# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════

def _to_json(obj) -> Any:
    """Convert any object to JSON-serializable form."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json(item) for item in obj]
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return {k: _to_json(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


def _success(data, message: str = "OK", endpoint: str = ""):
    global _request_count, _last_result
    _request_count += 1
    result = {
        "success": True,
        "message": message,
        "data": _to_json(data),
        "timestamp": time.time(),
    }
    _last_result = result
    # Save to history
    _history.append({
        "endpoint": endpoint,
        "message": message,
        "time": datetime.now().strftime("%H:%M:%S"),
        "success": True,
    })
    if len(_history) > 100:
        _history.pop(0)
    return JSONResponse(result)


def _error(msg: str, status_code: int = 500, endpoint: str = ""):
    global _error_count
    _error_count += 1
    _history.append({
        "endpoint": endpoint,
        "message": f"❌ {msg}",
        "time": datetime.now().strftime("%H:%M:%S"),
        "success": False,
    })
    return JSONResponse(
        {"success": False, "error": msg, "timestamp": time.time()},
        status_code=status_code,
    )


# ══════════════════════════════════════════════════════════
#  ROUTES — UI
# ══════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = DEMO_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>instaharvest_v2 Playground</h1><p>demo/index.html not found</p>")


# ══════════════════════════════════════════════════════════
#  ROUTES — STATUS & HISTORY
# ══════════════════════════════════════════════════════════

@app.get("/api/status")
async def status():
    uptime = time.time() - _start_time
    agent = get_agent()
    return JSONResponse({
        "status": "running",
        "uptime_seconds": round(uptime, 1),
        "total_requests": _request_count,
        "total_errors": _error_count,
        "client_ready": _ig is not None,
        "ai_available": agent is not None,
        "ai_provider": agent.provider_name if agent else None,
    })


@app.get("/api/history")
async def get_history():
    return JSONResponse({"history": list(reversed(_history[-50:]))})


# ══════════════════════════════════════════════════════════
#  ROUTES — AI CHAT (InstaAgent)
# ══════════════════════════════════════════════════════════

@app.post("/api/ai/ask")
async def ai_ask(request: Request):
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return _error("Message is empty", 400, "ai/ask")

    agent = get_agent()
    if agent is None:
        return _error(
            "AI Agent not available. Set GEMINI_API_KEY or OPENAI_API_KEY in .env",
            503, "ai/ask",
        )

    try:
        result = agent.ask(message)

        # Build answer — result.answer may be empty if LLM only used tool calls
        answer = result.answer or ""

        # If answer is empty, try to extract from execution result
        if not answer.strip() and result.execution_result:
            exec_res = result.execution_result
            # ExecutionResult has .output, .return_value, .error
            if hasattr(exec_res, 'output') and exec_res.output and exec_res.output.strip():
                answer = exec_res.output.strip()
            elif hasattr(exec_res, 'return_value') and exec_res.return_value:
                answer = str(exec_res.return_value).strip()
            elif hasattr(exec_res, 'error') and exec_res.error:
                answer = f"Error: {exec_res.error}"
            else:
                exec_out = str(exec_res)
                if exec_out and exec_out.strip():
                    answer = exec_out.strip()

        # If still empty, check the last assistant message in history
        if not answer.strip():
            for msg in reversed(agent.history):
                if msg.get("role") == "assistant":
                    content = str(msg.get("content", ""))
                    if content.strip():
                        answer = content.strip()
                        break
                elif msg.get("role") == "tool":
                    content = str(msg.get("content", ""))
                    if content.strip() and len(content) > 5:
                        answer = content.strip()
                        break

        # Last fallback — show code executed
        if not answer.strip() and result.code_executed:
            answer = f"Executed code:\n```python\n{result.code_executed}\n```"

        logger.info("AI answer length: %d, code: %s", len(answer), bool(result.code_executed))

        return JSONResponse({
            "success": result.success,
            "answer": answer,
            "code": result.code_executed,
            "files": result.files_created,
            "steps": result.steps,
            "tokens": result.tokens_used,
            "duration": round(result.duration, 2),
            "error": result.error,
        })
    except Exception as e:
        logger.error("AI Agent error: %s", traceback.format_exc())
        return _error(f"AI Agent error: {e}", 500, "ai/ask")


@app.post("/api/ai/ask/stream")
async def ai_ask_stream(request: Request):
    """
    Server-Sent Events (SSE) streaming endpoint for AI Agent.

    Streams the agent's internal steps in real time:
      - thinking: LLM is processing
      - code: Python code extracted/generated
      - tool_call: Tool being invoked
      - tool_result: Tool execution result
      - done: Final answer ready
      - error: Something went wrong
    """
    import asyncio
    import threading

    body = await request.json()
    message = body.get("message", "").strip()

    if not message:
        # Return error as SSE for consistency
        async def _err_gen():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Message is empty'})}\n\n"
        return StreamingResponse(_err_gen(), media_type="text/event-stream")

    agent = get_agent()
    if agent is None:
        async def _err_gen():
            yield f"data: {json.dumps({'type': 'error', 'message': 'AI Agent not available. Set GEMINI_API_KEY or OPENAI_API_KEY in .env'})}\n\n"
        return StreamingResponse(_err_gen(), media_type="text/event-stream")

    # Async queue bridges sync agent thread ↔ async SSE generator
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _step_callback(event: dict):
        """Called from the sync agent thread; pushes events into the async queue."""
        asyncio.run_coroutine_threadsafe(queue.put(event), loop)

    def _run_agent():
        """Runs the synchronous agent.ask() in a background thread."""
        try:
            result = agent.ask(message, step_callback=_step_callback)

            # Build enriched answer (same logic as the regular /api/ai/ask)
            answer = result.answer or ""
            if not answer.strip() and result.execution_result:
                exec_res = result.execution_result
                if hasattr(exec_res, 'output') and exec_res.output and exec_res.output.strip():
                    answer = exec_res.output.strip()
                elif hasattr(exec_res, 'return_value') and exec_res.return_value:
                    answer = str(exec_res.return_value).strip()
                elif hasattr(exec_res, 'error') and exec_res.error:
                    answer = f"Error: {exec_res.error}"
                else:
                    exec_out = str(exec_res)
                    if exec_out and exec_out.strip():
                        answer = exec_out.strip()

            if not answer.strip():
                for msg in reversed(agent.history):
                    if msg.get("role") == "assistant":
                        content = str(msg.get("content", ""))
                        if content.strip():
                            answer = content.strip()
                            break
                    elif msg.get("role") == "tool":
                        content = str(msg.get("content", ""))
                        if content.strip() and len(content) > 5:
                            answer = content.strip()
                            break

            if not answer.strip() and result.code_executed:
                answer = f"Executed code:\n```python\n{result.code_executed}\n```"

            # Push final "done" event
            asyncio.run_coroutine_threadsafe(queue.put({
                "type": "done",
                "answer": answer,
                "code": result.code_executed,
                "files": result.files_created,
                "steps": result.steps,
                "tokens": result.tokens_used,
                "duration": round(result.duration, 2),
                "error": result.error,
                "success": result.success,
            }), loop)

        except Exception as e:
            logger.error("AI Agent SSE error: %s", traceback.format_exc())
            asyncio.run_coroutine_threadsafe(queue.put({
                "type": "error",
                "message": f"AI Agent error: {e}",
            }), loop)

    # Launch agent in background thread
    threading.Thread(target=_run_agent, daemon=True).start()

    async def _event_generator():
        """Yields SSE-formatted events from the queue until done/error."""
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=120)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                # Safety: prevent infinite hanging
                yield f"data: {json.dumps({'type': 'error', 'message': 'Timeout: agent took too long'})}\n\n"
                break

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/ai/reset")
async def ai_reset():
    agent = get_agent()
    if agent:
        agent.reset()
    return JSONResponse({"status": "reset"})


@app.get("/api/ai/history")
async def ai_history():
    agent = get_agent()
    if not agent:
        return JSONResponse({"history": []})
    return JSONResponse({
        "history": [
            {"role": m.get("role", ""), "content": str(m.get("content", ""))[:500]}
            for m in agent.history
        ]
    })


# ══════════════════════════════════════════════════════════
#  ROUTES — DATA SAVING & EXPORT
# ══════════════════════════════════════════════════════════

@app.post("/api/save")
async def save_result(request: Request):
    body = await request.json()
    data = body.get("data", _last_result)
    name = body.get("name", "")

    if not data:
        return _error("No data to save", 400, "save")

    if not name:
        name = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Sanitize filename
    safe_name = "".join(c for c in name if c.isalnum() or c in "_-").strip()
    if not safe_name:
        safe_name = f"result_{int(time.time())}"

    filepath = SAVED_DIR / f"{safe_name}.json"
    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    return JSONResponse({
        "success": True,
        "filename": f"{safe_name}.json",
        "path": str(filepath),
        "size": filepath.stat().st_size,
    })


@app.get("/api/saved")
async def list_saved():
    files = []
    for f in sorted(SAVED_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return JSONResponse({"files": files})


@app.get("/api/saved/{filename}")
async def get_saved(filename: str):
    filepath = SAVED_DIR / filename
    if not filepath.exists() or not filepath.suffix == ".json":
        return _error("File not found", 404, f"saved/{filename}")
    data = json.loads(filepath.read_text(encoding="utf-8"))
    return JSONResponse(data)


@app.delete("/api/saved/{filename}")
async def delete_saved(filename: str):
    filepath = SAVED_DIR / filename
    if filepath.exists() and filepath.suffix == ".json":
        filepath.unlink()
        return JSONResponse({"success": True, "deleted": filename})
    return _error("File not found", 404, f"saved/{filename}")


@app.post("/api/export/csv")
async def export_csv(request: Request):
    """Export last result as CSV."""
    body = await request.json()
    data = body.get("data")

    if not data:
        return _error("No data to export", 400, "export/csv")

    # Flatten data for CSV
    rows = []
    raw = data.get("data", data) if isinstance(data, dict) else data
    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict):
        # Try to find a list inside
        for k, v in raw.items():
            if isinstance(v, list) and len(v) > 0:
                rows = v
                break
        if not rows:
            rows = [raw]

    if not rows:
        return _error("No tabular data to export", 400, "export/csv")

    # Build CSV
    output = io.StringIO()
    if isinstance(rows[0], dict):
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(v) if not isinstance(v, (str, int, float, bool)) else v for k, v in row.items()})
    else:
        writer = csv.writer(output)
        for row in rows:
            writer.writerow([row] if not isinstance(row, (list, tuple)) else row)

    output.seek(0)
    filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ══════════════════════════════════════════════════════════
#  ROUTES — USERS (enhanced)
# ══════════════════════════════════════════════════════════

@app.get("/api/users/username/{username}")
async def get_user_by_username(username: str):
    try:
        ig = get_ig()
        user = ig.users.get_by_username(username)
        return _success(user, f"Profile: @{username}", f"users/username/{username}")
    except Exception as e:
        return _error(str(e), endpoint=f"users/username/{username}")


@app.get("/api/users/id/{user_id}")
async def get_user_by_id(user_id: str):
    try:
        ig = get_ig()
        user = ig.users.get_by_id(user_id)
        return _success(user, f"User ID: {user_id}", f"users/id/{user_id}")
    except Exception as e:
        return _error(str(e), endpoint=f"users/id/{user_id}")


@app.get("/api/users/search")
async def search_users(q: str = Query(...)):
    try:
        ig = get_ig()
        users = ig.users.search(q)
        count = len(users) if isinstance(users, list) else "?"
        return _success(users, f"Found {count} users for '{q}'", f"users/search?q={q}")
    except Exception as e:
        return _error(str(e), endpoint="users/search")


@app.get("/api/users/full/{username}")
async def get_full_profile(username: str):
    try:
        ig = get_ig()
        profile = ig.users.get_full_profile(username)
        return _success(profile, f"Full profile: @{username}", f"users/full/{username}")
    except Exception as e:
        return _error(str(e), endpoint=f"users/full/{username}")


@app.get("/api/users/bio/{username}")
async def parse_bio(username: str):
    try:
        ig = get_ig()
        user = ig.users.get_by_username(username)
        bio = ig.users.parse_bio(user)
        return _success(bio, f"Bio parsed: @{username}", f"users/bio/{username}")
    except Exception as e:
        return _error(str(e), endpoint=f"users/bio/{username}")


# ══════════════════════════════════════════════════════════
#  ROUTES — MEDIA (enhanced)
# ══════════════════════════════════════════════════════════

@app.get("/api/media/info/{media_pk}")
async def get_media_info(media_pk: str):
    try:
        ig = get_ig()
        media = ig.media.get_info(media_pk)
        return _success(media, f"Media: {media_pk}", f"media/info/{media_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"media/info/{media_pk}")


@app.get("/api/media/full/{media_pk}")
async def get_media_full(media_pk: str):
    try:
        ig = get_ig()
        media = ig.media.get_full_info(media_pk)
        return _success(media, f"Full media: {media_pk}", f"media/full/{media_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"media/full/{media_pk}")


@app.get("/api/media/v2/{media_pk}")
async def get_media_v2(media_pk: str):
    try:
        ig = get_ig()
        media = ig.media.get_info_v2(media_pk)
        return _success(media, f"Media v2: {media_pk}", f"media/v2/{media_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"media/v2/{media_pk}")


@app.get("/api/media/by-url")
async def get_media_by_url(url: str = Query(...)):
    try:
        ig = get_ig()
        media = ig.media.get_by_url_v2(url)
        return _success(media, f"Media by URL", "media/by-url")
    except Exception as e:
        return _error(str(e), endpoint="media/by-url")


@app.get("/api/media/likers/{media_pk}")
async def get_media_likers(media_pk: str):
    try:
        ig = get_ig()
        likers = ig.media.get_likers(media_pk)
        return _success(likers, f"Likers: {media_pk}", f"media/likers/{media_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"media/likers/{media_pk}")


@app.get("/api/media/comments/{media_pk}")
async def get_media_comments(media_pk: str):
    try:
        ig = get_ig()
        comments = ig.media.get_comments_parsed(media_pk)
        return _success(comments, f"Comments: {media_pk}", f"media/comments/{media_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"media/comments/{media_pk}")


# ══════════════════════════════════════════════════════════
#  ROUTES — FEED
# ══════════════════════════════════════════════════════════

@app.get("/api/feed/user/{user_pk}")
async def get_user_feed(user_pk: str, count: int = 12):
    try:
        ig = get_ig()
        feed = ig.feed.get_user_feed(user_pk, count=count)
        return _success(feed, f"Feed: {user_pk}", f"feed/user/{user_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"feed/user/{user_pk}")


@app.get("/api/feed/tag/{hashtag}")
async def get_tag_feed(hashtag: str):
    try:
        ig = get_ig()
        feed = ig.feed.get_tag_feed(hashtag)
        return _success(feed, f"Tag: #{hashtag}", f"feed/tag/{hashtag}")
    except Exception as e:
        return _error(str(e), endpoint=f"feed/tag/{hashtag}")


@app.get("/api/feed/liked")
async def get_liked_feed():
    try:
        ig = get_ig()
        feed = ig.feed.get_liked()
        return _success(feed, "Liked posts", "feed/liked")
    except Exception as e:
        return _error(str(e), endpoint="feed/liked")


@app.get("/api/feed/saved")
async def get_saved_feed():
    try:
        ig = get_ig()
        feed = ig.feed.get_saved()
        return _success(feed, "Saved posts", "feed/saved")
    except Exception as e:
        return _error(str(e), endpoint="feed/saved")


# ══════════════════════════════════════════════════════════
#  ROUTES — SEARCH
# ══════════════════════════════════════════════════════════

@app.get("/api/search/top")
async def top_search(q: str = Query(...)):
    try:
        ig = get_ig()
        results = ig.search.top_search(q)
        return _success(results, f"Top search: {q}", f"search/top?q={q}")
    except Exception as e:
        return _error(str(e), endpoint="search/top")


@app.get("/api/search/users")
async def search_users_api(q: str = Query(...)):
    try:
        ig = get_ig()
        users = ig.search.search_users(q)
        return _success(users, f"Users: {q}", f"search/users?q={q}")
    except Exception as e:
        return _error(str(e), endpoint="search/users")


@app.get("/api/search/hashtags")
async def search_hashtags(q: str = Query(...)):
    try:
        ig = get_ig()
        tags = ig.search.search_hashtags(q)
        return _success(tags, f"Hashtags: {q}", f"search/hashtags?q={q}")
    except Exception as e:
        return _error(str(e), endpoint="search/hashtags")


@app.get("/api/search/places")
async def search_places(q: str = Query(...)):
    try:
        ig = get_ig()
        places = ig.search.search_places(q)
        return _success(places, f"Places: {q}", f"search/places?q={q}")
    except Exception as e:
        return _error(str(e), endpoint="search/places")


@app.get("/api/search/explore")
async def explore():
    try:
        ig = get_ig()
        data = ig.search.explore()
        return _success(data, "Explore page", "search/explore")
    except Exception as e:
        return _error(str(e), endpoint="search/explore")


# ══════════════════════════════════════════════════════════
#  ROUTES — STORIES
# ══════════════════════════════════════════════════════════

@app.get("/api/stories/user/{user_pk}")
async def get_user_stories(user_pk: str):
    try:
        ig = get_ig()
        stories = ig.stories.get_user_stories(user_pk)
        return _success(stories, f"Stories: {user_pk}", f"stories/user/{user_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"stories/user/{user_pk}")


@app.get("/api/stories/highlights/{user_pk}")
async def get_highlights(user_pk: str):
    try:
        ig = get_ig()
        highlights = ig.stories.get_highlights_tray(user_pk)
        return _success(highlights, f"Highlights: {user_pk}", f"stories/highlights/{user_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"stories/highlights/{user_pk}")


@app.get("/api/stories/tray")
async def get_stories_tray():
    try:
        ig = get_ig()
        tray = ig.stories.get_tray()
        return _success(tray, "Stories tray", "stories/tray")
    except Exception as e:
        return _error(str(e), endpoint="stories/tray")


# ══════════════════════════════════════════════════════════
#  ROUTES — FRIENDSHIPS
# ══════════════════════════════════════════════════════════

@app.get("/api/friendships/followers/{user_pk}")
async def get_followers(user_pk: str, count: int = 50):
    try:
        ig = get_ig()
        result = ig.friendships.get_followers(user_pk, count=count)
        return _success(result, f"Followers: {user_pk}", f"friendships/followers/{user_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"friendships/followers/{user_pk}")


@app.get("/api/friendships/following/{user_pk}")
async def get_following(user_pk: str, count: int = 50):
    try:
        ig = get_ig()
        result = ig.friendships.get_following(user_pk, count=count)
        return _success(result, f"Following: {user_pk}", f"friendships/following/{user_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"friendships/following/{user_pk}")


@app.get("/api/friendships/status/{user_pk}")
async def friendship_status(user_pk: str):
    try:
        ig = get_ig()
        result = ig.friendships.show(user_pk)
        return _success(result, f"Status: {user_pk}", f"friendships/status/{user_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"friendships/status/{user_pk}")


@app.get("/api/friendships/mutual/{user_pk}")
async def get_mutual_followers(user_pk: str):
    try:
        ig = get_ig()
        result = ig.friendships.get_mutual_followers(user_pk)
        return _success(result, f"Mutual: {user_pk}", f"friendships/mutual/{user_pk}")
    except Exception as e:
        return _error(str(e), endpoint=f"friendships/mutual/{user_pk}")


@app.get("/api/friendships/pending")
async def get_pending():
    try:
        ig = get_ig()
        result = ig.friendships.get_pending_requests()
        return _success(result, "Pending requests", "friendships/pending")
    except Exception as e:
        return _error(str(e), endpoint="friendships/pending")


# ══════════════════════════════════════════════════════════
#  ROUTES — ACCOUNT (enhanced)
# ══════════════════════════════════════════════════════════

@app.get("/api/account/me")
async def get_current_user():
    try:
        ig = get_ig()
        try:
            user = ig.account.get_current_user()
            if isinstance(user, dict) and user.get("status") == "fail":
                raise Exception(user.get("message", "Session error"))
            return _success(user, "My profile", "account/me")
        except Exception:
            # Fallback to account info
            info = ig.account.get_account_info()
            return _success(info, "My profile (via account info)", "account/me")
    except Exception as e:
        return _error(str(e), endpoint="account/me")


@app.get("/api/account/blocked")
async def get_blocked():
    try:
        ig = get_ig()
        blocked = ig.account.get_blocked_users()
        return _success(blocked, "Blocked users", "account/blocked")
    except Exception as e:
        return _error(str(e), endpoint="account/blocked")


@app.get("/api/account/restricted")
async def get_restricted():
    try:
        ig = get_ig()
        restricted = ig.account.get_restricted_users()
        return _success(restricted, "Restricted users", "account/restricted")
    except Exception as e:
        return _error(str(e), endpoint="account/restricted")


@app.get("/api/account/login-activity")
async def get_login_activity():
    try:
        ig = get_ig()
        activity = ig.account.get_login_activity()
        return _success(activity, "Login activity", "account/login-activity")
    except Exception as e:
        return _error(str(e), endpoint="account/login-activity")


@app.get("/api/account/privacy")
async def get_privacy():
    try:
        ig = get_ig()
        privacy = ig.account.get_privacy_settings()
        return _success(privacy, "Privacy settings", "account/privacy")
    except Exception as e:
        return _error(str(e), endpoint="account/privacy")


@app.get("/api/account/info")
async def get_account_info():
    try:
        ig = get_ig()
        info = ig.account.get_account_info()
        return _success(info, "Account info", "account/info")
    except Exception as e:
        return _error(str(e), endpoint="account/info")


# ══════════════════════════════════════════════════════════
#  ROUTES — PUBLIC
# ══════════════════════════════════════════════════════════

@app.get("/api/public/profile/{username}")
async def get_public_profile(username: str):
    try:
        ig = get_ig()
        profile = ig.public.get_profile(username)
        return _success(profile, f"Public: @{username}", f"public/profile/{username}")
    except Exception as e:
        return _error(str(e), endpoint=f"public/profile/{username}")


@app.get("/api/public/posts/{username}")
async def get_public_posts(username: str, count: int = 12):
    try:
        ig = get_ig()
        posts = ig.public.get_posts(username, max_count=count)
        return _success(posts, f"Posts: @{username} ({len(posts)})", f"public/posts/{username}")
    except Exception as e:
        return _error(str(e), endpoint=f"public/posts/{username}")


@app.get("/api/public/reels/{username}")
async def get_public_reels(username: str, count: int = 12):
    """Get user reels (anonymous)."""
    try:
        ig = get_ig()
        reels = ig.public.get_reels(username, max_count=count)
        return _success(reels, f"Reels: @{username} ({len(reels)})", f"public/reels/{username}")
    except Exception as e:
        return _error(str(e), endpoint=f"public/reels/{username}")


@app.get("/api/public/highlights/{username}")
async def get_public_highlights(username: str):
    """Get user story highlights (anonymous)."""
    try:
        ig = get_ig()
        highlights = ig.public.get_highlights(username)
        return _success(highlights, f"Highlights: @{username}", f"public/highlights/{username}")
    except Exception as e:
        return _error(str(e), endpoint=f"public/highlights/{username}")


@app.get("/api/public/similar/{username}")
async def get_public_similar(username: str):
    """Get similar accounts (anonymous)."""
    try:
        ig = get_ig()
        similar = ig.public.get_similar_accounts(username)
        return _success(similar, f"Similar accounts for @{username}", f"public/similar/{username}")
    except Exception as e:
        return _error(str(e), endpoint=f"public/similar/{username}")


@app.get("/api/public/search")
async def public_search(q: str = Query(...), context: str = "blended"):
    """Search Instagram anonymously."""
    try:
        ig = get_ig()
        results = ig.public.search(q, context=context)
        return _success(results, f"Search: '{q}' ({context})", "public/search")
    except Exception as e:
        return _error(str(e), endpoint="public/search")


@app.get("/api/public/comments/{shortcode}")
async def get_public_comments(shortcode: str, count: int = 24):
    """Get post comments (anonymous)."""
    try:
        ig = get_ig()
        comments = ig.public.get_comments(shortcode, max_count=count)
        return _success(comments, f"Comments for {shortcode}", f"public/comments/{shortcode}")
    except Exception as e:
        return _error(str(e), endpoint=f"public/comments/{shortcode}")


@app.get("/api/public/media_urls/{shortcode}")
async def get_public_media_urls(shortcode: str):
    """Get all media URLs from a post (anonymous)."""
    try:
        ig = get_ig()
        urls = ig.public.get_media_urls(shortcode)
        return _success(urls, f"Media URLs for {shortcode}", f"public/media_urls/{shortcode}")
    except Exception as e:
        return _error(str(e), endpoint=f"public/media_urls/{shortcode}")


# ══════════════════════════════════════════════════════════
#  ROUTES — HASHTAGS
# ══════════════════════════════════════════════════════════

@app.get("/api/hashtags/info/{tag}")
async def get_hashtag_info(tag: str):
    try:
        ig = get_ig()
        info = ig.hashtags.get_info(tag)
        return _success(info, f"#{tag}", f"hashtags/info/{tag}")
    except Exception as e:
        return _error(str(e), endpoint=f"hashtags/info/{tag}")


# ══════════════════════════════════════════════════════════
#  ROUTES — NOTIFICATIONS
# ══════════════════════════════════════════════════════════

@app.get("/api/notifications")
async def get_notifications():
    try:
        ig = get_ig()
        notif = ig.notifications.get_activity()
        return _success(notif, "Notifications", "notifications")
    except Exception as e:
        return _error(str(e), endpoint="notifications")


@app.get("/api/notifications/counts")
async def get_notification_counts():
    try:
        ig = get_ig()
        counts = ig.notifications.get_counts_parsed()
        return _success(counts, "Notification counts", "notifications/counts")
    except Exception as e:
        return _error(str(e), endpoint="notifications/counts")


@app.get("/api/notifications/parsed")
async def get_notifications_parsed():
    try:
        ig = get_ig()
        notifs = ig.notifications.get_all_parsed()
        return _success(notifs, "All notifications (parsed)", "notifications/parsed")
    except Exception as e:
        return _error(str(e), endpoint="notifications/parsed")


@app.get("/api/notifications/follows")
async def get_follow_notifications():
    try:
        ig = get_ig()
        follows = ig.notifications.get_follow_notifications()
        return _success(follows, "Follow notifications", "notifications/follows")
    except Exception as e:
        return _error(str(e), endpoint="notifications/follows")


@app.get("/api/notifications/likes")
async def get_like_notifications():
    try:
        ig = get_ig()
        likes = ig.notifications.get_like_notifications()
        return _success(likes, "Like notifications", "notifications/likes")
    except Exception as e:
        return _error(str(e), endpoint="notifications/likes")


# ══════════════════════════════════════════════════════════
#  ROUTES — DIRECT MESSAGES
# ══════════════════════════════════════════════════════════

@app.get("/api/direct/inbox")
async def get_inbox():
    try:
        ig = get_ig()
        inbox = ig.direct.get_inbox()
        return _success(inbox, "DM Inbox", "direct/inbox")
    except Exception as e:
        return _error(str(e), endpoint="direct/inbox")


# ══════════════════════════════════════════════════════════
#  ROUTES — DASHBOARD
# ══════════════════════════════════════════════════════════

@app.get("/api/dashboard")
async def get_dashboard():
    try:
        ig = get_ig()
        stats = ig.dashboard.status()
        return _success(stats, "Dashboard", "dashboard")
    except Exception as e:
        return _error(str(e), endpoint="dashboard")


# ══════════════════════════════════════════════════════════
#  ROUTES — DOWNLOAD MANAGER
# ══════════════════════════════════════════════════════════

import urllib.request
import uuid
import threading
import asyncio

DOWNLOADS_DIR = Path(__file__).parent / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_dotpath(obj, path):
    """Resolve a dot-separated path on a dict, supporting array indices.

    Examples:
        _resolve_dotpath(d, "edge_followed_by.count")
        _resolve_dotpath(d, "edges.0.node.text")  # 0 = array index
    """
    parts = path.split(".")
    val = obj
    for part in parts:
        if val is None:
            return None
        if isinstance(val, dict):
            val = val.get(part)
        elif isinstance(val, (list, tuple)):
            try:
                val = val[int(part)]
            except (IndexError, ValueError):
                return None
        else:
            return None
    return val


def _pval(p, key, default=0):
    """Extract profile value with fallback keys for different API formats."""
    MAP = {
        "followers": ["followers", "follower_count", "edge_followed_by.count"],
        "following": ["following", "following_count", "edge_follow.count"],
        "posts_count": ["posts_count", "media_count", "edge_owner_to_timeline_media.count"],
        "bio": ["biography", "bio"],
        "pic": ["profile_pic_url", "profile_pic_url_hd"],
        "name": ["full_name"],
        "verified": ["is_verified"],
        "private": ["is_private"],
        "category": ["category_name", "category", "business_category_name"],
        "url": ["external_url"],
    }
    keys = MAP.get(key, [key])
    if isinstance(p, dict):
        for k in keys:
            if "." in k:
                val = _resolve_dotpath(p, k)
                if val is not None and val != {}:
                    return val
            elif k in p and p[k] is not None:
                return p[k]
    return default


def _postval(post, key, default=0):
    """Extract post value with dot-path and array index support."""
    MAP = {
        "likes": ["likes", "like_count", "edge_liked_by.count", "edge_media_preview_like.count"],
        "comments": ["comments", "comment_count", "edge_media_to_comment.count"],
        "caption": ["caption_text", "caption", "edge_media_to_caption.edges.0.node.text"],
        "display_url": ["display_url", "image_versions2.candidates.0.url", "thumbnail_src"],
        "video_url": ["video_url", "video_versions.0.url"],
        "shortcode": ["shortcode", "code"],
        "timestamp": ["taken_at_timestamp", "taken_at", "date"],
    }
    keys = MAP.get(key, [key])
    if isinstance(post, dict):
        for k in keys:
            if "." in k:
                val = _resolve_dotpath(post, k)
                if val is not None and val != {}:
                    return val
            elif k in post and post[k] is not None:
                return post[k]
    return default


@app.get("/api/download/list")
async def list_downloads():
    """List all downloaded files."""
    files = []
    for f in sorted(DOWNLOADS_DIR.rglob("*")):
        if f.is_file() and not f.name.startswith("_"):
            stat = f.stat()
            files.append({
                "name": f.name,
                "path": str(f.relative_to(DOWNLOADS_DIR)),
                "full_path": str(f.absolute()),
                "size": stat.st_size,
                "size_human": f"{stat.st_size / 1024:.1f} KB" if stat.st_size < 1048576 else f"{stat.st_size / 1048576:.1f} MB",
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "type": f.suffix.lower().lstrip("."),
            })
    return _success(files, f"{len(files)} files", "download/list")


@app.post("/api/download/profile_pic")
async def download_profile_pic(request: Request):
    """Download a user's profile picture."""
    try:
        body = await request.json()
        username = body.get("username", "").strip()
        if not username:
            return _error("Username required", 400, "download/profile_pic")
        ig = get_ig()
        profile = ig.public.get_profile(username)
        pic_url = _pval(profile, "pic", "")
        if not pic_url:
            return _error("No profile pic found", 404, "download/profile_pic")
        user_dir = DOWNLOADS_DIR / username
        user_dir.mkdir(parents=True, exist_ok=True)
        filepath = user_dir / f"{username}_profile.jpg"
        req = urllib.request.Request(pic_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            filepath.write_bytes(resp.read())
        return _success({
            "file": str(filepath.absolute()),
            "size": filepath.stat().st_size,
            "username": username,
        }, f"Profile pic downloaded", "download/profile_pic")
    except Exception as e:
        return _error(str(e), endpoint="download/profile_pic")


@app.post("/api/download/posts")
async def download_posts(request: Request):
    """Download images from user's posts."""
    try:
        body = await request.json()
        username = body.get("username", "").strip()
        count = min(int(body.get("count", 4)), 20)
        if not username:
            return _error("Username required", 400, "download/posts")
        ig = get_ig()
        posts = ig.public.get_posts(username, max_count=count)
        user_dir = DOWNLOADS_DIR / username
        user_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []
        for post in posts:
            url = post.get("display_url", "")
            shortcode = post.get("shortcode", str(uuid.uuid4())[:8])
            if url:
                filepath = user_dir / f"{shortcode}.jpg"
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        filepath.write_bytes(resp.read())
                    downloaded.append({
                        "shortcode": shortcode,
                        "file": str(filepath.absolute()),
                        "size": filepath.stat().st_size,
                    })
                except Exception:
                    pass
        return _success({
            "downloaded": downloaded,
            "total": len(downloaded),
            "folder": str(user_dir.absolute()),
        }, f"{len(downloaded)} posts downloaded", "download/posts")
    except Exception as e:
        return _error(str(e), endpoint="download/posts")


# ══════════════════════════════════════════════════════════
#  ROUTES — ANALYTICS DASHBOARD
# ══════════════════════════════════════════════════════════

@app.get("/api/analytics/profile/{username}")
async def analytics_profile(username: str):
    """Deep analytics for a user profile."""
    try:
        ig = get_ig()
        profile = ig.public.get_profile(username)
        posts = ig.public.get_posts(username, max_count=12)
        followers = _pval(profile, "followers")
        following = _pval(profile, "following")
        total_likes = sum(_postval(p, "likes") for p in posts)
        total_comments = sum(_postval(p, "comments") for p in posts)
        post_count = len(posts) or 1
        avg_likes = total_likes / post_count
        avg_comments = total_comments / post_count
        engagement_rate = ((avg_likes + avg_comments) / max(followers, 1)) * 100
        follow_ratio = followers / max(following, 1)
        # Top posts by likes
        sorted_posts = sorted(posts, key=lambda p: _postval(p, "likes"), reverse=True)
        top_posts = []
        for p in sorted_posts[:5]:
            top_posts.append({
                "shortcode": p.get("shortcode", ""),
                "likes": _postval(p, "likes"),
                "comments": _postval(p, "comments"),
                "caption": str(_postval(p, "caption", ""))[:100],
            })
        # Hashtag analysis
        all_hashtags = []
        for p in posts:
            caption = str(_postval(p, "caption", "") or "")
            tags = [w.strip("#").lower() for w in caption.split() if w.startswith("#")]
            all_hashtags.extend(tags)
        from collections import Counter
        hashtag_freq = Counter(all_hashtags).most_common(10)
        return _success({
            "username": username,
            "followers": followers,
            "following": following,
            "follow_ratio": round(follow_ratio, 2),
            "total_posts_analyzed": post_count,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "avg_likes": round(avg_likes, 1),
            "avg_comments": round(avg_comments, 1),
            "engagement_rate": round(engagement_rate, 3),
            "engagement_quality": "Excellent" if engagement_rate > 5 else "Good" if engagement_rate > 2 else "Average" if engagement_rate > 1 else "Low",
            "top_posts": top_posts,
            "top_hashtags": [{"tag": t, "count": c} for t, c in hashtag_freq],
            "is_verified": _pval(profile, "verified", False),
            "is_private": _pval(profile, "private", False),
            "bio": _pval(profile, "bio", ""),
        }, "Analytics computed", "analytics/profile")
    except Exception as e:
        return _error(str(e), endpoint="analytics/profile")


# ══════════════════════════════════════════════════════════
#  ROUTES — SCHEDULED TASKS
# ══════════════════════════════════════════════════════════

_scheduled_tasks: Dict[str, Dict] = {}
_task_results: Dict[str, List] = {}


@app.post("/api/tasks/create")
async def create_task(request: Request):
    """Create a scheduled monitoring task."""
    try:
        body = await request.json()
        task_type = body.get("type", "profile_check")  # profile_check, follower_alert
        username = body.get("username", "").strip()
        interval_minutes = min(int(body.get("interval", 60)), 1440)
        if not username:
            return _error("Username required", 400, "tasks/create")
        task_id = str(uuid.uuid4())[:8]
        _scheduled_tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "username": username,
            "interval": interval_minutes,
            "created": datetime.now().isoformat(),
            "last_run": None,
            "status": "active",
            "runs": 0,
        }
        _task_results[task_id] = []
        # Run first check immediately
        try:
            ig = get_ig()
            profile = ig.public.get_profile(username)
            snapshot = {
                "time": datetime.now().isoformat(),
                "followers": _pval(profile, "followers"),
                "following": _pval(profile, "following"),
                "posts": _pval(profile, "posts_count"),
            }
            _task_results[task_id].append(snapshot)
            _scheduled_tasks[task_id]["last_run"] = snapshot["time"]
            _scheduled_tasks[task_id]["runs"] = 1
        except Exception:
            pass
        return _success(_scheduled_tasks[task_id], "Task created", "tasks/create")
    except Exception as e:
        return _error(str(e), endpoint="tasks/create")


@app.get("/api/tasks/list")
async def list_tasks():
    return _success(list(_scheduled_tasks.values()), f"{len(_scheduled_tasks)} tasks", "tasks/list")


@app.get("/api/tasks/{task_id}/results")
async def task_results(task_id: str):
    if task_id not in _scheduled_tasks:
        return _error("Task not found", 404, "tasks/results")
    return _success({
        "task": _scheduled_tasks[task_id],
        "results": _task_results.get(task_id, []),
    }, "Task results", "tasks/results")


@app.post("/api/tasks/{task_id}/run")
async def run_task(task_id: str):
    """Manually run a scheduled task now."""
    if task_id not in _scheduled_tasks:
        return _error("Task not found", 404, "tasks/run")
    task = _scheduled_tasks[task_id]
    try:
        ig = get_ig()
        profile = ig.public.get_profile(task["username"])
        snapshot = {
            "time": datetime.now().isoformat(),
            "followers": _pval(profile, "followers"),
            "following": _pval(profile, "following"),
            "posts": _pval(profile, "posts_count"),
        }
        _task_results[task_id].append(snapshot)
        task["last_run"] = snapshot["time"]
        task["runs"] += 1
        # Check for changes
        alert = None
        if len(_task_results[task_id]) >= 2:
            prev = _task_results[task_id][-2]
            diff = snapshot["followers"] - prev["followers"]
            if diff != 0:
                alert = f"Follower change: {'+' if diff > 0 else ''}{diff}"
        return _success({"snapshot": snapshot, "alert": alert}, "Task executed", "tasks/run")
    except Exception as e:
        return _error(str(e), endpoint="tasks/run")


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    if task_id in _scheduled_tasks:
        del _scheduled_tasks[task_id]
        _task_results.pop(task_id, None)
        return _success({"deleted": task_id}, "Task deleted", "tasks/delete")
    return _error("Task not found", 404, "tasks/delete")


# ══════════════════════════════════════════════════════════
#  ROUTES — COMPARE TOOL
# ══════════════════════════════════════════════════════════

@app.get("/api/compare")
async def compare_profiles(users: str = Query(..., description="Comma-separated usernames")):
    """Compare 2-3 profiles side by side."""
    try:
        usernames = [u.strip() for u in users.split(",") if u.strip()][:3]
        if len(usernames) < 2:
            return _error("At least 2 usernames required", 400, "compare")
        ig = get_ig()
        profiles = []
        for uname in usernames:
            try:
                p = ig.public.get_profile(uname)
                posts = ig.public.get_posts(uname, max_count=6)
                followers = _pval(p, "followers")
                following = _pval(p, "following")
                total_likes = sum(_postval(post, "likes") for post in posts)
                avg_likes = total_likes / max(len(posts), 1)
                engagement = ((avg_likes) / max(followers, 1)) * 100
                profiles.append({
                    "username": uname,
                    "full_name": _pval(p, "name", ""),
                    "followers": followers,
                    "following": following,
                    "posts_count": _pval(p, "posts_count"),
                    "avg_likes": round(avg_likes, 0),
                    "engagement_rate": round(engagement, 3),
                    "is_verified": _pval(p, "verified", False),
                    "is_private": _pval(p, "private", False),
                    "bio": str(_pval(p, "bio", "") or "")[:150],
                    "profile_pic": _pval(p, "pic", ""),
                })
            except Exception as ex:
                profiles.append({"username": uname, "error": str(ex)})
        # Determine winner
        valid = [p for p in profiles if "error" not in p]
        winner = max(valid, key=lambda x: x["followers"]) if valid else None
        return _success({
            "profiles": profiles,
            "winner_followers": winner["username"] if winner else None,
            "winner_engagement": max(valid, key=lambda x: x["engagement_rate"])["username"] if valid else None,
        }, f"Compared {len(profiles)} profiles", "compare")
    except Exception as e:
        return _error(str(e), endpoint="compare")


# ══════════════════════════════════════════════════════════
#  ROUTES — BATCH OPERATIONS
# ══════════════════════════════════════════════════════════

@app.post("/api/batch/scrape")
async def batch_scrape(request: Request):
    """Scrape multiple profiles at once."""
    try:
        body = await request.json()
        usernames = body.get("usernames", [])
        if isinstance(usernames, str):
            usernames = [u.strip() for u in usernames.split(",") if u.strip()]
        usernames = usernames[:20]  # Max 20
        if not usernames:
            return _error("Usernames list required", 400, "batch/scrape")
        ig = get_ig()
        results = []
        errors = []
        for uname in usernames:
            try:
                p = ig.public.get_profile(uname)
                results.append({
                    "username": uname,
                    "full_name": _pval(p, "name", ""),
                    "followers": _pval(p, "followers"),
                    "following": _pval(p, "following"),
                    "posts": _pval(p, "posts_count"),
                    "bio": str(_pval(p, "bio", "") or "")[:200],
                    "is_verified": _pval(p, "verified", False),
                    "is_private": _pval(p, "private", False),
                    "profile_pic": _pval(p, "pic", ""),
                })
            except Exception as ex:
                errors.append({"username": uname, "error": str(ex)})
        # Save results
        global _last_result
        _last_result = results
        return _success({
            "results": results,
            "errors": errors,
            "total_success": len(results),
            "total_errors": len(errors),
        }, f"Scraped {len(results)}/{len(usernames)}", "batch/scrape")
    except Exception as e:
        return _error(str(e), endpoint="batch/scrape")


@app.post("/api/batch/import")
async def batch_import(request: Request):
    """Import usernames from text (one per line or comma-separated)."""
    try:
        body = await request.json()
        text = body.get("text", "")
        # Parse usernames from text
        usernames = []
        for line in text.replace(",", "\n").split("\n"):
            u = line.strip().strip("@").strip()
            if u and len(u) > 1:
                usernames.append(u)
        usernames = list(dict.fromkeys(usernames))[:50]  # Unique, max 50
        return _success({
            "usernames": usernames,
            "count": len(usernames),
        }, f"Parsed {len(usernames)} usernames", "batch/import")
    except Exception as e:
        return _error(str(e), endpoint="batch/import")


# ══════════════════════════════════════════════════════════
#  ROUTES — SESSION MANAGER
# ══════════════════════════════════════════════════════════

@app.get("/api/session/status")
async def session_status():
    """Get current session status."""
    try:
        ig = get_ig()
        logged_in = False
        username = None
        try:
            user = ig.account.current_user()
            logged_in = True
            username = user.get("username", "unknown") if isinstance(user, dict) else getattr(user, "username", "unknown")
        except Exception:
            pass
        return _success({
            "logged_in": logged_in,
            "username": username,
            "session_file": str(Path(__file__).parent / "instagram_session.json"),
            "session_exists": (Path(__file__).parent / "instagram_session.json").exists(),
            "uptime": round(time.time() - _start_time),
            "requests": _request_count,
            "errors": _error_count,
        }, "Session status", "session/status")
    except Exception as e:
        return _error(str(e), endpoint="session/status")


@app.post("/api/session/login")
async def session_login(request: Request):
    """Login with credentials."""
    try:
        body = await request.json()
        username = body.get("username", "").strip()
        password = body.get("password", "").strip()
        if not username or not password:
            return _error("Username and password required", 400, "session/login")
        global _ig
        _ig = Instagram()
        result = _ig.login(username, password)
        return _success({"logged_in": True, "username": username}, "Logged in", "session/login")
    except Exception as e:
        return _error(str(e), endpoint="session/login")


@app.post("/api/session/logout")
async def session_logout():
    """Logout current session."""
    try:
        global _ig
        if _ig:
            try:
                _ig.logout()
            except Exception:
                pass
        _ig = None
        return _success({"logged_in": False}, "Logged out", "session/logout")
    except Exception as e:
        return _error(str(e), endpoint="session/logout")


# ══════════════════════════════════════════════════════════
#  ROUTES — REAL-TIME ACTIVITY FEED (WebSocket)
# ══════════════════════════════════════════════════════════

_activity_log: List[Dict] = []


def _add_activity(action: str, detail: str, data: Any = None):
    entry = {
        "id": str(uuid.uuid4())[:8],
        "time": datetime.now().isoformat(),
        "action": action,
        "detail": detail,
        "data": data,
    }
    _activity_log.insert(0, entry)
    if len(_activity_log) > 100:
        _activity_log.pop()
    return entry


@app.get("/api/activity/feed")
async def activity_feed(limit: int = 20):
    """Get recent activity log."""
    return _success(_activity_log[:limit], f"{min(limit, len(_activity_log))} activities", "activity/feed")


@app.get("/api/activity/live")
async def activity_live():
    """Get live notifications (poll-based alternative to WebSocket)."""
    try:
        ig = get_ig()
        notifs = []
        try:
            raw = ig.notifications.get_notifications()
            if isinstance(raw, list):
                for n in raw[:10]:
                    notifs.append({
                        "type": n.get("type", "unknown") if isinstance(n, dict) else "notification",
                        "text": str(n.get("text", "")) if isinstance(n, dict) else str(n)[:100],
                        "time": n.get("timestamp", "") if isinstance(n, dict) else "",
                    })
        except Exception:
            pass
        return _success(notifs, f"{len(notifs)} notifications", "activity/live")
    except Exception as e:
        return _error(str(e), endpoint="activity/live")


# ══════════════════════════════════════════════════════════
#  ROUTES — COLLECTION MANAGER
# ══════════════════════════════════════════════════════════

COLLECTIONS_FILE = DEMO_DIR / "collections.json"


def _load_collections() -> Dict:
    if COLLECTIONS_FILE.exists():
        return json.loads(COLLECTIONS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_collections(data: Dict):
    COLLECTIONS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@app.get("/api/collections/list")
async def list_collections():
    cols = _load_collections()
    result = []
    for name, items in cols.items():
        result.append({"name": name, "count": len(items), "items": items})
    return _success(result, f"{len(result)} collections", "collections/list")


@app.post("/api/collections/create")
async def create_collection(request: Request):
    try:
        body = await request.json()
        name = body.get("name", "").strip()
        if not name:
            return _error("Collection name required", 400, "collections/create")
        cols = _load_collections()
        if name in cols:
            return _error("Collection already exists", 400, "collections/create")
        cols[name] = []
        _save_collections(cols)
        return _success({"name": name, "count": 0}, "Collection created", "collections/create")
    except Exception as e:
        return _error(str(e), endpoint="collections/create")


@app.post("/api/collections/{name}/add")
async def add_to_collection(name: str, request: Request):
    try:
        body = await request.json()
        username = body.get("username", "").strip()
        if not username:
            return _error("Username required", 400, "collections/add")
        cols = _load_collections()
        if name not in cols:
            return _error("Collection not found", 404, "collections/add")
        # Fetch profile data
        ig = get_ig()
        try:
            p = ig.public.get_profile(username)
            item = {
                "username": username,
                "full_name": _pval(p, "name", ""),
                "followers": _pval(p, "followers"),
                "is_verified": _pval(p, "verified", False),
                "added": datetime.now().isoformat(),
            }
        except Exception:
            item = {"username": username, "added": datetime.now().isoformat()}
        # Avoid duplicates
        if not any(i["username"] == username for i in cols[name]):
            cols[name].append(item)
            _save_collections(cols)
        return _success({"collection": name, "item": item, "total": len(cols[name])}, "Added to collection", "collections/add")
    except Exception as e:
        return _error(str(e), endpoint="collections/add")


@app.delete("/api/collections/{name}")
async def delete_collection(name: str):
    cols = _load_collections()
    if name in cols:
        del cols[name]
        _save_collections(cols)
        return _success({"deleted": name}, "Collection deleted", "collections/delete")
    return _error("Collection not found", 404, "collections/delete")


@app.delete("/api/collections/{name}/{username}")
async def remove_from_collection(name: str, username: str):
    cols = _load_collections()
    if name not in cols:
        return _error("Collection not found", 404, "collections/remove")
    cols[name] = [i for i in cols[name] if i.get("username") != username]
    _save_collections(cols)
    return _success({"removed": username, "remaining": len(cols[name])}, "Removed", "collections/remove")


# ══════════════════════════════════════════════════════════
#  ROUTES — EXPORT CENTER
# ══════════════════════════════════════════════════════════

@app.post("/api/export/json")
async def export_json(request: Request):
    """Export data as JSON."""
    try:
        body = await request.json()
        data = body.get("data", _last_result)
        filename = body.get("filename", f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        filepath = SAVED_DIR / filename
        filepath.write_text(json.dumps(_to_json(data), indent=2, ensure_ascii=False), encoding="utf-8")
        return _success({
            "file": str(filepath.absolute()),
            "size": filepath.stat().st_size,
            "format": "json",
        }, "Exported as JSON", "export/json")
    except Exception as e:
        return _error(str(e), endpoint="export/json")


@app.post("/api/export/csv")
async def export_csv_endpoint(request: Request):
    """Export data as CSV."""
    try:
        body = await request.json()
        data = body.get("data", _last_result)
        filename = body.get("filename", f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        filepath = SAVED_DIR / filename
        if isinstance(data, list) and data:
            keys = list(data[0].keys()) if isinstance(data[0], dict) else ["value"]
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for row in data:
                    if isinstance(row, dict):
                        writer.writerow({k: str(v) for k, v in row.items()})
                    else:
                        writer.writerow({"value": str(row)})
        else:
            filepath.write_text(str(data), encoding="utf-8")
        return _success({
            "file": str(filepath.absolute()),
            "size": filepath.stat().st_size,
            "format": "csv",
        }, "Exported as CSV", "export/csv")
    except Exception as e:
        return _error(str(e), endpoint="export/csv")


@app.post("/api/export/xlsx")
async def export_xlsx(request: Request):
    """Export data as Excel."""
    try:
        import openpyxl
        body = await request.json()
        data = body.get("data", _last_result)
        filename = body.get("filename", f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        filepath = SAVED_DIR / filename
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Export"
        if isinstance(data, list) and data and isinstance(data[0], dict):
            keys = list(data[0].keys())
            ws.append(keys)
            for row in data:
                ws.append([str(row.get(k, "")) for k in keys])
        elif isinstance(data, list):
            for row in data:
                ws.append([str(row)])
        wb.save(str(filepath))
        return _success({
            "file": str(filepath.absolute()),
            "size": filepath.stat().st_size,
            "format": "xlsx",
        }, "Exported as Excel", "export/xlsx")
    except ImportError:
        return _error("openpyxl not installed. Run: pip install openpyxl", 500, "export/xlsx")
    except Exception as e:
        return _error(str(e), endpoint="export/xlsx")


# ══════════════════════════════════════════════════════════
#  ROUTES — HASHTAG TRACKER
# ══════════════════════════════════════════════════════════

HASHTAG_DATA_FILE = DEMO_DIR / "hashtag_tracker.json"


def _load_hashtag_data() -> Dict:
    if HASHTAG_DATA_FILE.exists():
        return json.loads(HASHTAG_DATA_FILE.read_text(encoding="utf-8"))
    return {"tracked": {}}


def _save_hashtag_data(data: Dict):
    HASHTAG_DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@app.post("/api/hashtags/track")
async def track_hashtag(request: Request):
    """Start tracking a hashtag."""
    try:
        body = await request.json()
        tag = body.get("tag", "").strip().lstrip("#").lower()
        if not tag:
            return _error("Hashtag required", 400, "hashtags/track")
        data = _load_hashtag_data()
        ig = get_ig()
        # Get current hashtag info
        try:
            info = ig.public.get_hashtag_info(tag) if hasattr(ig.public, 'get_hashtag_info') else {}
        except Exception:
            info = {}
        snapshot = {
            "time": datetime.now().isoformat(),
            "media_count": info.get("media_count", 0) if isinstance(info, dict) else 0,
        }
        if tag not in data["tracked"]:
            data["tracked"][tag] = {"tag": tag, "snapshots": [], "created": datetime.now().isoformat()}
        data["tracked"][tag]["snapshots"].append(snapshot)
        _save_hashtag_data(data)
        return _success(data["tracked"][tag], f"Tracking #{tag}", "hashtags/track")
    except Exception as e:
        return _error(str(e), endpoint="hashtags/track")


@app.get("/api/hashtags/list")
async def list_tracked_hashtags():
    data = _load_hashtag_data()
    result = []
    for tag, info in data.get("tracked", {}).items():
        result.append({
            "tag": tag,
            "snapshots_count": len(info.get("snapshots", [])),
            "created": info.get("created", ""),
            "last_count": info["snapshots"][-1]["media_count"] if info.get("snapshots") else 0,
        })
    return _success(result, f"{len(result)} hashtags tracked", "hashtags/list")


@app.get("/api/hashtags/{tag}/top_posts")
async def hashtag_top_posts(tag: str):
    """Get top posts for a hashtag."""
    try:
        ig = get_ig()
        tag = tag.strip().lstrip("#").lower()
        posts = []
        try:
            feed = ig.search.top_search(tag)
            if isinstance(feed, dict):
                posts = feed.get("results", [])[:10]
        except Exception:
            pass
        return _success({
            "tag": tag,
            "posts": _to_json(posts),
            "count": len(posts),
        }, f"Top posts for #{tag}", "hashtags/top_posts")
    except Exception as e:
        return _error(str(e), endpoint="hashtags/top_posts")


@app.delete("/api/hashtags/{tag}")
async def untrack_hashtag(tag: str):
    data = _load_hashtag_data()
    tag = tag.strip().lstrip("#").lower()
    if tag in data.get("tracked", {}):
        del data["tracked"][tag]
        _save_hashtag_data(data)
        return _success({"untracked": tag}, f"Untracked #{tag}", "hashtags/untrack")
    return _error("Hashtag not found", 404, "hashtags/untrack")


# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    try:
        import uvicorn
    except ImportError:
        print("❌ uvicorn not found: pip install uvicorn")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="🧪 instaharvest_v2 Web Playground v2")
    parser.add_argument("--port", type=int, default=8877, help="Port (default: 8877)")
    parser.add_argument("--host", default="127.0.0.1", help="Host")
    parser.add_argument("--env", default=".env", help=".env file path")
    args = parser.parse_args()

    os.environ["instaharvest_v2_ENV"] = args.env

    # Load env for AI keys
    try:
        from dotenv import load_dotenv
        load_dotenv(args.env)
    except ImportError:
        pass

    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║   🧪  instaharvest_v2 Web Playground v2         ║")
    print(f"  ║   🌐  http://{args.host}:{args.port:<5d}              ║")
    print("  ║   🤖  AI Chat: Enabled                   ║")
    print("  ║   💾  Data Saving: Enabled                ║")
    print("  ║   Press Ctrl+C to stop                   ║")
    print("  ╚══════════════════════════════════════════╝")
    print()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

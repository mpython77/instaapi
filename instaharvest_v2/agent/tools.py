"""
Agent Tools — Built-in Tool Handlers
=====================================
Handlers for all 10 built-in agent tools.

Tools:
    1. run_instaharvest_v2_code  — Execute Python code in sandbox
    2. save_to_file       — Save content to a file
    3. ask_user           — Ask the user a question
    4. read_file          — Read file contents
    5. list_files         — List directory contents
    6. download_media     — Download Instagram media
    7. analyze_data       — Analyze data (stats, top_n, etc.)
    8. http_request       — Make HTTP requests
    9. create_chart       — Create charts/visualizations
   10. search_web         — Search the internet
"""

import csv
import glob
import io
import json
import logging
import os
import re
import statistics
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

logger = logging.getLogger("instaharvest_v2.agent.tools")


# ═══════════════════════════════════════════════════════════
# TOOL 4: read_file
# ═══════════════════════════════════════════════════════════

def handle_read_file(args: Dict) -> str:
    """Read file contents from current directory."""
    filename = args.get("filename", "")
    max_lines = min(args.get("max_lines", 100), 500)

    if not filename:
        return "Error: no filename provided"

    # Security: only relative paths
    if os.path.isabs(filename) or ".." in filename:
        return "Error: only relative paths allowed (no absolute paths or '..')"

    if not os.path.exists(filename):
        return f"Error: file not found: '{filename}'"

    try:
        ext = os.path.splitext(filename)[1].lower()
        file_size = os.path.getsize(filename)

        if file_size > 5 * 1024 * 1024:  # 5MB limit
            return f"Error: file too large ({file_size / 1024 / 1024:.1f}MB). Max: 5MB"

        with open(filename, "r", encoding="utf-8", errors="replace") as f:
            if ext == ".json":
                data = json.load(f)
                content = json.dumps(data, indent=2, ensure_ascii=False)
                lines = content.split("\n")
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                    lines.append(f"... (truncated, {len(content)} chars total)")
                return "\n".join(lines)

            elif ext in (".csv", ".tsv"):
                delimiter = "\t" if ext == ".tsv" else ","
                reader = csv.reader(f, delimiter=delimiter)
                rows = []
                for i, row in enumerate(reader):
                    if i >= max_lines:
                        rows.append(f"... (truncated at {max_lines} rows)")
                        break
                    rows.append(delimiter.join(row))
                return "\n".join(rows)

            else:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"... (truncated at {max_lines} lines)")
                        break
                    lines.append(line.rstrip())
                return "\n".join(lines)

    except Exception as e:
        return f"Error reading file: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 5: list_files
# ═══════════════════════════════════════════════════════════

def handle_list_files(args: Dict) -> str:
    """List files in directory."""
    directory = args.get("directory", ".")
    pattern = args.get("pattern", "*")

    # Security
    if os.path.isabs(directory) or ".." in directory:
        return "Error: only relative paths allowed"

    if not os.path.isdir(directory):
        return f"Error: directory not found: '{directory}'"

    try:
        search_path = os.path.join(directory, pattern)
        entries = glob.glob(search_path)

        if not entries:
            return f"No files matching '{pattern}' in '{directory}'"

        lines = [f"Files in '{directory}' (pattern: {pattern}):"]
        lines.append("-" * 50)

        dirs = []
        files = []

        for entry in sorted(entries):
            if os.path.isdir(entry):
                child_count = len(os.listdir(entry))
                dirs.append(f"  📁 {os.path.basename(entry)}/  ({child_count} items)")
            else:
                size = os.path.getsize(entry)
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f}KB"
                else:
                    size_str = f"{size / 1024 / 1024:.1f}MB"
                files.append(f"  📄 {os.path.basename(entry)}  ({size_str})")

        lines.extend(dirs)
        lines.extend(files)
        lines.append(f"\nTotal: {len(dirs)} dirs, {len(files)} files")

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing files: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 6: download_media
# ═══════════════════════════════════════════════════════════

def handle_download_media(args: Dict, ig=None) -> str:
    """Download Instagram media using instaharvest_v2."""
    url = args.get("url", "")
    output_dir = args.get("output_dir", "downloads")
    media_type = args.get("media_type", "post")

    if not url:
        return "Error: no URL or username provided"

    if ig is None:
        return "Error: Instagram client required. Cannot download in anonymous mode."

    # Security: relative paths only
    if os.path.isabs(output_dir) or ".." in output_dir:
        return "Error: only relative output directories allowed"

    os.makedirs(output_dir, exist_ok=True)
    full_output_path = os.path.abspath(output_dir)

    try:
        # ─── URL-based download ───
        if url.startswith("http"):
            if hasattr(ig, "download") and hasattr(ig.download, "download_by_url"):
                try:
                    files = ig.download.download_by_url(url, folder=output_dir)
                    if files:
                        return (
                            f"✅ Downloaded {len(files)} file(s)\n"
                            f"Path: {full_output_path}\n"
                            f"Files: {', '.join(os.path.basename(f) for f in files)}"
                        )
                except Exception as e:
                    logger.warning(f"download_by_url failed: {e}")

            # Fallback: extract shortcode manually
            shortcode_match = re.search(r"/(?:p|reel|tv)/([A-Za-z0-9_-]+)", url)
            if shortcode_match and hasattr(ig, "download"):
                shortcode = shortcode_match.group(1)
                try:
                    media_info = ig.media.get_by_shortcode(shortcode)
                    media_pk = media_info.get("pk") if isinstance(media_info, dict) else getattr(media_info, "pk", None)
                    if media_pk:
                        files = ig.download.download_media(media_pk, folder=output_dir)
                        return (
                            f"✅ Downloaded media (shortcode: {shortcode})\n"
                            f"Path: {full_output_path}\n"
                            f"Files: {len(files) if isinstance(files, list) else 1}"
                        )
                except Exception as e:
                    return f"Error downloading from URL: {e}"

            return f"Error: could not extract media from URL: {url}"

        # ─── Username-based download ───
        username = url.lstrip("@")

        if media_type == "profile_pic":
            if hasattr(ig, "download") and hasattr(ig.download, "download_profile_pic"):
                filepath = ig.download.download_profile_pic(
                    username=username, folder=output_dir
                )
                return (
                    f"✅ Profile pic of @{username} downloaded\n"
                    f"Path: {os.path.abspath(filepath)}"
                )
            return "Error: download_profile_pic not available"

        elif media_type == "stories":
            if hasattr(ig, "download") and hasattr(ig.download, "download_stories"):
                # Need user_pk for stories
                user_data = ig.users.get_by_username(username)
                user_pk = user_data.get("pk") if isinstance(user_data, dict) else getattr(user_data, "pk", None)
                if user_pk:
                    files = ig.download.download_stories(user_pk, folder=output_dir)
                    return (
                        f"✅ Stories of @{username} downloaded\n"
                        f"Path: {full_output_path}\n"
                        f"Files: {len(files) if isinstance(files, list) else '?'}"
                    )
            return "Error: stories download not available"

        elif media_type == "reels" or media_type == "all":
            if hasattr(ig, "bulk_download") and hasattr(ig.bulk_download, "everything"):
                result = ig.bulk_download.everything(username, output_dir)
                return (
                    f"✅ All media of @{username} downloaded\n"
                    f"Path: {full_output_path}\n"
                    f"Result: {json.dumps(result, default=str)[:300]}"
                )
            return "Error: bulk_download not available"

        else:
            # Default: download posts using bulk_download (accepts username)
            if hasattr(ig, "bulk_download") and hasattr(ig.bulk_download, "all_posts"):
                max_count = 10
                result = ig.bulk_download.all_posts(
                    username, output_dir, max_count=max_count
                )
                return (
                    f"✅ Posts of @{username} downloaded\n"
                    f"Path: {full_output_path}\n"
                    f"Result: {json.dumps(result, default=str)[:300]}"
                )

            # Fallback: download_user_posts (needs user_pk)
            if hasattr(ig, "download") and hasattr(ig.download, "download_user_posts"):
                user_data = ig.users.get_by_username(username)
                user_pk = user_data.get("pk") if isinstance(user_data, dict) else getattr(user_data, "pk", None)
                if user_pk:
                    files = ig.download.download_user_posts(
                        user_pk, folder=output_dir, max_posts=10
                    )
                    return (
                        f"✅ {len(files)} posts of @{username} downloaded\n"
                        f"Path: {full_output_path}\n"
                        f"Files: {', '.join(os.path.basename(f) for f in files[:5])}"
                    )
            return "Error: post download not available"

    except Exception as e:
        return f"Error downloading media: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 7: analyze_data
# ═══════════════════════════════════════════════════════════

def handle_analyze_data(args: Dict) -> str:
    """Analyze data from file or raw input."""
    source = args.get("source", "")
    analysis_type = args.get("analysis_type", "summary")
    field = args.get("field", None)
    top_n = args.get("top_n", 10)

    if not source:
        return "Error: no data source provided"

    # Load data
    data = _load_data(source)
    if isinstance(data, str):
        return data  # Error message

    if not data:
        return "Error: no data to analyze"

    try:
        if analysis_type == "summary":
            return _analyze_summary(data, field)
        elif analysis_type == "top_n":
            return _analyze_top_n(data, field, top_n)
        elif analysis_type == "distribution":
            return _analyze_distribution(data, field)
        elif analysis_type == "compare":
            return _analyze_compare(data, field)
        elif analysis_type == "trend":
            return _analyze_trend(data, field)
        else:
            return f"Error: unknown analysis type '{analysis_type}'. Use: summary, top_n, distribution, compare, trend"

    except Exception as e:
        return f"Error analyzing data: {e}"


def _load_data(source: str) -> Any:
    """Load data from file path or raw JSON string."""
    # Try as file first
    if os.path.exists(source):
        ext = os.path.splitext(source)[1].lower()
        try:
            if ext == ".json":
                with open(source, "r", encoding="utf-8") as f:
                    return json.load(f)
            elif ext == ".jsonl":
                with open(source, "r", encoding="utf-8") as f:
                    return [json.loads(line) for line in f if line.strip()]
            elif ext in (".csv", ".tsv"):
                delimiter = "\t" if ext == ".tsv" else ","
                with open(source, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f, delimiter=delimiter)
                    return list(reader)
            else:
                with open(source, "r", encoding="utf-8") as f:
                    return [{"line": line.strip()} for line in f if line.strip()]
        except Exception as e:
            return f"Error loading '{source}': {e}"

    # Try as raw JSON
    try:
        return json.loads(source)
    except (json.JSONDecodeError, TypeError):
        return f"Error: '{source}' is not a valid file path or JSON data"


def _analyze_summary(data, field=None):
    """Generate summary statistics."""
    if isinstance(data, list) and data:
        lines = [f"📊 Data Summary ({len(data)} records)"]
        lines.append("-" * 40)

        if isinstance(data[0], dict):
            keys = list(data[0].keys())
            lines.append(f"Fields: {', '.join(keys[:15])}")

            # Numeric fields stats
            for key in keys[:10]:
                values = [_to_num(item.get(key)) for item in data if _to_num(item.get(key)) is not None]
                if values and len(values) >= 2:
                    lines.append(f"\n  {key}:")
                    lines.append(f"    Count: {len(values)}")
                    lines.append(f"    Min: {min(values):,.2f}")
                    lines.append(f"    Max: {max(values):,.2f}")
                    lines.append(f"    Avg: {statistics.mean(values):,.2f}")
                    lines.append(f"    Median: {statistics.median(values):,.2f}")

        return "\n".join(lines)

    return f"Data: {type(data).__name__} with {len(data) if hasattr(data, '__len__') else '?'} items"


def _analyze_top_n(data, field, n=10):
    """Get top N items by a field."""
    if not field or not isinstance(data, list):
        return "Error: 'field' required for top_n analysis"

    try:
        sorted_data = sorted(
            [d for d in data if _to_num(d.get(field)) is not None],
            key=lambda x: _to_num(x.get(field, 0)),
            reverse=True
        )

        lines = [f"🏆 Top {n} by '{field}':"]
        lines.append("-" * 40)

        for i, item in enumerate(sorted_data[:n], 1):
            name = item.get("username") or item.get("name") or item.get("id") or f"#{i}"
            value = item.get(field)
            lines.append(f"  {i}. {name}: {value:,}" if isinstance(value, (int, float)) else f"  {i}. {name}: {value}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error in top_n analysis: {e}"


def _analyze_distribution(data, field):
    """Analyze value distribution."""
    if not field or not isinstance(data, list):
        return "Error: 'field' required for distribution analysis"

    values = [item.get(field) for item in data if item.get(field) is not None]
    if not values:
        return f"Error: no values found for field '{field}'"

    numeric = [_to_num(v) for v in values if _to_num(v) is not None]

    if numeric:
        lines = [f"📈 Distribution of '{field}' ({len(numeric)} values):"]
        lines.append("-" * 40)

        # Ranges
        min_v, max_v = min(numeric), max(numeric)
        range_size = (max_v - min_v) / 5 if max_v != min_v else 1
        buckets = {}
        for v in numeric:
            bucket = int((v - min_v) / range_size) if range_size else 0
            bucket = min(bucket, 4)
            low = min_v + bucket * range_size
            high = low + range_size
            key = f"{low:,.0f}-{high:,.0f}"
            buckets[key] = buckets.get(key, 0) + 1

        for key, count in sorted(buckets.items()):
            bar = "█" * min(count, 40)
            lines.append(f"  {key:>20s}: {bar} ({count})")

        return "\n".join(lines)

    # Categorical distribution
    from collections import Counter
    counter = Counter(values)
    lines = [f"📊 Distribution of '{field}' ({len(values)} values):"]
    for value, count in counter.most_common(20):
        bar = "█" * min(count, 30)
        lines.append(f"  {str(value):>20s}: {bar} ({count})")

    return "\n".join(lines)


def _analyze_compare(data, field):
    """Compare items."""
    if not isinstance(data, list) or len(data) < 2:
        return "Error: need at least 2 items to compare"

    lines = [f"⚖️ Comparison ({len(data)} items):"]
    lines.append("-" * 50)

    keys = list(data[0].keys()) if isinstance(data[0], dict) else []
    for item in data:
        name = item.get("username") or item.get("name") or "?"
        lines.append(f"\n  {name}:")
        for key in keys[:8]:
            val = item.get(key, "—")
            if isinstance(val, (int, float)):
                val = f"{val:,}"
            lines.append(f"    {key}: {val}")

    return "\n".join(lines)


def _analyze_trend(data, field):
    """Analyze trend over time."""
    if not field or not isinstance(data, list):
        return "Error: 'field' required for trend analysis"

    values = [_to_num(item.get(field)) for item in data if _to_num(item.get(field)) is not None]
    if len(values) < 3:
        return "Error: need at least 3 data points for trend analysis"

    lines = [f"📈 Trend of '{field}' ({len(values)} points):"]
    lines.append("-" * 40)

    first_half = values[:len(values) // 2]
    second_half = values[len(values) // 2:]

    avg_first = statistics.mean(first_half)
    avg_second = statistics.mean(second_half)
    change = ((avg_second - avg_first) / avg_first * 100) if avg_first else 0

    arrow = "📈" if change > 0 else "📉" if change < 0 else "➡️"
    lines.append(f"  First half avg:  {avg_first:,.2f}")
    lines.append(f"  Second half avg: {avg_second:,.2f}")
    lines.append(f"  Change: {arrow} {change:+.1f}%")

    return "\n".join(lines)


def _to_num(val):
    """Convert value to number if possible."""
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        try:
            return float(val.replace(",", ""))
        except (ValueError, AttributeError):
            return None
    return None


# ═══════════════════════════════════════════════════════════
# TOOL 8: http_request
# ═══════════════════════════════════════════════════════════

def handle_http_request(args: Dict) -> str:
    """Make HTTP request."""
    method = args.get("method", "GET").upper()
    url = args.get("url", "")
    headers = args.get("headers", {})
    body = args.get("body", "")

    if not url:
        return "Error: no URL provided"

    if method not in ("GET", "POST"):
        return f"Error: unsupported method '{method}'. Use GET or POST"

    # Security: block localhost and internal IPs
    blocked = ["localhost", "127.0.0.1", "0.0.0.0", "169.254.", "10.", "192.168.", "172.16."]
    for pattern in blocked:
        if pattern in url.lower():
            return f"Error: requests to internal/local addresses are blocked"

    try:
        req = urllib.request.Request(url, method=method)

        # Set headers
        req.add_header("User-Agent", "InstaHarvest v2-Agent/1.0")
        for key, val in headers.items():
            req.add_header(key, val)

        # Set body for POST
        data = body.encode("utf-8") if body and method == "POST" else None

        with urllib.request.urlopen(req, data=data, timeout=15) as resp:
            response_body = resp.read().decode("utf-8", errors="replace")
            status = resp.status

            # Truncate large responses
            if len(response_body) > 5000:
                response_body = response_body[:5000] + "\n... (truncated)"

            return f"HTTP {status}\n{response_body}"

    except urllib.error.HTTPError as e:
        return f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"URL Error: {e.reason}"
    except Exception as e:
        return f"Request error: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 9: create_chart
# ═══════════════════════════════════════════════════════════

def handle_create_chart(args: Dict) -> str:
    """Create chart using ASCII (no matplotlib dependency)."""
    chart_type = args.get("chart_type", "bar")
    title = args.get("title", "Chart")
    labels = args.get("labels", [])
    values = args.get("values", [])
    filename = args.get("filename", "chart.txt")

    if not labels or not values:
        return "Error: 'labels' and 'values' are required"

    if len(labels) != len(values):
        return f"Error: labels ({len(labels)}) and values ({len(values)}) must have equal length"

    try:
        # Generate ASCII chart
        max_val = max(values) if values else 1
        max_label_len = max(len(str(l)) for l in labels)

        lines = [f"  {title}", "  " + "=" * (max_label_len + 45)]

        if chart_type in ("bar", "horizontal_bar"):
            for label, val in zip(labels, values):
                bar_len = int((val / max_val) * 35) if max_val else 0
                bar = "█" * bar_len
                lines.append(f"  {str(label):>{max_label_len}s} │{bar} {val:,.0f}")

        elif chart_type == "line":
            lines.append("")
            # Simple sparkline
            for i, (label, val) in enumerate(zip(labels, values)):
                height = int((val / max_val) * 10) if max_val else 0
                marker = "─" * height + "●"
                lines.append(f"  {str(label):>{max_label_len}s} │{marker} {val:,.0f}")

        elif chart_type == "pie":
            total = sum(values)
            for label, val in sorted(zip(labels, values), key=lambda x: -x[1]):
                pct = (val / total * 100) if total else 0
                blocks = int(pct / 3)
                lines.append(f"  {str(label):>{max_label_len}s} │{'█' * blocks} {pct:.1f}% ({val:,.0f})")

        lines.append("  " + "=" * (max_label_len + 45))

        chart_text = "\n".join(lines)

        # Save to file
        if os.path.isabs(filename) or ".." in filename:
            return "Error: only relative file paths allowed"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(chart_text)

        return f"✅ Chart saved to '{filename}':\n\n{chart_text}"

    except Exception as e:
        return f"Error creating chart: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 10: search_web
# ═══════════════════════════════════════════════════════════

def handle_search_web(args: Dict) -> str:
    """Search the web using DuckDuckGo Lite."""
    query = args.get("query", "")

    if not query:
        return "Error: no search query provided"

    try:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"

        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) InstaHarvest v2-Agent/1.0")

        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Extract text snippets from HTML
        results = _extract_search_results(html)

        if not results:
            return f"No results found for: '{query}'"

        lines = [f"🔍 Search results for: '{query}'"]
        lines.append("-" * 50)

        for i, result in enumerate(results[:5], 1):
            lines.append(f"\n  {i}. {result['title']}")
            if result.get("snippet"):
                lines.append(f"     {result['snippet'][:200]}")
            if result.get("url"):
                lines.append(f"     → {result['url']}")

        return "\n".join(lines)

    except Exception as e:
        return f"Search error: {e}"


def _extract_search_results(html: str) -> list:
    """Extract search results from DuckDuckGo Lite HTML."""
    import urllib.parse
    results = []

    # Find result links and snippets
    title_pattern = re.compile(r'<a[^>]*class="result-link"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
    snippet_pattern = re.compile(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', re.DOTALL)

    titles = title_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    # Fallback: simpler patterns
    if not titles:
        titles = re.findall(r'<a[^>]*rel="nofollow"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)

    if not snippets:
        snippets = re.findall(r'<td[^>]*class="(?:result-snippet|snippet)"[^>]*>(.*?)</td>', html, re.DOTALL)

    for i, (url, title) in enumerate(titles[:10]):
        # Clean HTML tags
        clean_title = re.sub(r'<[^>]+>', '', title).strip()
        clean_snippet = ""
        if i < len(snippets):
            clean_snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()

        if clean_title:
            results.append({
                "title": clean_title,
                "url": url,
                "snippet": clean_snippet,
            })

    return results

# ═══════════════════════════════════════════════════════════
# TOOL 11: get_profile — Specialized Instagram Profile Tool
# ═══════════════════════════════════════════════════════════

def handle_get_profile(args: Dict, ig=None, cache=None) -> str:
    """Get Instagram profile info — direct API call, no code needed."""
    username = args.get("username", "").strip().lstrip("@").lower()

    if not username:
        return "Error: username is required. Example: get_profile(username='cristiano')"

    if ig is None:
        return "Error: Instagram client not available."

    # Check cache first
    if cache and username in cache:
        cached = cache[username]
        if isinstance(cached, dict):
            lines = [
                f"(From cache) Profile: @{username}",
                f"Username: {cached.get('username', username)}",
                f"Full Name: {cached.get('full_name', 'N/A')}",
                f"Followers: {cached.get('followers', 0):,}",
                f"Following: {cached.get('following', 0):,}",
                f"Posts: {cached.get('posts_count', 0):,}",
                f"Bio: {cached.get('biography', 'N/A')}",
                f"Verified: {'Yes' if cached.get('is_verified') else 'No'}",
                f"Private: {'Yes' if cached.get('is_private') else 'No'}",
            ]
            pic = cached.get("profile_pic_url") or cached.get("profile_pic_url_hd")
            if pic:
                lines.append(f"Profile Pic: {pic}")
            return "\n".join(lines)

    try:
        profile = ig.public.get_profile(username)
        if not profile:
            return f"Profile not found: '@{username}'. Check the username spelling."

        # Build formatted output
        lines = [
            f"Profile: @{profile.get('username', username)}",
            f"Full Name: {profile.get('full_name', 'N/A')}",
            f"Followers: {profile.get('followers', 0):,}",
            f"Following: {profile.get('following', 0):,}",
            f"Posts: {profile.get('posts_count', 0):,}",
            f"Bio: {profile.get('biography', 'N/A')}",
            f"Verified: {'Yes' if profile.get('is_verified') else 'No'}",
            f"Private: {'Yes' if profile.get('is_private') else 'No'}",
        ]

        # Add optional fields
        pic = profile.get("profile_pic_url") or profile.get("profile_pic_url_hd")
        if pic:
            lines.append(f"Profile Pic: {pic}")

        ext_url = profile.get("external_url")
        if ext_url:
            lines.append(f"Website: {ext_url}")

        category = profile.get("category_name") or profile.get("category")
        if category:
            lines.append(f"Category: {category}")

        # Cache for future use
        if cache is not None:
            cache[username] = profile

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching profile '@{username}': {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 12: get_posts — Specialized Instagram Posts Tool
# ═══════════════════════════════════════════════════════════

def handle_get_posts(args: Dict, ig=None, cache=None) -> str:
    """Get user's recent Instagram posts — direct API call."""
    username = args.get("username", "").strip().lstrip("@").lower()
    max_count = min(args.get("max_count", 12), 50)

    if not username:
        return "Error: username is required."

    if ig is None:
        return "Error: Instagram client not available."

    try:
        posts = ig.public.get_posts(username)
        if not posts:
            return f"No posts found for '@{username}' or profile is private."

        # Limit to max_count
        posts = posts[:max_count] if isinstance(posts, list) else [posts]

        lines = [f"Recent posts from @{username} ({len(posts)} posts):"]
        lines.append("-" * 50)

        for i, post in enumerate(posts, 1):
            if isinstance(post, dict):
                shortcode = post.get("shortcode", "?")
                likes = post.get("like_count", post.get("likes", 0))
                comments = post.get("comment_count", post.get("comments", 0))
                caption = post.get("caption", "") or ""
                timestamp = post.get("taken_at", post.get("timestamp", ""))
                media_type = post.get("media_type", post.get("type", "photo"))

                # Truncate caption
                if len(caption) > 100:
                    caption = caption[:100] + "..."

                lines.append(f"\n  {i}. [{media_type}] https://instagram.com/p/{shortcode}/")
                if likes:
                    lines.append(f"     Likes: {likes:,}")
                if comments:
                    lines.append(f"     Comments: {comments:,}")
                if caption:
                    lines.append(f"     Caption: {caption}")
                if timestamp:
                    lines.append(f"     Date: {timestamp}")
            else:
                lines.append(f"\n  {i}. {str(post)[:200]}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching posts for '@{username}': {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 13: search_users — Specialized Instagram Search Tool
# ═══════════════════════════════════════════════════════════

def handle_search_users(args: Dict, ig=None) -> str:
    """Search Instagram for users — direct API call."""
    query = args.get("query", "").strip()

    if not query:
        return "Error: search query is required."

    if ig is None:
        return "Error: Instagram client not available."

    try:
        # Try public search first
        if hasattr(ig, "public") and hasattr(ig.public, "search"):
            results = ig.public.search(query)
        elif hasattr(ig, "users") and hasattr(ig.users, "search"):
            results = ig.users.search(query)
        else:
            return "Error: search is not available in current mode."

        if not results:
            return f"No users found for query: '{query}'"

        items = results if isinstance(results, list) else [results]
        lines = [f"Search results for '{query}' ({len(items)} found):"]
        lines.append("-" * 50)

        for i, user in enumerate(items[:10], 1):
            if isinstance(user, dict):
                uname = user.get("username", "?")
                fname = user.get("full_name", "")
                followers = user.get("followers", user.get("follower_count", "?"))
                verified = " ✅" if user.get("is_verified") else ""
                private = " 🔒" if user.get("is_private") else ""

                lines.append(f"\n  {i}. @{uname}{verified}{private}")
                if fname:
                    lines.append(f"     Name: {fname}")
                if isinstance(followers, int):
                    lines.append(f"     Followers: {followers:,}")
            else:
                lines.append(f"\n  {i}. {str(user)[:200]}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error searching for '{query}': {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 14: get_user_info — Detailed User Info Tool
# ═══════════════════════════════════════════════════════════

def handle_get_user_info(args: Dict, ig=None, is_logged_in=False, cache=None) -> str:
    """Get detailed user info — uses login API if available, fallback to public."""
    username = args.get("username", "").strip().lstrip("@").lower()

    if not username:
        return "Error: username is required."

    if ig is None:
        return "Error: Instagram client not available."

    # Try login API first (more detailed data)
    if is_logged_in and hasattr(ig, "users") and hasattr(ig.users, "get_by_username"):
        try:
            user = ig.users.get_by_username(username)
            if user:
                # Handle both dict and object responses
                if isinstance(user, dict):
                    data = user
                else:
                    data = {
                        "username": getattr(user, "username", username),
                        "full_name": getattr(user, "full_name", "N/A"),
                        "followers": getattr(user, "followers", 0),
                        "following": getattr(user, "following", 0),
                        "posts_count": getattr(user, "posts_count", 0),
                        "biography": getattr(user, "biography", ""),
                        "is_verified": getattr(user, "is_verified", False),
                        "is_private": getattr(user, "is_private", False),
                        "is_business": getattr(user, "is_business_account", False),
                        "category": getattr(user, "category_name", ""),
                        "external_url": getattr(user, "external_url", ""),
                        "profile_pic_url": getattr(user, "profile_pic_url", ""),
                    }

                lines = [
                    f"Detailed Profile: @{data.get('username', username)}",
                    f"Full Name: {data.get('full_name', 'N/A')}",
                    f"Followers: {data.get('followers', 0):,}",
                    f"Following: {data.get('following', 0):,}",
                    f"Posts: {data.get('posts_count', 0):,}",
                    f"Bio: {data.get('biography', 'N/A')}",
                    f"Verified: {'Yes' if data.get('is_verified') else 'No'}",
                    f"Private: {'Yes' if data.get('is_private') else 'No'}",
                    f"Business: {'Yes' if data.get('is_business') else 'No'}",
                ]

                if data.get("category"):
                    lines.append(f"Category: {data['category']}")
                if data.get("external_url"):
                    lines.append(f"Website: {data['external_url']}")
                if data.get("profile_pic_url"):
                    lines.append(f"Profile Pic: {data['profile_pic_url']}")

                # Cache
                if cache is not None:
                    cache[username] = data

                return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Login API failed for '{username}': {e}, falling back to public")

    # Fallback to public API
    return handle_get_profile(args, ig=ig, cache=cache)

# ═══════════════════════════════════════════════════════════
# TOOL 15: follow_user — Follow/Unfollow
# ═══════════════════════════════════════════════════════════

def handle_follow_user(args: Dict, ig=None, is_logged_in=False) -> str:
    """Follow or unfollow a user."""
    username = args.get("username", "").strip().lstrip("@").lower()
    action = args.get("action", "follow").lower()

    if not username:
        return "Error: username is required."
    if not is_logged_in:
        return "Error: follow/unfollow requires login. You are in anonymous mode."
    if ig is None:
        return "Error: Instagram client not available."

    try:
        # Get user PK first
        user = ig.users.get_by_username(username)
        if not user:
            return f"User '@{username}' not found."

        user_pk = user.get("pk") if isinstance(user, dict) else getattr(user, "pk", None)
        if not user_pk:
            return f"Could not get user ID for '@{username}'."

        if action == "follow":
            ig.friendships.follow(user_pk)
            return f"✅ Successfully followed @{username}"
        elif action == "unfollow":
            ig.friendships.unfollow(user_pk)
            return f"✅ Successfully unfollowed @{username}"
        else:
            return f"Error: unknown action '{action}'. Use 'follow' or 'unfollow'."

    except Exception as e:
        return f"Error {action}ing @{username}: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 16: get_followers — Followers list
# ═══════════════════════════════════════════════════════════

def handle_get_followers(args: Dict, ig=None, is_logged_in=False) -> str:
    """Get followers list for a user."""
    username = args.get("username", "").strip().lstrip("@").lower()
    max_count = min(args.get("max_count", 50), 1000)

    if not username:
        return "Error: username is required."
    if not is_logged_in:
        return "Error: followers list requires login. You are in anonymous mode."
    if ig is None:
        return "Error: Instagram client not available."

    try:
        user = ig.users.get_by_username(username)
        if not user:
            return f"User '@{username}' not found."

        user_pk = user.get("pk") if isinstance(user, dict) else getattr(user, "pk", None)
        if not user_pk:
            return f"Could not get user ID for '@{username}'."

        followers = ig.friendships.get_all_followers(user_pk, max_count=max_count)
        if not followers:
            return f"No followers found for '@{username}' (may be private)."

        lines = [f"Followers of @{username} ({len(followers)} shown):"]
        lines.append("-" * 50)

        for i, f in enumerate(followers[:max_count], 1):
            if isinstance(f, dict):
                fname = f.get("full_name", "")
                uname = f.get("username", "?")
                verified = " ✅" if f.get("is_verified") else ""
                lines.append(f"  {i}. @{uname}{verified}" + (f" ({fname})" if fname else ""))
            else:
                uname = getattr(f, "username", str(f))
                lines.append(f"  {i}. @{uname}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting followers for '@{username}': {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 17: get_following — Following list
# ═══════════════════════════════════════════════════════════

def handle_get_following(args: Dict, ig=None, is_logged_in=False) -> str:
    """Get following list for a user."""
    username = args.get("username", "").strip().lstrip("@").lower()
    max_count = min(args.get("max_count", 50), 1000)

    if not username:
        return "Error: username is required."
    if not is_logged_in:
        return "Error: following list requires login. You are in anonymous mode."
    if ig is None:
        return "Error: Instagram client not available."

    try:
        user = ig.users.get_by_username(username)
        if not user:
            return f"User '@{username}' not found."

        user_pk = user.get("pk") if isinstance(user, dict) else getattr(user, "pk", None)
        if not user_pk:
            return f"Could not get user ID for '@{username}'."

        following = ig.friendships.get_all_following(user_pk, max_count=max_count)
        if not following:
            return f"No following found for '@{username}' (may be private)."

        lines = [f"Following of @{username} ({len(following)} shown):"]
        lines.append("-" * 50)

        for i, f in enumerate(following[:max_count], 1):
            if isinstance(f, dict):
                fname = f.get("full_name", "")
                uname = f.get("username", "?")
                verified = " ✅" if f.get("is_verified") else ""
                lines.append(f"  {i}. @{uname}{verified}" + (f" ({fname})" if fname else ""))
            else:
                uname = getattr(f, "username", str(f))
                lines.append(f"  {i}. @{uname}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting following for '@{username}': {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 18: get_friendship_status — Relationship check
# ═══════════════════════════════════════════════════════════

def handle_get_friendship_status(args: Dict, ig=None, is_logged_in=False) -> str:
    """Check friendship status between me and another user."""
    username = args.get("username", "").strip().lstrip("@").lower()

    if not username:
        return "Error: username is required."
    if not is_logged_in:
        return "Error: friendship status requires login."
    if ig is None:
        return "Error: Instagram client not available."

    try:
        user = ig.users.get_by_username(username)
        if not user:
            return f"User '@{username}' not found."

        user_pk = user.get("pk") if isinstance(user, dict) else getattr(user, "pk", None)
        if not user_pk:
            return f"Could not get user ID for '@{username}'."

        status = ig.friendships.show(user_pk)
        if not status:
            return f"Could not get friendship status for '@{username}'."

        if isinstance(status, dict):
            lines = [
                f"Friendship status with @{username}:",
                f"  I follow them: {'Yes' if status.get('following') else 'No'}",
                f"  They follow me: {'Yes' if status.get('followed_by') else 'No'}",
                f"  Blocked: {'Yes' if status.get('blocking') else 'No'}",
                f"  Muted: {'Yes' if status.get('muting') else 'No'}",
                f"  Restricted: {'Yes' if status.get('is_restricted') else 'No'}",
            ]
            if status.get("outgoing_request"):
                lines.append("  Pending follow request: Yes")
            return "\n".join(lines)

        return f"Friendship with @{username}: {status}"

    except Exception as e:
        return f"Error checking friendship with '@{username}': {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 19: like_media — Like/Unlike post
# ═══════════════════════════════════════════════════════════

def _resolve_media_id(media_id_or_url: str, ig) -> str:
    """Resolve Instagram URL to media PK if needed."""
    if media_id_or_url.startswith("http"):
        shortcode_match = re.search(r"/(?:p|reel|tv)/([A-Za-z0-9_-]+)", media_id_or_url)
        if shortcode_match and hasattr(ig, "media"):
            shortcode = shortcode_match.group(1)
            try:
                info = ig.media.get_by_shortcode(shortcode) if hasattr(ig.media, "get_by_shortcode") else None
                if info:
                    return str(info.get("pk", info.get("id", shortcode)))
            except Exception:
                pass
            # Fallback: use shortcode_to_media_id
            if hasattr(ig.media, "_shortcode_to_media_id"):
                return str(ig.media._shortcode_to_media_id(shortcode))
        return media_id_or_url
    return media_id_or_url


def handle_like_media(args: Dict, ig=None, is_logged_in=False) -> str:
    """Like or unlike a post."""
    media_id = args.get("media_id", "").strip()
    action = args.get("action", "like").lower()

    if not media_id:
        return "Error: media_id or URL is required."
    if not is_logged_in:
        return "Error: like/unlike requires login."
    if ig is None:
        return "Error: Instagram client not available."

    try:
        resolved_id = _resolve_media_id(media_id, ig)

        if action == "like":
            ig.media.like(resolved_id)
            return f"✅ Liked post (ID: {resolved_id})"
        elif action == "unlike":
            ig.media.unlike(resolved_id)
            return f"✅ Unliked post (ID: {resolved_id})"
        else:
            return f"Error: unknown action '{action}'. Use 'like' or 'unlike'."

    except Exception as e:
        return f"Error {action}ing post: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 20: comment_media — Add comment
# ═══════════════════════════════════════════════════════════

def handle_comment_media(args: Dict, ig=None, is_logged_in=False) -> str:
    """Add comment to a post."""
    media_id = args.get("media_id", "").strip()
    text = args.get("text", "").strip()

    if not media_id:
        return "Error: media_id or URL is required."
    if not text:
        return "Error: comment text is required."
    if not is_logged_in:
        return "Error: commenting requires login."
    if ig is None:
        return "Error: Instagram client not available."

    try:
        resolved_id = _resolve_media_id(media_id, ig)
        result = ig.media.comment(resolved_id, text)
        return f"✅ Comment posted: '{text}' (on post {resolved_id})"
    except Exception as e:
        return f"Error commenting: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 21: get_media_info — Full post info
# ═══════════════════════════════════════════════════════════

def handle_get_media_info(args: Dict, ig=None) -> str:
    """Get full information about a post."""
    media_id = args.get("media_id", "").strip()

    if not media_id:
        return "Error: media_id or URL is required."
    if ig is None:
        return "Error: Instagram client not available."

    try:
        # Try URL-based lookup first
        if media_id.startswith("http"):
            if hasattr(ig, "media") and hasattr(ig.media, "get_by_url_v2"):
                info = ig.media.get_by_url_v2(media_id)
            elif hasattr(ig, "public") and hasattr(ig.public, "get_post_by_url"):
                info = ig.public.get_post_by_url(media_id)
            else:
                resolved_id = _resolve_media_id(media_id, ig)
                info = ig.media.get_full_info(resolved_id) if hasattr(ig.media, "get_full_info") else ig.media.get_info(resolved_id)
        else:
            if hasattr(ig, "media") and hasattr(ig.media, "get_full_info"):
                info = ig.media.get_full_info(media_id)
            elif hasattr(ig, "media") and hasattr(ig.media, "get_info"):
                info = ig.media.get_info(media_id)
            else:
                return "Error: media info endpoint not available."

        if not info:
            return f"Post not found: {media_id}"

        if isinstance(info, dict):
            lines = [
                f"Post Info:",
                f"  Type: {info.get('media_type', info.get('type', 'unknown'))}",
                f"  Owner: @{info.get('owner', {}).get('username', info.get('username', 'N/A'))}",
                f"  Likes: {info.get('likes', info.get('like_count', 0)):,}",
                f"  Comments: {info.get('comments_count', info.get('comment_count', 0)):,}",
            ]
            caption = info.get("caption", "")
            if isinstance(caption, dict):
                caption = caption.get("text", "")
            if caption:
                lines.append(f"  Caption: {str(caption)[:200]}")

            shortcode = info.get("code", info.get("shortcode", ""))
            if shortcode:
                lines.append(f"  URL: https://instagram.com/p/{shortcode}/")

            views = info.get("views", info.get("play_count", 0))
            if views:
                lines.append(f"  Views: {views:,}")

            return "\n".join(lines)

        return f"Post info: {str(info)[:500]}"

    except Exception as e:
        return f"Error getting post info: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 22: get_stories — User stories
# ═══════════════════════════════════════════════════════════

def handle_get_stories(args: Dict, ig=None, is_logged_in=False) -> str:
    """Get user's stories."""
    username = args.get("username", "").strip().lstrip("@").lower()

    if not username:
        return "Error: username is required."
    if not is_logged_in:
        return "Error: viewing stories requires login."
    if ig is None:
        return "Error: Instagram client not available."

    try:
        user = ig.users.get_by_username(username)
        if not user:
            return f"User '@{username}' not found."

        user_pk = user.get("pk") if isinstance(user, dict) else getattr(user, "pk", None)
        if not user_pk:
            return f"Could not get user ID for '@{username}'."

        # Try parsed stories first
        if hasattr(ig, "stories") and hasattr(ig.stories, "get_stories_parsed"):
            stories = ig.stories.get_stories_parsed(user_pk)
        elif hasattr(ig, "stories") and hasattr(ig.stories, "get_user_stories"):
            stories = ig.stories.get_user_stories(user_pk)
        else:
            return "Error: stories API not available."

        if not stories:
            return f"No active stories for @{username}."

        # Parse response
        items = []
        if isinstance(stories, dict):
            items = stories.get("items", stories.get("reel", {}).get("items", []))
        elif isinstance(stories, list):
            items = stories

        if not items:
            return f"No active stories for @{username}."

        lines = [f"Stories from @{username} ({len(items)} items):"]
        lines.append("-" * 50)

        for i, item in enumerate(items, 1):
            if isinstance(item, dict):
                mtype = "Photo" if item.get("media_type", 1) == 1 else "Video"
                timestamp = item.get("taken_at", item.get("timestamp", ""))
                lines.append(f"\n  {i}. [{mtype}] - {timestamp}")

                # Media URL
                if mtype == "Video":
                    videos = item.get("video_versions", [])
                    if videos:
                        lines.append(f"     URL: {videos[0].get('url', 'N/A')[:100]}")
                else:
                    images = item.get("image_versions2", {}).get("candidates", [])
                    if images:
                        lines.append(f"     URL: {images[0].get('url', 'N/A')[:100]}")

                viewers = item.get("viewer_count", item.get("total_viewer_count"))
                if viewers:
                    lines.append(f"     Viewers: {viewers:,}")
            else:
                lines.append(f"\n  {i}. {str(item)[:200]}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting stories for '@{username}': {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 23: send_dm — Direct message
# ═══════════════════════════════════════════════════════════

def handle_send_dm(args: Dict, ig=None, is_logged_in=False) -> str:
    """Send a direct message."""
    username = args.get("username", "").strip().lstrip("@").lower()
    text = args.get("text", "").strip()
    thread_id = args.get("thread_id", "").strip()

    if not text:
        return "Error: message text is required."
    if not is_logged_in:
        return "Error: sending DM requires login."
    if ig is None:
        return "Error: Instagram client not available."

    try:
        # If thread_id is given, send directly
        if thread_id:
            ig.direct.send_text(thread_id, text)
            return f"✅ Message sent to thread {thread_id}: '{text}'"

        # Otherwise, need username to create/find thread
        if not username:
            return "Error: either username or thread_id is required."

        user = ig.users.get_by_username(username)
        if not user:
            return f"User '@{username}' not found."

        user_pk = user.get("pk") if isinstance(user, dict) else getattr(user, "pk", None)
        if not user_pk:
            return f"Could not get user ID for '@{username}'."

        # Create new thread with message
        result = ig.direct.create_thread([user_pk], text=text)
        return f"✅ Message sent to @{username}: '{text}'"

    except Exception as e:
        return f"Error sending DM: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 24: get_hashtag_info — Hashtag data
# ═══════════════════════════════════════════════════════════

def handle_get_hashtag_info(args: Dict, ig=None, is_logged_in=False) -> str:
    """Get hashtag information."""
    hashtag = args.get("hashtag", "").strip().lstrip("#").lower()

    if not hashtag:
        return "Error: hashtag name is required."
    if not is_logged_in:
        return "Error: hashtag info requires login."
    if ig is None:
        return "Error: Instagram client not available."

    try:
        info = ig.hashtags.get_info(hashtag)
        if not info:
            return f"Hashtag '#{hashtag}' not found."

        if isinstance(info, dict):
            lines = [
                f"Hashtag Info: #{hashtag}",
                f"  Posts: {info.get('media_count', 0):,}",
            ]
            if info.get("name"):
                lines.append(f"  Name: {info['name']}")
            if info.get("id"):
                lines.append(f"  ID: {info['id']}")
            if info.get("following"):
                lines.append(f"  You follow: Yes")

            # Try getting related hashtags
            try:
                related = ig.hashtags.get_related(hashtag)
                if related and isinstance(related, list):
                    related_names = [r.get("name", str(r)) for r in related[:10] if isinstance(r, dict)]
                    if related_names:
                        lines.append(f"  Related: {', '.join('#' + n for n in related_names)}")
            except Exception:
                pass

            return "\n".join(lines)

        return f"Hashtag #{hashtag}: {str(info)[:500]}"

    except Exception as e:
        return f"Error getting hashtag info: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL 25: get_my_account — Current user info
# ═══════════════════════════════════════════════════════════

def handle_get_my_account(args: Dict, ig=None, is_logged_in=False) -> str:
    """Get current logged-in user info."""
    if not is_logged_in:
        return "Error: account info requires login."
    if ig is None:
        return "Error: Instagram client not available."

    try:
        if hasattr(ig, "account") and hasattr(ig.account, "get_current_user"):
            user = ig.account.get_current_user()
        else:
            return "Error: account API not available."

        if not user or (isinstance(user, dict) and user.get("status") == "fail"):
            msg = user.get("message", "unknown error") if isinstance(user, dict) else "no data"
            return f"Error: could not get account info: {msg}"

        if isinstance(user, dict):
            lines = [
                f"My Account:",
                f"  Username: @{user.get('username', 'N/A')}",
                f"  Full Name: {user.get('full_name', 'N/A')}",
                f"  Followers: {user.get('followers', user.get('follower_count', 0)):,}",
                f"  Following: {user.get('following', user.get('following_count', 0)):,}",
                f"  Posts: {user.get('posts_count', user.get('media_count', 0)):,}",
                f"  Bio: {user.get('biography', 'N/A')}",
                f"  Verified: {'Yes' if user.get('is_verified') else 'No'}",
                f"  Private: {'Yes' if user.get('is_private') else 'No'}",
            ]
            if user.get("external_url"):
                lines.append(f"  Website: {user['external_url']}")
            if user.get("email"):
                lines.append(f"  Email: {user['email']}")
            return "\n".join(lines)

        return f"My account: {str(user)[:500]}"

    except Exception as e:
        return f"Error getting account info: {e}"


# ═══════════════════════════════════════════════════════════
# TOOL REGISTRY — Maps tool names to handlers
# ═══════════════════════════════════════════════════════════

TOOL_HANDLERS = {
    "read_file": handle_read_file,
    "list_files": handle_list_files,
    "download_media": handle_download_media,
    "analyze_data": handle_analyze_data,
    "http_request": handle_http_request,
    "create_chart": handle_create_chart,
    "search_web": handle_search_web,
    # Specialized Instagram tools (Phase 1)
    "get_profile": handle_get_profile,
    "get_posts": handle_get_posts,
    "search_users": handle_search_users,
    "get_user_info": handle_get_user_info,
    # Specialized Instagram tools (Phase 2)
    "follow_user": handle_follow_user,
    "get_followers": handle_get_followers,
    "get_following": handle_get_following,
    "get_friendship_status": handle_get_friendship_status,
    "like_media": handle_like_media,
    "comment_media": handle_comment_media,
    "get_media_info": handle_get_media_info,
    "get_stories": handle_get_stories,
    "send_dm": handle_send_dm,
    "get_hashtag_info": handle_get_hashtag_info,
    "get_my_account": handle_get_my_account,
}

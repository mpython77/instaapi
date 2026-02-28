"""
Auth Platform Challenge Resolver
=================================
Handles Instagram's new auth_platform checkpoint flow using GraphQL API.

When Instagram detects an unusual login, it returns checkpoint_required
with a checkpoint_url containing /auth_platform/?apc=...

The flow:
    1. Visit checkpoint page → triggers email send to user
    2. Read verification code from Gmail via EmailVerifier
    3. Submit code via GraphQL /api/graphql (useAuthPlatformSubmitCodeMutation)

GraphQL payload structure matched from real Chrome DevTools.
"""

import json
import os
import re
import time
import logging
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("instaharvest_v2")

# GraphQL constants (from real Chrome DevTools)
GRAPHQL_URL = "https://www.instagram.com/api/graphql"
SUBMIT_CODE_DOC_ID = "25017097917894476"
SEC_CH_UA = '"Not A Brand";v="99", "Google Chrome";v="142", "Chromium";v="142"'

# Debug log directory
DEBUG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug_logs")


def _save_debug_response(filename: str, content: str) -> None:
    """Save response content to debug file for analysis."""
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        filepath = os.path.join(DEBUG_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.debug(f"[AuthPlatform] Debug saved: {filepath}")
    except Exception as e:
        logger.debug(f"[AuthPlatform] Failed to save debug: {e}")


def _extract_page_tokens(page_html: str) -> dict:
    """
    Extract all required tokens from the auth_platform HTML page.
    These tokens are needed for the GraphQL mutation request.
    """
    tokens = {
        "lsd": "",
        "jazoest": "",
        "hsi": "",
        "spin_r": "1033859812",
        "spin_t": "",
        "__hs": "",
        "__s": "",
        "__dyn": "",
        "__csr": "",
        "__hsdp": "",
        "__hblp": "",
        "__sjsp": "",
    }

    # LSD token
    m = re.search(r'"LSD",\[\],\{"token":"([^"]+)"', page_html)
    if not m:
        m = re.search(r'"lsd":\{"token":"([^"]+)"', page_html)
    if not m:
        m = re.search(r'name="lsd"\s+value="([^"]+)"', page_html)
    if m:
        tokens["lsd"] = m.group(1)

    # Jazoest
    m = re.search(r'"jazoest"\s*[:,]\s*"?(\d+)"?', page_html)
    if not m:
        m = re.search(r'jazoest=(\d+)', page_html)
    if m:
        tokens["jazoest"] = m.group(1)

    # HSI
    m = re.search(r'"hsi":"(\d+)"', page_html)
    if m:
        tokens["hsi"] = m.group(1)

    # __spin_r (revision)
    m = re.search(r'"server_revision":(\d+)', page_html)
    if not m:
        m = re.search(r'"__spin_r":(\d+)', page_html)
    if m:
        tokens["spin_r"] = m.group(1)

    # __spin_t (timestamp from page)
    m = re.search(r'"__spin_t":(\d+)', page_html)
    if m:
        tokens["spin_t"] = m.group(1)

    # __hs (HasteSite)
    m = re.search(r'"haste_session":"([^"]+)"', page_html)
    if not m:
        m = re.search(r'"__hs":"([^"]+)"', page_html)
    if m:
        tokens["__hs"] = m.group(1)

    # __s (session tokens): format like "abc123:def456:ghi789"
    m = re.search(r'"__s":"([^"]+)"', page_html)
    if m:
        tokens["__s"] = m.group(1)

    # __dyn (dynamic modules)
    m = re.search(r'"__dyn":"([^"]+)"', page_html)
    if m:
        tokens["__dyn"] = m.group(1)

    # __csr (CSR)
    m = re.search(r'"__csr":"([^"]+)"', page_html)
    if m:
        tokens["__csr"] = m.group(1)

    # __hsdp
    m = re.search(r'"__hsdp":"([^"]+)"', page_html)
    if m:
        tokens["__hsdp"] = m.group(1)

    # __hblp
    m = re.search(r'"__hblp":"([^"]+)"', page_html)
    if m:
        tokens["__hblp"] = m.group(1)

    # __sjsp
    m = re.search(r'"__sjsp":"([^"]+)"', page_html)
    if m:
        tokens["__sjsp"] = m.group(1)

    return tokens


def resolve_auth_platform(
    session,
    checkpoint_url: str,
    csrf_token: str,
    user_agent: str,
    challenge_callback: Optional[Callable] = None,
    username: str = "",
) -> Dict[str, Any]:
    """
    Resolve auth_platform challenge using Instagram's GraphQL API.

    Args:
        session: curl_cffi Session
        checkpoint_url: The auth_platform URL with apc parameter
        csrf_token: Current CSRF token
        user_agent: User-Agent string
        challenge_callback: Callback that returns the email verification code
        username: Instagram username (for result)

    Returns:
        dict with authentication result, or None if failed
    """
    # Normalize URL
    full_url = checkpoint_url if checkpoint_url.startswith("http") \
        else f"https://www.instagram.com{checkpoint_url}"

    # Step 0: Extract encrypted_ap_context from apc parameter
    parsed = urlparse(full_url)
    params = parse_qs(parsed.query)
    encrypted_ap_context = params.get("apc", [""])[0]

    if not encrypted_ap_context:
        logger.warning("[AuthPlatform] No apc parameter found in URL")
        return None

    logger.info(f"[AuthPlatform] apc extracted ({len(encrypted_ap_context)} chars)")
    print(f"[DEBUG-AP] apc: {encrypted_ap_context[:60]}...")

    # Step 1: Visit checkpoint page (triggers email send + extract tokens)
    logger.info("[AuthPlatform] Visiting checkpoint page (triggers email send)...")
    tokens = {}

    try:
        page_resp = session.get(full_url, headers={
            "user-agent": user_agent,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "sec-ch-ua": SEC_CH_UA,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "referer": "https://www.instagram.com/accounts/login/",
            "upgrade-insecure-requests": "1",
        }, timeout=15)

        # Update CSRF
        new_csrf = session.cookies.get("csrftoken", "")
        if new_csrf:
            csrf_token = new_csrf

        # Extract ALL required tokens from page
        tokens = _extract_page_tokens(page_resp.text)

        found = sum(1 for v in tokens.values() if v)
        logger.info(f"[AuthPlatform] Extracted {found}/{len(tokens)} tokens from page")

    except Exception as e:
        logger.warning(f"[AuthPlatform] Checkpoint page failed: {e}")
        tokens = _extract_page_tokens("")  # Use defaults

    # Wait for email to arrive
    time.sleep(3)

    # Step 2: Get verification code from callback
    if not challenge_callback:
        return None

    logger.info("[AuthPlatform] Waiting for verification code from email...")
    code = challenge_callback()
    print(f"[DEBUG-AP] Got code from email: {code}")
    if not code:
        logger.warning("[AuthPlatform] No verification code received")
        return None

    time.sleep(1)

    # Step 3: Submit code via GraphQL (exact Chrome payload format)
    logger.info(f"[AuthPlatform] Submitting code via GraphQL: {code}")

    spin_r = tokens.get("spin_r", "1033859812")

    variables = json.dumps({
        "input": {
            "client_mutation_id": "1",
            "actor_id": "0",
            "code": str(code),
            "encrypted_ap_context": encrypted_ap_context,
        }
    })

    # Build payload — exact match to real Chrome DevTools
    graphql_data = {
        "av": "0",
        "__d": "www",
        "__user": "0",
        "__a": "1",
        "__req": "r",
        "dpr": "1",
        "__ccg": "GOOD",
        "__rev": spin_r,
        "__comet_req": "7",
        "lsd": tokens.get("lsd", ""),
        "jazoest": tokens.get("jazoest", ""),
        "__spin_r": spin_r,
        "__spin_b": "trunk",
        "__spin_t": tokens.get("spin_t", str(int(time.time()))),
        "__crn": "comet.igweb.PolarisAuthPlatformCodeEntryRoute",
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "useAuthPlatformSubmitCodeMutation",
        "server_timestamps": "true",
        "variables": variables,
        "doc_id": SUBMIT_CODE_DOC_ID,
    }

    # Add optional tokens (only if extracted from page)
    if tokens.get("hsi"):
        graphql_data["__hsi"] = tokens["hsi"]
    if tokens.get("__hs"):
        graphql_data["__hs"] = tokens["__hs"]
    if tokens.get("__s"):
        graphql_data["__s"] = tokens["__s"]
    if tokens.get("__dyn"):
        graphql_data["__dyn"] = tokens["__dyn"]
    if tokens.get("__csr"):
        graphql_data["__csr"] = tokens["__csr"]
    if tokens.get("__hsdp"):
        graphql_data["__hsdp"] = tokens["__hsdp"]
    if tokens.get("__hblp"):
        graphql_data["__hblp"] = tokens["__hblp"]
    if tokens.get("__sjsp"):
        graphql_data["__sjsp"] = tokens["__sjsp"]

    graphql_headers = {
        "user-agent": user_agent,
        "content-type": "application/x-www-form-urlencoded",
        "x-csrftoken": csrf_token,
        "x-ig-app-id": "936619743392459",
        "x-requested-with": "XMLHttpRequest",
        "x-instagram-ajax": spin_r,
        "x-fb-lsd": tokens.get("lsd", ""),
        "x-asbd-id": "129477",
        "x-fb-friendly-name": "useAuthPlatformSubmitCodeMutation",
        "referer": full_url,
        "origin": "https://www.instagram.com",
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
    }

    try:
        verify_resp = session.post(
            GRAPHQL_URL,
            headers=graphql_headers,
            data=graphql_data,
            timeout=30,
            allow_redirects=True,
        )

        logger.info(f"[AuthPlatform] GraphQL response: {verify_resp.status_code}")

        # Save FULL response for debugging
        resp_text = verify_resp.text
        _save_debug_response(
            f"graphql_response_{int(time.time())}.txt",
            f"Status: {verify_resp.status_code}\n"
            f"Headers: {dict(verify_resp.headers)}\n\n"
            f"Body:\n{resp_text}"
        )

        # Log all cookies after GraphQL request
        all_cookies = {k: v for k, v in session.cookies.items()}
        logger.info(f"[AuthPlatform] Cookies after GraphQL: {list(all_cookies.keys())}")

        # Check for sessionid in cookies — success indicator
        if session.cookies.get("sessionid"):
            logger.info("[AuthPlatform] Session cookie found — challenge resolved! ✅")
            ds_user_id = session.cookies.get("ds_user_id", "")
            return {
                "status": "ok",
                "authenticated": True,
                "user_id": ds_user_id,
                "username": username,
                "challenge_resolved": True,
            }

        try:
            verify_data = verify_resp.json()
            logger.info(f"[AuthPlatform] Response JSON: {json.dumps(verify_data, ensure_ascii=False)[:500]}")

            # Save parsed JSON for debugging
            _save_debug_response(
                f"graphql_parsed_{int(time.time())}.json",
                json.dumps(verify_data, indent=2, ensure_ascii=False)
            )

            # Check for GraphQL errors array
            errors = verify_data.get("errors", [])
            if errors:
                for err in errors:
                    logger.warning(f"[AuthPlatform] GraphQL error: {err.get('message', err)}")

            # Check GraphQL result shape — try ALL known key patterns
            data = verify_data.get("data", {})
            submit_result = None

            # Known key patterns (Instagram changes these)
            known_keys = [
                "xfb_auth_platform_submit_code",
                "auth_platform_submit_code",
                "xdt_auth_platform_submit_code",
                "ig_auth_platform_submit_code",
            ]
            for key in known_keys:
                if data.get(key):
                    submit_result = data[key]
                    logger.info(f"[AuthPlatform] Found result under key: {key}")
                    break

            # Fallback: scan ALL keys in data for anything with submit_code
            if not submit_result:
                for key, val in data.items():
                    if "submit_code" in key.lower() or "auth_platform" in key.lower():
                        submit_result = val
                        logger.info(f"[AuthPlatform] Found result under dynamic key: {key}")
                        break

            # If still no submit_result, check if data itself has useful fields
            if not submit_result and data:
                logger.info(f"[AuthPlatform] Data keys: {list(data.keys())}")
                # Some responses have the result at data level directly
                if data.get("redirect_uri") or data.get("result"):
                    submit_result = data

            if not submit_result:
                submit_result = {}
                logger.warning(f"[AuthPlatform] No submit_result found in data keys: {list(data.keys())}")

            redirect_uri = submit_result.get("redirect_uri", "")
            result_status = submit_result.get("result", "")
            error_msg = submit_result.get("error_message", "")
            ap_error = submit_result.get("ap_error_code", "")

            logger.info(
                f"[AuthPlatform] Result: status={result_status}, "
                f"redirect={redirect_uri[:60] if redirect_uri else 'none'}, "
                f"error={error_msg or ap_error or 'none'}"
            )

            # If we got a redirect_uri, follow it to complete login
            if redirect_uri:
                logger.info(f"[AuthPlatform] Got redirect_uri: {redirect_uri[:80]}")
                try:
                    redir_url = redirect_uri if redirect_uri.startswith("http") \
                        else f"https://www.instagram.com{redirect_uri}"
                    redir_resp = session.get(redir_url, headers={
                        "user-agent": user_agent,
                        "referer": full_url,
                        "sec-ch-ua": SEC_CH_UA,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"',
                        "sec-fetch-dest": "document",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-site": "same-origin",
                    }, timeout=15, allow_redirects=True)
                    logger.info(f"[AuthPlatform] Redirect response: {redir_resp.status_code}")
                    logger.info(f"[AuthPlatform] Cookies after redirect: {list(session.cookies.keys())}")
                except Exception as e:
                    logger.debug(f"[AuthPlatform] Redirect follow: {e}")

                # Check if redirect gave us a session
                if session.cookies.get("sessionid"):
                    logger.info("[AuthPlatform] Session obtained after redirect! ✅")
                    ds_user_id = session.cookies.get("ds_user_id", "")
                    return {
                        "status": "ok",
                        "authenticated": True,
                        "user_id": ds_user_id,
                        "username": username,
                        "challenge_resolved": True,
                    }

            if result_status in ("SUCCESS", "success") or redirect_uri:
                logger.info("[AuthPlatform] Code verified! ✅")
                return {
                    "status": "ok",
                    "authenticated": False,
                    "username": username,
                    "challenge_resolved": True,
                }

            # No explicit success/redirect but no error either = challenge accepted
            if submit_result and not error_msg and not ap_error:
                logger.info("[AuthPlatform] Challenge accepted (no errors)! ✅")
                return {
                    "status": "ok",
                    "authenticated": False,
                    "username": username,
                    "challenge_resolved": True,
                }

            # Alternative: logged_in_user
            if verify_data.get("logged_in_user"):
                uid = verify_data.get("logged_in_user", {}).get("pk", "")
                logger.info("[AuthPlatform] Login successful! ✅")
                return {
                    "status": "ok",
                    "authenticated": True,
                    "user_id": str(uid),
                    "username": username,
                    "challenge_resolved": True,
                    "redirect_uri": redirect_uri,
                }

            # Error case — log clearly
            if error_msg or ap_error:
                logger.error(
                    f"[AuthPlatform] Code rejected! "
                    f"error_message={error_msg}, ap_error_code={ap_error}"
                )
            else:
                logger.warning(
                    f"[AuthPlatform] Unexpected result — "
                    f"full response saved to debug_logs/"
                )

        except ValueError:
            # Not JSON — might be HTML redirect
            logger.warning(f"[AuthPlatform] Non-JSON response (len={len(resp_text)})")
            _save_debug_response(
                f"graphql_html_{int(time.time())}.html", resp_text
            )
            # Check if we got session from redirect
            if session.cookies.get("sessionid"):
                logger.info("[AuthPlatform] Session found after non-JSON response! ✅")
                ds_user_id = session.cookies.get("ds_user_id", "")
                return {
                    "status": "ok",
                    "authenticated": True,
                    "user_id": ds_user_id,
                    "username": username,
                    "challenge_resolved": True,
                }

        except Exception as e:
            logger.warning(f"[AuthPlatform] Response parse error: {e}")

    except Exception as e:
        logger.warning(f"[AuthPlatform] GraphQL request failed: {e}")

    return None

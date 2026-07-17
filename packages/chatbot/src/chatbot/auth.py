"""
Shared auth + CORS logic for chatbot's HTTP entrypoints.

This exists because _check_api_key and the CORS origin-parsing logic were
previously copied verbatim across three separate entrypoints
(packages/chatbot/api_server.py, packages/chatbot/entrypoints/fastapi_app.py,
packages/chatbot/src/chatbot/entrypoints/fastapi_app.py). Any auth fix
(status code change, key rotation, opt-out env var rename) had to be applied
in all three places by hand — a partial update silently left whichever
entrypoint a real deployment happened to be running with the old, possibly
broken logic. Since the README lets deployers pick whichever entrypoint
suits them, there's no safe assumption about which copy is actually in use.

All three entrypoints should import check_api_key() and cors_origins() from
here instead of defining their own copies.
"""

from __future__ import annotations

import hmac
import os

from fastapi import HTTPException


def check_api_key(provided: str | None) -> None:
    """
    Raise HTTPException(500) if CHATBOT_API_KEY isn't configured (unless
    CHATBOT_ALLOW_INSECURE_NO_AUTH=true was explicitly set), or
    HTTPException(401) if `provided` doesn't match it. Returns None (no
    exception) if the key is valid, or if insecure mode was explicitly
    opted into.
    """
    expected = os.environ.get("CHATBOT_API_KEY")
    allow_insecure = os.environ.get("CHATBOT_ALLOW_INSECURE_NO_AUTH", "").lower() == "true"
    if not expected:
        if allow_insecure:
            return  # explicitly opted into no-auth mode (local dev only)
        raise HTTPException(
            status_code=500,
            detail=(
                "Server misconfigured: CHATBOT_API_KEY is not set. Set "
                "CHATBOT_API_KEY to a strong secret, or set "
                "CHATBOT_ALLOW_INSECURE_NO_AUTH=true to explicitly run "
                "without authentication (not recommended)."
            ),
        )
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")


def cors_origins() -> list[str]:
    """
    Parsed CHATBOT_CORS_ALLOWED_ORIGINS (comma-separated). Empty/unset
    means no cross-origin access at all (fail closed) — there is no "*"
    fallback; wildcard CORS combined with any credentialed access is
    unsafe in production.
    """
    raw = os.environ.get("CHATBOT_CORS_ALLOWED_ORIGINS", "")
    return [o.strip() for o in raw.split(",") if o.strip()]

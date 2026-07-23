"""Canonical public site URL for emails, push, share links, and SEO."""
from __future__ import annotations

import os

CANONICAL_PUBLIC_BASE_URL = "https://mx-fantasy.se"

LEGACY_RENDER_HOSTS = frozenset(
    {
        "mx-fatasy-league-eu.onrender.com",
        "mx-fatasy-league.onrender.com",
        "mx-fatasy-league.eu.onrender.com",
    }
)


def get_public_base_url() -> str:
    """
    Absolute site origin (no trailing slash) for outbound links.
    Prefer PUBLIC_BASE_URL; on Render default to the custom domain so share/email
    links never stick to *.onrender.com.
    """
    v = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if v:
        return v

    if os.getenv("RENDER"):
        return CANONICAL_PUBLIC_BASE_URL

    try:
        from flask import has_request_context, request

        if has_request_context() and request.host_url:
            host = (request.host or "").split(":")[0].lower()
            if is_legacy_render_host(host):
                return CANONICAL_PUBLIC_BASE_URL
            # Custom domain behind TLS-terminating proxy often reports http:// —
            # always emit the canonical https origin for SEO/share links.
            if host in ("mx-fantasy.se", "www.mx-fantasy.se"):
                return CANONICAL_PUBLIC_BASE_URL
            return request.host_url.rstrip("/")
    except Exception:
        pass

    return CANONICAL_PUBLIC_BASE_URL

def is_legacy_render_host(host: str | None) -> bool:
    h = (host or "").split(":")[0].lower()
    if not h:
        return False
    if h in LEGACY_RENDER_HOSTS:
        return True
    return "mx-fatasy" in h and h.endswith(".onrender.com")


def legacy_redirect_url(full_path: str) -> str:
    """Build https://mx-fantasy.se/... from a Flask request.full_path."""
    path = full_path or "/"
    if path.endswith("?") and "?" in path:
        path = path[:-1]
    if not path.startswith("/"):
        path = "/" + path
    return f"{CANONICAL_PUBLIC_BASE_URL}{path}"

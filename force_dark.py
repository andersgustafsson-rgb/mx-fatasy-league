"""Force dark theme on all HTML responses.

The UI is dark-designed. Tailwind CDN defaults to darkMode:'media', so light OS
preference reveals light-first utilities (bg-white tables on dark chrome).
This injects class-based dark + a CSS safety net on every HTML page.
"""
from __future__ import annotations

import re
from typing import Any

_MARKER = "mx-force-dark"

# Early head: color-scheme + html.dark before paint; Tailwind class mode after CDN.
_HEAD_EARLY = (
    f'<!-- {_MARKER} -->'
    '<meta name="color-scheme" content="dark" />'
    '<meta name="theme-color" content="#0f172a" />'
    "<script>(function(){try{"
    "document.documentElement.classList.add('dark');"
    "document.documentElement.style.colorScheme='dark';"
    "}catch(e){}})();</script>"
    f'<link rel="stylesheet" href="/static/mx_force_dark.css" data-{_MARKER}="1" />'
)

_TAILWIND_CONFIG = (
    "<script>"
    "try{"
    "window.tailwind=window.tailwind||{};"
    "tailwind.config=Object.assign({},tailwind.config||{},{darkMode:'class'});"
    "}catch(e){}"
    "</script>"
)

_HTML_TAG_RE = re.compile(r"<html(\s[^>]*)?>", re.IGNORECASE)
_TAILWIND_CDN_RE = re.compile(
    r'(<script\s[^>]*src=["\']https://cdn\.tailwindcss\.com[^"\']*["\'][^>]*>\s*</script>)',
    re.IGNORECASE,
)


def force_dark_html(html: str) -> str:
    """Rewrite HTML string to force dark theme. Idempotent via marker comment."""
    if _MARKER in html:
        return html

    # Ensure <html class="dark" ...>
    def _html_with_dark(m: re.Match[str]) -> str:
        attrs = m.group(1) or ""
        if re.search(r"""\bclass\s*=\s*["'][^"']*\bdark\b""", attrs, re.I):
            return m.group(0)
        class_m = re.search(r"""\bclass\s*=\s*(["'])(.*?)(\1)""", attrs, re.I)
        if class_m:
            q, val = class_m.group(1), class_m.group(2)
            new_attrs = (
                attrs[: class_m.start()]
                + f'class={q}dark {val}{q}'
                + attrs[class_m.end() :]
            )
            return f"<html{new_attrs}>"
        return f'<html class="dark"{attrs}>'

    html = _HTML_TAG_RE.sub(_html_with_dark, html, count=1)

    lower = html.lower()
    # Insert early bootstrap right after <head ...>
    head_open = re.search(r"<head(\s[^>]*)?>", html, re.IGNORECASE)
    if head_open:
        i = head_open.end()
        html = html[:i] + _HEAD_EARLY + html[i:]
    else:
        # Fallback: before </head> or at start
        lower = html.lower()
        head_i = lower.find("</head>")
        if head_i != -1:
            html = html[:head_i] + _HEAD_EARLY + html[head_i:]
        else:
            html = _HEAD_EARLY + html

    # Configure Tailwind darkMode:'class' immediately after CDN script
    if _TAILWIND_CDN_RE.search(html):
        html = _TAILWIND_CDN_RE.sub(r"\1" + _TAILWIND_CONFIG, html, count=1)
    else:
        # No Tailwind CDN — still leave CSS safety net from _HEAD_EARLY
        pass

    return html


def register_force_dark(app: Any) -> None:
    """Attach after_request hook that rewrites text/html responses."""

    @app.after_request
    def _force_dark_theme(response):  # type: ignore[no-untyped-def]
        ctype = (response.headers.get("Content-Type") or "").lower()
        if "text/html" not in ctype:
            return response
        try:
            if getattr(response, "direct_passthrough", False):
                response.direct_passthrough = False
            raw = response.get_data()
            if not raw:
                return response
            charset = getattr(response, "charset", None) or "utf-8"
            html = raw.decode(charset, "replace")
            if _MARKER in html:
                return response
            # Skip non-document fragments / email previews that embed full docs later
            lower = html.lower()
            if "<html" not in lower and "<!doctype" not in lower:
                return response
            new_html = force_dark_html(html)
            if new_html is html:
                return response
            response.set_data(new_html.encode("utf-8"))
            response.headers["Content-Type"] = "text/html; charset=utf-8"
            response.headers.pop("Content-Length", None)
        except Exception as e:
            print(f"force_dark skip: {type(e).__name__}: {e}")
        return response

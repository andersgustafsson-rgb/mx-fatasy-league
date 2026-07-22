"""Ping /api/cron/reminders — körs av Render Cron varje minut."""
from __future__ import annotations

import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request


def _post_urllib(url: str, secret: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "User-Agent": "mx-fantasy-reminder-cron/2",
        },
    )
    ctx = ssl.create_default_context()
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # type: ignore[attr-defined]
    except Exception:
        pass
    with urllib.request.urlopen(req, timeout=55, context=ctx) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def _post_curl(url: str, secret: str) -> tuple[int, str]:
    proc = subprocess.run(
        [
            "curl",
            "-sS",
            "-f",
            "-X",
            "POST",
            url,
            "-H",
            f"Authorization: Bearer {secret}",
            "-H",
            "User-Agent: mx-fantasy-reminder-cron/2",
            "--max-time",
            "55",
        ],
        capture_output=True,
        text=True,
    )
    body = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode, body


def main() -> int:
    secret = (os.getenv("CRON_SECRET") or os.getenv("REMINDER_CRON_SECRET") or "").strip()
    if not secret:
        print("CRON_SECRET saknas", file=sys.stderr)
        return 1

    url = (os.getenv("REMINDER_CRON_URL") or "").strip()
    if not url:
        base = (
            os.getenv("PUBLIC_BASE_URL")
            or os.getenv("RENDER_EXTERNAL_URL")
            or "https://mx-fantasy.se"
        ).strip().rstrip("/")
        if not base:
            print("REMINDER_CRON_URL eller PUBLIC_BASE_URL saknas", file=sys.stderr)
            return 1
        url = f"{base}/api/cron/reminders"

    if not url.startswith("https://"):
        print(f"REMINDER_CRON_URL måste vara https://, got: {url}", file=sys.stderr)
        return 1

    try:
        status, body = _post_curl(url, secret)
        if status == 0:
            print(body or '{"ok":true}')
            return 0
    except FileNotFoundError:
        pass
    except Exception as ex:
        print(f"curl failed: {ex}", file=sys.stderr)

    try:
        status, body = _post_urllib(url, secret)
        print(body)
        return 0 if 200 <= status < 300 else 1
    except urllib.error.HTTPError as ex:
        print(ex.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except Exception as ex:
        print(str(ex), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

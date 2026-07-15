"""Ping /api/cron/reminders — körs av Render Cron varje minut."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    secret = (os.getenv("CRON_SECRET") or os.getenv("REMINDER_CRON_SECRET") or "").strip()
    if not secret:
        print("CRON_SECRET saknas", file=sys.stderr)
        return 1

    url = (os.getenv("REMINDER_CRON_URL") or "").strip()
    if not url:
        base = (os.getenv("RENDER_EXTERNAL_URL") or os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
        if not base:
            print("REMINDER_CRON_URL eller RENDER_EXTERNAL_URL saknas", file=sys.stderr)
            return 1
        url = f"{base}/api/cron/reminders"

    req = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "User-Agent": "mx-fantasy-reminder-cron/1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=55) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(body)
            return 0 if 200 <= resp.status < 300 else 1
    except urllib.error.HTTPError as ex:
        print(ex.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except Exception as ex:
        print(str(ex), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

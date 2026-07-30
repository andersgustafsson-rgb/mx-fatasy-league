"""Ping /health so Render inte somnar — kör som Cron Job var 5–10 min."""
from __future__ import annotations

import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request


def _target_url() -> str:
    explicit = (os.getenv("KEEPALIVE_URL") or "").strip()
    if explicit:
        return explicit
    base = (
        os.getenv("PUBLIC_BASE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or "https://mx-fantasy.se"
    ).strip().rstrip("/")
    return f"{base}/health"


def _get_urllib(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "mx-fantasy-keepalive/1"},
    )
    ctx = ssl.create_default_context()
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # type: ignore[attr-defined]
    except Exception:
        pass
    with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
        return int(resp.status), resp.read().decode("utf-8", errors="replace")


def _get_curl(url: str) -> tuple[int, str]:
    proc = subprocess.run(
        [
            "curl",
            "-sS",
            "-f",
            "-L",
            url,
            "-H",
            "User-Agent: mx-fantasy-keepalive/1",
            "--max-time",
            "45",
        ],
        capture_output=True,
        text=True,
    )
    body = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode, body


def main() -> int:
    url = _target_url()
    if not url.startswith("https://"):
        print(f"KEEPALIVE_URL måste vara https://, got: {url}", file=sys.stderr)
        return 1

    ok = False
    try:
        code, body = _get_curl(url)
        if code == 0:
            print(body or '{"ok":true}')
            ok = True
    except FileNotFoundError:
        pass

    if not ok:
        try:
            status, body = _get_urllib(url)
            print(body or f'{{"status":{status}}}')
            ok = 200 <= status < 400
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code}: {e.reason}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"keepalive failed: {e}", file=sys.stderr)
            return 1

    # Also warm the homepage so the first human visit after idle/deploy
    # does not hit a cold / with heavy schema + queries.
    home = url.rsplit("/health", 1)[0].rstrip("/") + "/"
    if home.startswith("https://") and home != url:
        try:
            code, _ = _get_curl(home)
            if code == 0:
                print("homepage warm: ok")
            else:
                # curl -f fails on 4xx/5xx; try urllib anyway
                status, _ = _get_urllib(home)
                print(f"homepage warm: {status}")
        except Exception as e:
            print(f"homepage warm skipped: {e}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

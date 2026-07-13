"""Web Push — duell-notiser (test: endast topic=challenge)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime

from models import PushSubscription, db


_schema_ready = False


def ensure_push_tables() -> None:
    global _schema_ready
    if _schema_ready:
        return
    from sqlalchemy import inspect

    if not inspect(db.engine).has_table("push_subscriptions"):
        db.create_all()
    _schema_ready = True


def _vapid_private_key() -> str:
    raw = (os.getenv("VAPID_PRIVATE_KEY") or "").strip()
    if not raw:
        return ""
    if "\\n" in raw and "-----BEGIN" in raw:
        return raw.replace("\\n", "\n")
    return raw


def _vapid_subject() -> str:
    return (
        os.getenv("VAPID_SUBJECT", "").strip()
        or os.getenv("GMAIL_USER", "").strip()
        or "mailto:admin@mx-fantasy.local"
    )


def _application_server_key_from_pem(pem: str) -> str | None:
    """Härled publik nyckel från PEM så den alltid matchar privat nyckel."""
    if not pem or "BEGIN PRIVATE KEY" not in pem:
        return None
    path = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".pem", delete=False, encoding="utf-8"
        ) as f:
            f.write(pem)
            path = f.name
        out = subprocess.run(
            [
                sys.executable,
                "-m",
                "py_vapid",
                "--applicationServerKey",
                "--private-key",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if out.returncode != 0:
            print(f"VAPID key derive failed: {out.stderr or out.stdout}")
            return None
        for line in out.stdout.splitlines():
            if "Application Server Key" in line:
                return line.split("=", 1)[-1].strip()
    except Exception as ex:
        print(f"VAPID key derive error: {ex}")
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
    return None


def get_vapid_public_key_b64() -> str | None:
    """Publik nyckel till webbläsaren — härleds från privat PEM om möjligt."""
    pem = _vapid_private_key()
    if pem:
        derived = _application_server_key_from_pem(pem)
        if derived:
            return derived
    key = (os.getenv("VAPID_PUBLIC_KEY") or "").strip()
    return key or None


def push_configured() -> bool:
    return bool(_vapid_private_key())


def _public_base_url() -> str:
    for key in ("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL"):
        v = (os.getenv(key) or "").strip().rstrip("/")
        if v:
            return v
    return ""


def user_has_challenge_push(user_id: int) -> bool:
    ensure_push_tables()
    return (
        PushSubscription.query.filter_by(user_id=int(user_id), topic="challenge").first()
        is not None
    )


def list_subscriptions_for_user(user_id: int) -> list[dict]:
    ensure_push_tables()
    rows = PushSubscription.query.filter_by(
        user_id=int(user_id), topic="challenge"
    ).all()
    return [
        {
            "id": r.id,
            "endpoint_tail": (r.endpoint or "")[-48:],
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "user_agent": r.user_agent,
        }
        for r in rows
    ]


def save_subscription(
    user_id: int,
    subscription: dict,
    *,
    topic: str = "challenge",
    user_agent: str | None = None,
) -> PushSubscription:
    ensure_push_tables()
    endpoint = (subscription.get("endpoint") or "").strip()
    keys = subscription.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth_key = (keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth_key:
        raise ValueError("invalid_subscription")

    row = PushSubscription.query.filter_by(
        user_id=int(user_id), endpoint=endpoint
    ).first()
    if not row:
        row = PushSubscription(user_id=int(user_id), endpoint=endpoint)
        db.session.add(row)
    row.p256dh = p256dh
    row.auth_key = auth_key
    row.topic = topic
    row.user_agent = (user_agent or "")[:300] or None
    row.updated_at = datetime.utcnow()
    db.session.commit()
    return row


def remove_subscription(user_id: int, endpoint: str | None = None) -> int:
    ensure_push_tables()
    q = PushSubscription.query.filter_by(user_id=int(user_id), topic="challenge")
    if endpoint:
        q = q.filter_by(endpoint=endpoint.strip())
    deleted = q.delete(synchronize_session=False)
    db.session.commit()
    return deleted


def send_challenge_push_sync(
    user_id: int, title: str, preview: str, league_id: int
) -> dict:
    """Skicka push direkt — returnerar resultat (för test/diagnostik)."""
    if not push_configured():
        return {"ok": False, "error": "push_not_configured"}
    ensure_push_tables()
    subs = PushSubscription.query.filter_by(
        user_id=int(user_id), topic="challenge"
    ).all()
    if not subs:
        return {"ok": False, "error": "no_subscription", "hint": "Slå på duell-notiser i Pit Lane igen"}

    from pywebpush import WebPushException, webpush

    pem = _vapid_private_key()
    base = _public_base_url()
    path = (
        f"/leagues/{int(league_id)}#duelsSection"
        if int(league_id or 0) > 0
        else "/"
    )
    url = f"{base}{path}" if base else path
    payload = json.dumps(
        {
            "title": (title or "MX Fantasy")[:120],
            "body": (preview or "")[:240],
            "url": url,
            "tag": f"challenge-{league_id}",
        },
        ensure_ascii=False,
    )
    sent = 0
    errors: list[str] = []
    stale: list[PushSubscription] = []
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth_key},
                },
                data=payload,
                vapid_private_key=pem,
                vapid_claims={"sub": _vapid_subject()},
            )
            sent += 1
            print(f"Web push OK user={user_id} sub={sub.id}")
        except WebPushException as ex:
            status = getattr(getattr(ex, "response", None), "status_code", None)
            body = ""
            try:
                body = (ex.response.text or "")[:200] if ex.response else ""
            except Exception:
                pass
            msg = f"HTTP {status}: {ex} {body}".strip()
            errors.append(msg)
            print(f"Web push failed user={user_id}: {msg}")
            if status in (404, 410):
                stale.append(sub)
        except Exception as ex:
            errors.append(str(ex))
            print(f"Web push failed user={user_id}: {ex}")
    for sub in stale:
        db.session.delete(sub)
    if stale:
        db.session.commit()
    if sent:
        return {"ok": True, "sent": sent, "errors": errors}
    return {"ok": False, "error": errors[0] if errors else "send_failed", "errors": errors}


def _schedule(fn, *args, **kwargs) -> None:
    try:
        from flask import current_app

        app = current_app._get_current_object()
    except RuntimeError:
        return

    def job():
        with app.app_context():
            try:
                fn(*args, **kwargs)
            except Exception as ex:
                print(f"Web push error: {ex}")

    threading.Thread(target=job, daemon=True).start()


def notify_challenge_push(
    user_id: int, title: str, preview: str, league_id: int
) -> None:
    """Skicka mobilnotis för duell."""
    if not push_configured():
        return
    try:
        from flask import has_app_context

        if has_app_context():
            send_challenge_push_sync(int(user_id), title, preview, int(league_id))
            return
    except Exception:
        pass
    _schedule(send_challenge_push_sync, int(user_id), title, preview, int(league_id))

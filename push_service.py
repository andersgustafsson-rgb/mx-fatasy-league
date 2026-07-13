"""Web Push — duell-notiser (test: endast topic=challenge)."""
from __future__ import annotations

import json
import os
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


def push_configured() -> bool:
    return bool(
        os.getenv("VAPID_PUBLIC_KEY", "").strip()
        and os.getenv("VAPID_PRIVATE_KEY", "").strip()
    )


def get_vapid_public_key_b64() -> str | None:
    key = os.getenv("VAPID_PUBLIC_KEY", "").strip()
    return key or None


def _vapid_private_key() -> str:
    raw = os.getenv("VAPID_PRIVATE_KEY", "").strip()
    if "\\n" in raw:
        return raw.replace("\\n", "\n")
    return raw


def _vapid_subject() -> str:
    return (
        os.getenv("VAPID_SUBJECT", "").strip()
        or os.getenv("GMAIL_USER", "").strip()
        or "mailto:admin@mx-fantasy.local"
    )


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


def _send_challenge_push_sync(
    user_id: int, title: str, preview: str, league_id: int
) -> None:
    if not push_configured():
        return
    ensure_push_tables()
    subs = PushSubscription.query.filter_by(
        user_id=int(user_id), topic="challenge"
    ).all()
    if not subs:
        return

    from pywebpush import WebPushException, webpush

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
    stale: list[PushSubscription] = []
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth_key},
                },
                data=payload,
                vapid_private_key=_vapid_private_key(),
                vapid_claims={"sub": _vapid_subject()},
            )
        except WebPushException as ex:
            status = getattr(getattr(ex, "response", None), "status_code", None)
            if status in (404, 410):
                stale.append(sub)
            else:
                print(f"Web push failed for user {user_id}: {ex}")
        except Exception as ex:
            print(f"Web push failed for user {user_id}: {ex}")
    for sub in stale:
        db.session.delete(sub)
    if stale:
        db.session.commit()


def notify_challenge_push(
    user_id: int, title: str, preview: str, league_id: int
) -> None:
    """Skicka mobilnotis för duell (bakgrundstråd)."""
    if not push_configured():
        return
    _schedule(_send_challenge_push_sync, int(user_id), title, preview, int(league_id))

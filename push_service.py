"""Web Push — Pit Lane (DM, dueller, Race Control m.m.)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime

from models import PushSubscription, db

PUSH_TOPIC = "inbox"
PUSH_TOPICS_LEGACY = (PUSH_TOPIC, "challenge")
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


def _write_pem_tempfile(pem: str) -> str | None:
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".pem", delete=False, encoding="utf-8"
        ) as f:
            f.write(pem)
            if not pem.endswith("\n"):
                f.write("\n")
            return f.name
    except Exception as ex:
        print(f"VAPID temp PEM error: {ex}")
        return None


def _application_server_key_from_pem(pem: str) -> str | None:
    if not pem or "BEGIN PRIVATE KEY" not in pem:
        return None
    path = _write_pem_tempfile(pem)
    if not path:
        return None
    try:
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
        try:
            os.unlink(path)
        except OSError:
            pass
    return None


def _webpush_send(
    subscription_info: dict, payload: str, pem: str, subject: str
) -> None:
    from pywebpush import webpush

    path = _write_pem_tempfile(pem)
    if not path:
        raise ValueError("invalid_vapid_pem")
    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=path,
            vapid_claims={"sub": subject},
        )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def get_vapid_public_key_b64() -> str | None:
    pem = _vapid_private_key()
    if pem:
        derived = _application_server_key_from_pem(pem)
        if derived:
            return derived
    return (os.getenv("VAPID_PUBLIC_KEY") or "").strip() or None


def push_configured() -> bool:
    return bool(_vapid_private_key())


def _public_base_url() -> str:
    for key in ("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL"):
        v = (os.getenv(key) or "").strip().rstrip("/")
        if v:
            return v
    return ""


def _absolute_url(link_url: str | None) -> str:
    path = (link_url or "/pit-lane").strip() or "/pit-lane"
    if path.startswith(("http://", "https://")):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    base = _public_base_url()
    return f"{base}{path}" if base else path


def _subs_for_user(user_id: int) -> list[PushSubscription]:
    ensure_push_tables()
    return (
        PushSubscription.query.filter(
            PushSubscription.user_id == int(user_id),
            PushSubscription.topic.in_(PUSH_TOPICS_LEGACY),
        ).all()
    )


def user_has_push(user_id: int) -> bool:
    return bool(_subs_for_user(user_id))


def user_has_challenge_push(user_id: int) -> bool:
    """Bakåtkompatibelt namn."""
    return user_has_push(user_id)


def list_subscriptions_for_user(user_id: int) -> list[dict]:
    return [
        {
            "id": r.id,
            "topic": r.topic,
            "endpoint_tail": (r.endpoint or "")[-48:],
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "user_agent": r.user_agent,
        }
        for r in _subs_for_user(user_id)
    ]


def save_subscription(
    user_id: int,
    subscription: dict,
    *,
    topic: str = PUSH_TOPIC,
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
    q = PushSubscription.query.filter(
        PushSubscription.user_id == int(user_id),
        PushSubscription.topic.in_(PUSH_TOPICS_LEGACY),
    )
    if endpoint:
        q = q.filter_by(endpoint=endpoint.strip())
    deleted = q.delete(synchronize_session=False)
    db.session.commit()
    return deleted


def send_push_sync(
    user_id: int,
    title: str,
    preview: str,
    link_url: str | None = None,
    *,
    tag: str | None = None,
) -> dict:
    if not push_configured():
        return {"ok": False, "error": "push_not_configured"}
    subs = _subs_for_user(user_id)
    if not subs:
        return {
            "ok": False,
            "error": "no_subscription",
            "hint": "Slå på Pit Lane-notiser i klockan (överst)",
        }

    pem = _vapid_private_key()
    url = _absolute_url(link_url)
    payload = json.dumps(
        {
            "title": (title or "MX Fantasy")[:120],
            "body": (preview or "")[:240],
            "url": url,
            "tag": (tag or "pit-lane")[:64],
            "icon": "/static/icons/mx_notification_badge.png",
            "badge": "/static/icons/mx_notification_badge.png",
            "image": "/static/icons/mx_fantasy_app_icon_192.png",
        },
        ensure_ascii=False,
    )
    sent = 0
    errors: list[str] = []
    stale: list[PushSubscription] = []
    for sub in subs:
        try:
            _webpush_send(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth_key},
                },
                payload=payload,
                pem=pem,
                subject=_vapid_subject(),
            )
            sent += 1
            print(f"Web push OK user={user_id} sub={sub.id}")
        except Exception as ex:
            from pywebpush import WebPushException

            if isinstance(ex, WebPushException):
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
            else:
                errors.append(str(ex))
                print(f"Web push failed user={user_id}: {ex}")
    for sub in stale:
        db.session.delete(sub)
    if stale:
        db.session.commit()
    if sent:
        return {"ok": True, "sent": sent, "errors": errors}
    return {"ok": False, "error": errors[0] if errors else "send_failed", "errors": errors}


def send_challenge_push_sync(
    user_id: int, title: str, preview: str, league_id: int
) -> dict:
    link = (
        f"/leagues/{int(league_id)}#duelsSection"
        if int(league_id or 0) > 0
        else "/pit-lane"
    )
    return send_push_sync(
        user_id,
        title,
        preview,
        link,
        tag=f"challenge-{league_id}" if league_id else "challenge-test",
    )


def _dispatch_push(fn, *args, **kwargs) -> None:
    if not push_configured():
        return
    try:
        from flask import has_app_context

        if has_app_context():
            fn(*args, **kwargs)
            return
    except Exception:
        pass

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


def notify_inbox_push(
    user_id: int,
    title: str,
    preview: str | None,
    link_url: str | None = None,
    *,
    tag: str | None = None,
) -> None:
    _dispatch_push(
        send_push_sync,
        int(user_id),
        title,
        preview or "",
        link_url,
        tag=tag,
    )


def notify_challenge_push(
    user_id: int, title: str, preview: str, league_id: int
) -> None:
    link = f"/leagues/{int(league_id)}#duelsSection"
    notify_inbox_push(
        user_id, title, preview, link, tag=f"challenge-{league_id}"
    )


def notify_pick_reminder_push(
    user_id: int,
    competition_name: str,
    deadline_time: str,
    competition_id: int,
) -> dict:
    """Push-påminnelse om picks (samma tillfälle som pick-reminder-mail)."""
    if not user_has_push(user_id):
        return {"ok": False, "error": "no_subscription"}
    link = f"/race_picks/{int(competition_id)}"
    title = f"⏰ Picks: {competition_name}"[:120]
    preview = f"Deadline {deadline_time} — gör dina val innan tävlingen!"
    return send_push_sync(
        user_id,
        title,
        preview,
        link,
        tag=f"picks-{int(competition_id)}",
    )


def notify_all_subscribers_push(
    title: str,
    preview: str | None,
    link_url: str | None = None,
    *,
    tag: str = "broadcast",
) -> None:
    if not push_configured():
        return
    ensure_push_tables()
    rows = (
        db.session.query(PushSubscription.user_id)
        .filter(PushSubscription.topic.in_(PUSH_TOPICS_LEGACY))
        .distinct()
        .all()
    )
    for (uid,) in rows:
        notify_inbox_push(int(uid), title, preview or "", link_url, tag=tag)

"""E-postnotiser för Pit Lane (DM + Race Control)."""
from __future__ import annotations

import os
import re
import threading
from typing import Optional

from models import User, db

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _notify_enabled() -> bool:
    if os.getenv("PIT_LANE_EMAIL_NOTIFY", "1").strip().lower() in ("0", "false", "no"):
        return False
    return bool(os.getenv("GMAIL_PASSWORD", "").strip())


def _public_base_url() -> str:
    for key in ("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL"):
        v = (os.getenv(key) or "").strip().rstrip("/")
        if v:
            return v
    return ""


def _valid_email(email: str | None) -> bool:
    if not email:
        return False
    e = email.strip()
    return bool(e and _EMAIL_RE.match(e))


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
                print(f"Pit Lane email notify error: {ex}")

    threading.Thread(target=job, daemon=True).start()


def _send_dm_email(
    to_user_id: int,
    from_user_id: int,
    body: str,
    thread_id: int,
) -> None:
    if not _notify_enabled():
        return
    recipient = User.query.get(int(to_user_id))
    sender = User.query.get(int(from_user_id))
    if not recipient or not sender:
        return
    if not _valid_email(recipient.email):
        return
    if int(to_user_id) == int(from_user_id):
        return

    from email_utils import send_pit_lane_dm_email

    base = _public_base_url()
    pit_url = f"{base}/pit-lane?thread={thread_id}" if base else f"/pit-lane?thread={thread_id}"
    name = (recipient.display_name or recipient.username or "Spelare").strip()
    sender_name = (sender.display_name or sender.username or "Någon").strip()
    ok, err = send_pit_lane_dm_email(
        recipient.email.strip(),
        name,
        sender_name,
        body,
        pit_url,
        base or None,
    )
    if ok:
        print(f"Pit Lane: DM-notis skickad till {recipient.email}")
    elif err:
        print(f"Pit Lane: DM-notis misslyckades ({recipient.email}): {err}")


def _send_race_control_emails(body: str, priority: str) -> None:
    if not _notify_enabled():
        return
    from email_utils import send_pit_lane_race_control_email

    base = _public_base_url()
    pit_url = f"{base}/pit-lane?tab=race-control" if base else "/pit-lane?tab=race-control"
    important = (priority or "").lower() == "important"
    users = User.query.filter(User.email.isnot(None)).all()
    sent = failed = skipped = 0
    for user in users:
        if not _valid_email(user.email):
            skipped += 1
            continue
        name = (user.display_name or user.username or "Spelare").strip()
        ok, err = send_pit_lane_race_control_email(
            user.email.strip(),
            name,
            body,
            pit_url,
            important=important,
            base_url=base or None,
        )
        if ok:
            sent += 1
        else:
            failed += 1
            if err:
                print(f"Pit Lane RC email failed for {user.email}: {err}")
    print(f"Pit Lane: Race Control-e-post — skickade {sent}, misslyckades {failed}, utan e-post {skipped}")


def notify_dm_received(to_user_id: int, from_user_id: int, body: str, thread_id: int) -> None:
    """Skicka e-post till mottagaren (bakgrundstråd)."""
    _schedule(_send_dm_email, int(to_user_id), int(from_user_id), body, int(thread_id))


def notify_race_control_published(body: str, priority: str = "info") -> None:
    """Skicka e-post till alla användare med giltig e-postadress."""
    _schedule(_send_race_control_emails, (body or "").strip(), priority or "info")

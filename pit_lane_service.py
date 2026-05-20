"""Pit Lane — meddelandecenter, admin-historik och DM."""
from __future__ import annotations

import unicodedata
from datetime import datetime

from models import (
    db,
    User,
    GlobalSimulation,
    AdminAnnouncement,
    UserAnnouncementDismissal,
    MessageThread,
    Message,
    InboxNotification,
)

MAX_MESSAGE_LENGTH = 2000
_schema_ready = False


def normalize_pit_lane_body(body: str) -> str:
    """Behåll emoji och vanlig text; normalisera Unicode och ta bort kontrolltecken."""
    text = unicodedata.normalize("NFC", (body or "").strip())
    out: list[str] = []
    for ch in text:
        if ch in "\n\r\t":
            out.append(ch)
            continue
        cat = unicodedata.category(ch)
        if cat == "Cc":
            continue
        out.append(ch)
    return "".join(out).strip()


def _thread_pair(user_id_a: int, user_id_b: int) -> tuple[int, int]:
    a, b = int(user_id_a), int(user_id_b)
    return (a, b) if a < b else (b, a)


def ensure_pit_lane_tables() -> None:
    from sqlalchemy import inspect

    insp = inspect(db.engine)
    needed = (
        "admin_announcements",
        "user_announcement_dismissals",
        "message_threads",
        "messages",
        "inbox_notifications",
    )
    if any(not insp.has_table(t) for t in needed):
        db.create_all()
    migrate_legacy_announcement_if_needed()
    _schema_ready = True


def migrate_legacy_announcement_if_needed() -> None:
    if AdminAnnouncement.query.first() is not None:
        return
    gs = GlobalSimulation.query.first()
    if not gs or not gs.admin_message_active or not (gs.admin_message or "").strip():
        return
    ann = AdminAnnouncement(
        body=gs.admin_message.strip(),
        priority=gs.admin_message_priority or "info",
        is_active=True,
    )
    db.session.add(ann)
    db.session.commit()


def sync_global_sim_announcement(body: str | None, priority: str, active: bool) -> None:
    gs = GlobalSimulation.query.first()
    if not gs:
        gs = GlobalSimulation(id=1, active=False)
        db.session.add(gs)
    if active and body:
        gs.admin_message = body
        gs.admin_message_priority = priority
        gs.admin_message_active = True
    else:
        gs.admin_message_active = False
        if not body:
            gs.admin_message = None
            gs.admin_message_priority = None


def publish_admin_announcement(
    body: str, priority: str = "info", created_by_user_id: int | None = None
) -> AdminAnnouncement:
    body = normalize_pit_lane_body(body)
    AdminAnnouncement.query.filter_by(is_active=True).update({"is_active": False})
    ann = AdminAnnouncement(
        body=body,
        priority=priority or "info",
        is_active=True,
        created_by_user_id=created_by_user_id,
    )
    db.session.add(ann)
    sync_global_sim_announcement(body, ann.priority, True)
    db.session.commit()
    try:
        import pit_lane_notify as pln

        pln.notify_race_control_published(body, ann.priority or "info")
    except Exception as ex:
        print(f"Pit Lane: kunde inte köa Race Control-e-post: {ex}")
    return ann


def deactivate_admin_announcements() -> None:
    AdminAnnouncement.query.filter_by(is_active=True).update({"is_active": False})
    sync_global_sim_announcement(None, "info", False)
    db.session.commit()


def dismiss_announcement(user_id: int, announcement_id: int) -> None:
    exists = UserAnnouncementDismissal.query.filter_by(
        user_id=user_id, announcement_id=announcement_id
    ).first()
    if exists:
        return
    db.session.add(
        UserAnnouncementDismissal(user_id=user_id, announcement_id=announcement_id)
    )
    db.session.commit()


def active_announcement_unread(user_id: int) -> AdminAnnouncement | None:
    ann = AdminAnnouncement.query.filter_by(is_active=True).order_by(
        AdminAnnouncement.created_at.desc()
    ).first()
    if not ann:
        return None
    dismissed = UserAnnouncementDismissal.query.filter_by(
        user_id=user_id, announcement_id=ann.id
    ).first()
    return ann if not dismissed else None


def unread_dm_count(user_id: int) -> int:
    return (
        Message.query.join(MessageThread, Message.thread_id == MessageThread.id)
        .filter(
            Message.from_user_id != user_id,
            Message.read_at.is_(None),
            db.or_(
                MessageThread.user_a_id == user_id,
                MessageThread.user_b_id == user_id,
            ),
        )
        .count()
    )


def unread_inbox_notification_count(user_id: int) -> int:
    """Icke-DM-notiser (DM räknas via olästa meddelanden)."""
    return (
        InboxNotification.query.filter_by(user_id=user_id)
        .filter(InboxNotification.read_at.is_(None))
        .filter(InboxNotification.kind != "dm")
        .count()
    )


def total_unread_count(user_id: int) -> int:
    n = unread_dm_count(user_id) + unread_inbox_notification_count(user_id)
    if active_announcement_unread(user_id):
        n += 1
    return n


def get_or_create_thread(user_id: int, other_user_id: int) -> MessageThread:
    if user_id == other_user_id:
        raise ValueError("cannot_message_self")
    ua, ub = _thread_pair(user_id, other_user_id)
    thread = MessageThread.query.filter_by(user_a_id=ua, user_b_id=ub).first()
    if thread:
        return thread
    thread = MessageThread(user_a_id=ua, user_b_id=ub, updated_at=datetime.utcnow())
    db.session.add(thread)
    db.session.flush()
    return thread


def _display_name(user: User | None) -> str:
    if not user:
        return "Användare"
    return (user.display_name or user.username or "Användare").strip()


def send_direct_message(from_user_id: int, to_user_id: int, body: str) -> Message:
    body = normalize_pit_lane_body(body)
    if not body:
        raise ValueError("empty_body")
    if len(body) > MAX_MESSAGE_LENGTH:
        raise ValueError("body_too_long")
    sender = User.query.get(from_user_id)
    recipient = User.query.get(to_user_id)
    if not recipient:
        raise ValueError("user_not_found")

    thread = get_or_create_thread(from_user_id, to_user_id)
    msg = Message(
        thread_id=thread.id,
        from_user_id=from_user_id,
        body=body,
    )
    thread.updated_at = datetime.utcnow()
    db.session.add(msg)
    db.session.flush()

    preview = body[:120] + ("…" if len(body) > 120 else "")
    db.session.add(
        InboxNotification(
            user_id=to_user_id,
            kind="dm",
            title=_display_name(sender),
            preview=preview,
            link_url=f"/pit-lane?thread={thread.id}",
            ref_type="thread",
            ref_id=thread.id,
        )
    )
    db.session.commit()
    try:
        import pit_lane_notify as pln

        pln.notify_dm_received(to_user_id, from_user_id, body, thread.id)
    except Exception as ex:
        print(f"Pit Lane: kunde inte köa DM-e-post: {ex}")
    return msg


def mark_thread_read(thread_id: int, user_id: int) -> None:
    thread = MessageThread.query.get(thread_id)
    if not thread or user_id not in (thread.user_a_id, thread.user_b_id):
        return
    now = datetime.utcnow()
    Message.query.filter(
        Message.thread_id == thread_id,
        Message.from_user_id != user_id,
        Message.read_at.is_(None),
    ).update({"read_at": now})
    InboxNotification.query.filter_by(
        user_id=user_id, ref_type="thread", ref_id=thread_id
    ).filter(InboxNotification.read_at.is_(None)).update({"read_at": now})
    db.session.commit()


def other_user_in_thread(thread: MessageThread, user_id: int) -> int:
    return thread.user_b_id if thread.user_a_id == user_id else thread.user_a_id


def thread_to_dict(thread: MessageThread, viewer_id: int) -> dict:
    other_id = other_user_in_thread(thread, viewer_id)
    other = User.query.get(other_id)
    last = (
        Message.query.filter_by(thread_id=thread.id)
        .order_by(Message.created_at.desc())
        .first()
    )
    unread = (
        Message.query.filter(
            Message.thread_id == thread.id,
            Message.from_user_id != viewer_id,
            Message.read_at.is_(None),
        ).count()
        if last
        else 0
    )
    return {
        "id": thread.id,
        "other_user_id": other_id,
        "other_display_name": _display_name(other),
        "other_username": other.username if other else "",
        "updated_at": thread.updated_at.isoformat() if thread.updated_at else "",
        "last_preview": (last.body[:80] + "…") if last and len(last.body) > 80 else (last.body if last else ""),
        "unread_count": unread,
    }


def announcement_to_dict(ann: AdminAnnouncement) -> dict:
    return {
        "id": ann.id,
        "body": ann.body,
        "priority": ann.priority,
        "is_active": ann.is_active,
        "created_at": ann.created_at.isoformat() if ann.created_at else "",
    }


def recent_items_for_dropdown(user_id: int, limit: int = 6) -> list[dict]:
    items: list[dict] = []
    ann = active_announcement_unread(user_id)
    if ann:
        items.append(
            {
                "kind": "announcement",
                "id": ann.id,
                "title": "Race Control",
                "preview": ann.body[:80],
                "priority": ann.priority,
                "link": "/pit-lane?tab=race-control",
            }
        )
    for n in (
        InboxNotification.query.filter_by(user_id=user_id)
        .filter(InboxNotification.read_at.is_(None))
        .filter(InboxNotification.kind != "dm")
        .order_by(InboxNotification.created_at.desc())
        .limit(limit)
        .all()
    ):
        items.append(
            {
                "kind": n.kind,
                "id": n.id,
                "title": n.title,
                "preview": n.preview or "",
                "link": n.link_url or "/pit-lane",
            }
        )
    threads = (
        MessageThread.query.filter(
            db.or_(
                MessageThread.user_a_id == user_id,
                MessageThread.user_b_id == user_id,
            )
        )
        .order_by(MessageThread.updated_at.desc())
        .limit(limit)
        .all()
    )
    for t in threads:
        td = thread_to_dict(t, user_id)
        if td["unread_count"] > 0:
            items.append(
                {
                    "kind": "dm",
                    "thread_id": t.id,
                    "title": td["other_display_name"],
                    "preview": td["last_preview"],
                    "link": f"/pit-lane?thread={t.id}",
                }
            )
    return items[:limit]


def list_threads_for_user(user_id: int, unread_only: bool = False) -> list[dict]:
    threads = (
        MessageThread.query.filter(
            db.or_(
                MessageThread.user_a_id == user_id,
                MessageThread.user_b_id == user_id,
            )
        )
        .order_by(MessageThread.updated_at.desc())
        .all()
    )
    rows = [thread_to_dict(t, user_id) for t in threads]
    if unread_only:
        rows = [r for r in rows if r["unread_count"] > 0]
    return rows


def mark_all_dm_threads_read(user_id: int) -> int:
    """Markera alla inkomna DM som lästa. Returnerar antal uppdaterade meddelanden."""
    now = datetime.utcnow()
    thread_ids = [
        t.id
        for t in MessageThread.query.filter(
            db.or_(
                MessageThread.user_a_id == user_id,
                MessageThread.user_b_id == user_id,
            )
        ).all()
    ]
    if not thread_ids:
        return 0
    n = (
        Message.query.filter(
            Message.thread_id.in_(thread_ids),
            Message.from_user_id != user_id,
            Message.read_at.is_(None),
        ).update({"read_at": now}, synchronize_session=False)
    )
    InboxNotification.query.filter_by(user_id=user_id, kind="dm").filter(
        InboxNotification.read_at.is_(None)
    ).update({"read_at": now}, synchronize_session=False)
    db.session.commit()
    return int(n or 0)

"""Schemalagda push-påminnelser per användare."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from models import UserReminder, db

_schema_ready = False
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?$")
_GRACE_MINUTES = 5
_VALID_REPEAT = frozenset({"daily", "weekdays", "weekends", "custom"})


def ensure_reminder_tables() -> None:
    global _schema_ready
    if _schema_ready:
        return
    from sqlalchemy import inspect

    if not inspect(db.engine).has_table("user_reminders"):
        db.create_all()
    _schema_ready = True


def _parse_time(value: str) -> tuple[int, int] | None:
    m = _TIME_RE.match((value or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _normalize_days_mask(mask: str | None) -> str | None:
    if mask is None:
        return None
    raw = (mask or "").strip()
    if len(raw) != 7 or any(c not in "01" for c in raw):
        return None
    return raw


def reminder_to_dict(row: UserReminder) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "body": row.body or "",
        "time_local": row.time_local,
        "repeat_mode": row.repeat_mode,
        "days_mask": row.days_mask or "1111100",
        "timezone": row.timezone,
        "enabled": bool(row.enabled),
        "link_url": row.link_url or "",
        "last_sent_on": row.last_sent_on.isoformat() if row.last_sent_on else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_reminders(user_id: int) -> list[dict]:
    ensure_reminder_tables()
    rows = (
        UserReminder.query.filter_by(user_id=int(user_id))
        .order_by(UserReminder.time_local, UserReminder.id)
        .all()
    )
    return [reminder_to_dict(r) for r in rows]


def create_reminder(user_id: int, data: dict) -> tuple[UserReminder | None, str | None]:
    ensure_reminder_tables()
    title = (data.get("title") or "").strip()
    if not title:
        return None, "title_required"
    parsed = _parse_time(data.get("time_local") or "")
    if not parsed:
        return None, "invalid_time"
    repeat = (data.get("repeat_mode") or "weekdays").strip().lower()
    if repeat not in _VALID_REPEAT:
        return None, "invalid_repeat"
    days_mask = _normalize_days_mask(data.get("days_mask"))
    if repeat == "custom" and not days_mask:
        return None, "days_mask_required"
    if repeat != "custom":
        days_mask = None

    hh, mm = parsed
    row = UserReminder(
        user_id=int(user_id),
        title=title[:120],
        body=((data.get("body") or "").strip() or None),
        time_local=f"{hh:02d}:{mm:02d}",
        repeat_mode=repeat,
        days_mask=days_mask,
        timezone=(data.get("timezone") or "Europe/Stockholm").strip()[:64],
        enabled=bool(data.get("enabled", True)),
        link_url=((data.get("link_url") or "").strip() or None),
    )
    db.session.add(row)
    db.session.commit()
    return row, None


def update_reminder(user_id: int, reminder_id: int, data: dict) -> tuple[UserReminder | None, str | None]:
    ensure_reminder_tables()
    row = UserReminder.query.filter_by(id=int(reminder_id), user_id=int(user_id)).first()
    if not row:
        return None, "not_found"

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return None, "title_required"
        row.title = title[:120]
    if "body" in data:
        row.body = ((data.get("body") or "").strip() or None)
    if "time_local" in data:
        parsed = _parse_time(data.get("time_local") or "")
        if not parsed:
            return None, "invalid_time"
        hh, mm = parsed
        row.time_local = f"{hh:02d}:{mm:02d}"
        row.last_sent_on = None
    if "repeat_mode" in data:
        repeat = (data.get("repeat_mode") or "").strip().lower()
        if repeat not in _VALID_REPEAT:
            return None, "invalid_repeat"
        row.repeat_mode = repeat
    if "days_mask" in data:
        row.days_mask = _normalize_days_mask(data.get("days_mask"))
    if row.repeat_mode == "custom" and not row.days_mask:
        return None, "days_mask_required"
    if row.repeat_mode != "custom":
        row.days_mask = None
    if "timezone" in data:
        row.timezone = (data.get("timezone") or "Europe/Stockholm").strip()[:64]
    if "enabled" in data:
        row.enabled = bool(data.get("enabled"))
    if "link_url" in data:
        row.link_url = ((data.get("link_url") or "").strip() or None)

    db.session.commit()
    return row, None


def delete_reminder(user_id: int, reminder_id: int) -> bool:
    ensure_reminder_tables()
    row = UserReminder.query.filter_by(id=int(reminder_id), user_id=int(user_id)).first()
    if not row:
        return False
    db.session.delete(row)
    db.session.commit()
    return True


def _weekday_matches(row: UserReminder, weekday: int) -> bool:
    mode = row.repeat_mode or "weekdays"
    if mode == "daily":
        return True
    if mode == "weekdays":
        return weekday < 5
    if mode == "weekends":
        return weekday >= 5
    if mode == "custom" and row.days_mask and len(row.days_mask) == 7:
        return row.days_mask[weekday] == "1"
    return False


def _to_local(utc_aware: datetime, tz_name: str) -> datetime:
    name = (tz_name or "Europe/Stockholm").strip()
    try:
        from zoneinfo import ZoneInfo

        return utc_aware.astimezone(ZoneInfo(name))
    except Exception:
        pass
    try:
        import pytz

        return utc_aware.astimezone(pytz.timezone(name))
    except Exception:
        from datetime import timedelta

        month = utc_aware.month
        hours = 2 if 3 <= month <= 10 else 1
        return utc_aware.astimezone(timezone(timedelta(hours=hours)))


def _is_due_now(local_now: datetime, hh: int, mm: int) -> bool:
    """True om schemalagd tid infallit inom senaste GRACE_MINUTES (tål Render cold start)."""
    scheduled = local_now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if local_now < scheduled:
        return False
    return local_now < scheduled + timedelta(minutes=_GRACE_MINUTES)


def send_reminder_push(row: UserReminder, *, mark_sent: bool = True) -> dict:
    import push_service as ps

    if not ps.user_has_push(row.user_id):
        return {"ok": False, "error": "no_subscription"}
    preview = (row.body or row.title)[:240]
    link = row.link_url or "/kundmail"
    result = ps.send_push_sync(
        row.user_id,
        row.title[:120],
        preview,
        link,
        tag=f"reminder-{row.id}",
    )
    if result.get("ok") and mark_sent:
        local_now = _to_local(datetime.now(timezone.utc), row.timezone or "Europe/Stockholm")
        row.last_sent_on = local_now.date()
        db.session.commit()
    return result


def send_reminder_test(user_id: int, reminder_id: int) -> dict:
    ensure_reminder_tables()
    row = UserReminder.query.filter_by(id=int(reminder_id), user_id=int(user_id)).first()
    if not row:
        return {"ok": False, "error": "not_found"}
    result = send_reminder_push(row, mark_sent=False)
    return result


def process_due_reminders(now_utc: datetime | None = None) -> dict:
    """Skicka push för påminnelser vars tid matchar (anropas varje minut via cron)."""
    ensure_reminder_tables()
    if not UserReminder.query.filter_by(enabled=True).limit(1).first():
        return {"ok": True, "sent": 0, "skipped": 0, "checked": 0, "idle": True}
    import push_service as ps

    utc = now_utc or datetime.utcnow()
    if utc.tzinfo is None:
        utc_aware = utc.replace(tzinfo=timezone.utc)
    else:
        utc_aware = utc.astimezone(timezone.utc)

    sent = 0
    skipped = 0
    errors: list[str] = []

    rows = UserReminder.query.filter_by(enabled=True).all()
    stockholm_now = _to_local(utc_aware, "Europe/Stockholm")
    for row in rows:
        local_now = _to_local(utc_aware, row.timezone or "Europe/Stockholm")
        if not _weekday_matches(row, local_now.weekday()):
            skipped += 1
            continue

        parsed = _parse_time(row.time_local)
        if not parsed:
            errors.append(f"reminder {row.id}: invalid time")
            continue
        hh, mm = parsed
        if not _is_due_now(local_now, hh, mm):
            skipped += 1
            continue

        today_local = local_now.date()
        if row.last_sent_on == today_local:
            skipped += 1
            continue

        result = send_reminder_push(row, mark_sent=True)
        if result.get("ok"):
            sent += 1
            print(f"Reminder push OK id={row.id} user={row.user_id}")
        else:
            err = result.get("error") or "send_failed"
            errors.append(f"reminder {row.id}: {err}")

    return {
        "ok": True,
        "sent": sent,
        "skipped": skipped,
        "checked": len(rows),
        "server_time_stockholm": stockholm_now.strftime("%Y-%m-%d %H:%M"),
        "errors": errors[:20],
    }

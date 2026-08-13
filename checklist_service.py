"""Personlig checklista per användare (Kundmail)."""
from __future__ import annotations

from models import UserChecklistItem, db

_schema_ready = False


def ensure_checklist_tables() -> None:
    global _schema_ready
    if _schema_ready:
        return
    from sqlalchemy import inspect

    if not inspect(db.engine).has_table("user_checklist_items"):
        db.create_all()
    _schema_ready = True


def item_to_dict(row: UserChecklistItem) -> dict:
    return {
        "id": row.id,
        "text": row.text,
        "done": bool(row.done),
        "sort_order": int(row.sort_order or 0),
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
    }


def list_items(user_id: int) -> list[dict]:
    ensure_checklist_tables()
    rows = (
        UserChecklistItem.query.filter_by(user_id=user_id)
        .order_by(UserChecklistItem.done.asc(), UserChecklistItem.id.desc())
        .limit(200)
        .all()
    )
    return [item_to_dict(r) for r in rows]


def create_item(user_id: int, text: str) -> tuple[UserChecklistItem | None, str | None]:
    ensure_checklist_tables()
    cleaned = (text or "").strip()
    if not cleaned:
        return None, "Tom punkt"
    if len(cleaned) > 500:
        return None, "Max 500 tecken"
    row = UserChecklistItem(user_id=user_id, text=cleaned, done=False, sort_order=0)
    db.session.add(row)
    db.session.commit()
    return row, None


def set_done(user_id: int, item_id: int, done: bool) -> tuple[UserChecklistItem | None, str | None]:
    ensure_checklist_tables()
    row = UserChecklistItem.query.filter_by(id=item_id, user_id=user_id).first()
    if not row:
        return None, "not_found"
    row.done = bool(done)
    db.session.commit()
    return row, None


def delete_item(user_id: int, item_id: int) -> bool:
    ensure_checklist_tables()
    row = UserChecklistItem.query.filter_by(id=item_id, user_id=user_id).first()
    if not row:
        return False
    db.session.delete(row)
    db.session.commit()
    return True


def clear_done(user_id: int) -> int:
    ensure_checklist_tables()
    rows = UserChecklistItem.query.filter_by(user_id=user_id, done=True).all()
    count = len(rows)
    for row in rows:
        db.session.delete(row)
    db.session.commit()
    return count
